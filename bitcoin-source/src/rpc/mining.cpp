// Copyright (c) 2010 Satoshi Nakamoto
// Copyright (c) 2009-present The Bitcoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include <bitcoin-build-config.h> // IWYU pragma: keep

#include <interfaces/mining.h>

#include <addresstype.h>
#include <arith_uint256.h>
#include <chain.h>
#include <chainparams.h>
#include <chainparamsbase.h>
#include <consensus/amount.h>
#include <consensus/consensus.h>
#include <consensus/merkle.h>
#include <consensus/params.h>
#include <consensus/validation.h>
#include <core_io.h>
#include <crypto/hex_base.h>
#include <hash.h>
#include <interfaces/types.h>
#include <key_io.h>
#include <net.h>
#include <netbase.h>
#include <node/blockstorage.h>
#include <node/context.h>
#include <node/miner.h>
#include <node/mining_args.h>
#include <node/mining_types.h>
#include <node/warnings.h>
#include <policy/feerate.h>
#include <policy/policy.h>
#include <pow.h>
#include <crypto/ethash/include/ethash/ethash.hpp>

namespace {
// Sharecoin/GPU-mined-crypto note: keyed by ProgPoW header hash hex string
// (getblocktemplate's own "pprpcheader" field), so an external GPU miner's
// in-flight search over a stable header hash isn't invalidated by a later
// getblocktemplate call producing a new template as the mempool changes -
// pprpcsb below looks the full block back up by that same key once a
// miner reports a solved nonce/mix_hash. Shape and naming deliberately
// mirror Ravencoin's own mapRVNKAWBlockTemplates (checked directly against
// their real source, not guessed) - existing GPU miner software already
// expects this exact RPC surface, not a Sharecoin-specific one.
std::map<std::string, CBlock> g_progpow_block_templates;

// Payout script used for the coinbase output of getblocktemplate's internal
// createNewBlock() call, below - unlike real BIP22 pools (which build their
// own coinbase and never touch this path), pprpcsb submits the server's
// cached template unmodified, so without this the coinbase output script
// defaults to CScript()'s empty/anyone-can-spend script. Set via the
// setprogpowminingaddress RPC.
CScript g_progpow_coinbase_script;
} // namespace
#include <primitives/block.h>
#include <primitives/transaction.h>
#include <rpc/blockchain.h>
#include <rpc/mining.h>
#include <rpc/protocol.h>
#include <rpc/request.h>
#include <rpc/server.h>
#include <rpc/server_util.h>
#include <rpc/util.h>
#include <script/descriptor.h>
#include <script/script.h>
#include <script/signingprovider.h>
#include <serialize.h>
#include <streams.h>
#include <sync.h>
#include <tinyformat.h>
#include <txmempool.h>
#include <uint256.h>
#include <univalue.h>
#include <util/chaintype.h>
#include <util/check.h>
#include <util/signalinterrupt.h>
#include <util/strencodings.h>
#include <util/string.h>
#include <util/time.h>
#include <validation.h>
#include <validationinterface.h>
#include <versionbits.h>

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <initializer_list>
#include <limits>
#include <charconv>
#include <map>
#include <memory>
#include <optional>
#include <set>
#include <span>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

using interfaces::BlockRef;
using interfaces::BlockTemplate;
using interfaces::Mining;
using node::BlockAssembler;
using node::GetMinimumTime;
using node::NodeContext;
using node::RegenerateCommitments;
using node::UpdateTime;
using util::ToString;

/**
 * Return average network hashes per second based on the last 'lookup' blocks,
 * or from the last difficulty change if 'lookup' is -1.
 * If 'height' is -1, compute the estimate from current chain tip.
 * If 'height' is a valid block height, compute the estimate at the time when a given block was found.
 */
static UniValue GetNetworkHashPS(int lookup, int height, const CChain& active_chain) {
    if (lookup < -1 || lookup == 0) {
        throw JSONRPCError(RPC_INVALID_PARAMETER, "Invalid nblocks. Must be a positive number or -1.");
    }

    if (height < -1 || height > active_chain.Height()) {
        throw JSONRPCError(RPC_INVALID_PARAMETER, "Block does not exist at specified height");
    }

    const CBlockIndex* pb = active_chain.Tip();

    if (height >= 0) {
        pb = active_chain[height];
    }

    if (pb == nullptr || !pb->nHeight)
        return 0;

    // If lookup is -1, then use blocks since last difficulty change.
    if (lookup == -1)
        lookup = pb->nHeight % Params().GetConsensus().DifficultyAdjustmentInterval() + 1;

    // If lookup is larger than chain, then set it to chain length.
    if (lookup > pb->nHeight)
        lookup = pb->nHeight;

    const CBlockIndex* pb0 = pb;
    int64_t minTime = pb0->GetBlockTime();
    int64_t maxTime = minTime;
    for (int i = 0; i < lookup; i++) {
        pb0 = pb0->pprev;
        int64_t time = pb0->GetBlockTime();
        minTime = std::min(time, minTime);
        maxTime = std::max(time, maxTime);
    }

    // In case there's a situation where minTime == maxTime, we don't want a divide by zero exception.
    if (minTime == maxTime)
        return 0;

    arith_uint256 workDiff = pb->nChainWork - pb0->nChainWork;
    int64_t timeDiff = maxTime - minTime;

    return workDiff.getdouble() / timeDiff;
}

static RPCMethod getnetworkhashps()
{
    return RPCMethod{
        "getnetworkhashps",
        "Returns the estimated network hashes per second based on the last n blocks.\n"
                "Pass in [blocks] to override # of blocks, -1 specifies since last difficulty change.\n"
                "Pass in [height] to estimate the network speed at the time when a certain block was found.\n",
                {
                    {"nblocks", RPCArg::Type::NUM, RPCArg::Default{120}, "The number of previous blocks to calculate estimate from, or -1 for blocks since last difficulty change."},
                    {"height", RPCArg::Type::NUM, RPCArg::Default{-1}, "To estimate at the time of the given height."},
                },
                RPCResult{
                    RPCResult::Type::NUM, "", "Hashes per second estimated"},
                RPCExamples{
                    HelpExampleCli("getnetworkhashps", "")
            + HelpExampleRpc("getnetworkhashps", "")
                },
        [](const RPCMethod& self, const JSONRPCRequest& request) -> UniValue
{
    ChainstateManager& chainman = EnsureAnyChainman(request.context);
    LOCK(cs_main);
    return GetNetworkHashPS(self.Arg<int>("nblocks"), self.Arg<int>("height"), chainman.ActiveChain());
},
    };
}

static bool GenerateBlock(ChainstateManager& chainman, CBlock&& block, uint64_t& max_tries, std::shared_ptr<const CBlock>& block_out, bool process_new_block)
{
    block_out.reset();
    block.hashMerkleRoot = BlockMerkleRoot(block);

    // MineBlock (pow.cpp) runs the real ProgPoW search, up to max_tries
    // nonces starting at 0, decrementing max_tries by however many were
    // actually consumed (same shared-budget-across-calls semantics the
    // original manual ++block.nNonce loop had), and sets block.nNonce64/
    // mix_hash on success - replaces calling CheckProofOfWork(block.GetHash(), ...)
    // directly in a loop, which no longer applies since GetHash() is the
    // block's identity hash, not its proof-of-work hash (see primitives/block.h).
    if (!MineBlock(block, /*start_nonce=*/0, max_tries) || chainman.m_interrupt) {
        return false;
    }

    block_out = std::make_shared<const CBlock>(std::move(block));

    if (!process_new_block) return true;

    if (!chainman.ProcessNewBlock(block_out, /*force_processing=*/true, /*min_pow_checked=*/true, nullptr)) {
        throw JSONRPCError(RPC_INTERNAL_ERROR, "ProcessNewBlock, block not accepted");
    }

    return true;
}

static UniValue generateBlocks(ChainstateManager& chainman, Mining& miner, const CScript& coinbase_output_script, int nGenerate, uint64_t nMaxTries)
{
    UniValue blockHashes(UniValue::VARR);
    while (nGenerate > 0 && !chainman.m_interrupt) {
        std::unique_ptr<BlockTemplate> block_template(miner.createNewBlock({ .coinbase_output_script = coinbase_output_script }, /*cooldown=*/false));
        CHECK_NONFATAL(block_template);

        std::shared_ptr<const CBlock> block_out;
        if (!GenerateBlock(chainman, block_template->getBlock(), nMaxTries, block_out, /*process_new_block=*/true)) {
            break;
        }

        if (block_out) {
            --nGenerate;
            blockHashes.push_back(block_out->GetHash().GetHex());
        }
    }
    return blockHashes;
}

static bool getScriptFromDescriptor(std::string_view descriptor, CScript& script, std::string& error)
{
    FlatSigningProvider key_provider;
    const auto descs = Parse(descriptor, key_provider, error, /* require_checksum = */ false);
    if (descs.empty()) return false;
    if (descs.size() > 1) {
        throw JSONRPCError(RPC_INVALID_PARAMETER, "Multipath descriptor not accepted");
    }
    const auto& desc = descs.at(0);
    if (desc->IsRange()) {
        throw JSONRPCError(RPC_INVALID_PARAMETER, "Ranged descriptor not accepted. Maybe pass through deriveaddresses first?");
    }

    FlatSigningProvider provider;
    std::vector<CScript> scripts;
    if (!desc->Expand(0, key_provider, scripts, provider)) {
        throw JSONRPCError(RPC_INVALID_ADDRESS_OR_KEY, "Cannot derive script without private keys");
    }

    // Combo descriptors can have 2 or 4 scripts, so we can't just check scripts.size() == 1
    CHECK_NONFATAL(scripts.size() > 0 && scripts.size() <= 4);

    if (scripts.size() == 1) {
        script = scripts.at(0);
    } else if (scripts.size() == 4) {
        // For uncompressed keys, take the 3rd script, since it is p2wpkh
        script = scripts.at(2);
    } else {
        // Else take the 2nd script, since it is p2pkh
        script = scripts.at(1);
    }

    return true;
}

static RPCMethod generatetodescriptor()
{
    return RPCMethod{
        "generatetodescriptor",
        "Mine to a specified descriptor and return the block hashes.",
        {
            {"num_blocks", RPCArg::Type::NUM, RPCArg::Optional::NO, "How many blocks are generated."},
            {"descriptor", RPCArg::Type::STR, RPCArg::Optional::NO, "The descriptor to send the newly generated bitcoin to."},
            {"maxtries", RPCArg::Type::NUM, RPCArg::Default{DEFAULT_MAX_TRIES}, "How many iterations to try."},
        },
        RPCResult{
            RPCResult::Type::ARR, "", "hashes of blocks generated",
            {
                {RPCResult::Type::STR_HEX, "", "blockhash"},
            }
        },
        RPCExamples{
            "\nGenerate 11 blocks to mydesc\n" + HelpExampleCli("generatetodescriptor", "11 \"mydesc\"")},
        [](const RPCMethod& self, const JSONRPCRequest& request) -> UniValue
{
    const auto num_blocks{self.Arg<int>("num_blocks")};
    const auto max_tries{self.Arg<uint64_t>("maxtries")};

    CScript coinbase_output_script;
    std::string error;
    if (!getScriptFromDescriptor(self.Arg<std::string_view>("descriptor"), coinbase_output_script, error)) {
        throw JSONRPCError(RPC_INVALID_ADDRESS_OR_KEY, error);
    }

    NodeContext& node = EnsureAnyNodeContext(request.context);
    Mining& miner = EnsureMining(node);
    ChainstateManager& chainman = EnsureChainman(node);

    return generateBlocks(chainman, miner, coinbase_output_script, num_blocks, max_tries);
},
    };
}

static RPCMethod generate()
{
    return RPCMethod{"generate", "has been replaced by the -generate cli option. Refer to -help for more information.", {}, {}, RPCExamples{""}, [](const RPCMethod& self, const JSONRPCRequest& request) -> UniValue {
        throw JSONRPCError(RPC_METHOD_NOT_FOUND, self.ToString());
    }};
}

static RPCMethod generatetoaddress()
{
    return RPCMethod{"generatetoaddress",
        "Mine to a specified address and return the block hashes.",
         {
             {"nblocks", RPCArg::Type::NUM, RPCArg::Optional::NO, "How many blocks are generated."},
             {"address", RPCArg::Type::STR, RPCArg::Optional::NO, "The address to send the newly generated bitcoin to."},
             {"maxtries", RPCArg::Type::NUM, RPCArg::Default{DEFAULT_MAX_TRIES}, "How many iterations to try."},
         },
         RPCResult{
             RPCResult::Type::ARR, "", "hashes of blocks generated",
             {
                 {RPCResult::Type::STR_HEX, "", "blockhash"},
             }},
         RPCExamples{
            "\nGenerate 11 blocks to myaddress\n"
            + HelpExampleCli("generatetoaddress", "11 \"myaddress\"")
            + "If you are using the " CLIENT_NAME " wallet, you can get a new address to send the newly generated bitcoin to with:\n"
            + HelpExampleCli("getnewaddress", "")
                },
        [](const RPCMethod& self, const JSONRPCRequest& request) -> UniValue
{
    const int num_blocks{request.params[0].getInt<int>()};
    const uint64_t max_tries{request.params[2].isNull() ? DEFAULT_MAX_TRIES : request.params[2].getInt<int>()};

    CTxDestination destination = DecodeDestination(request.params[1].get_str());
    if (!IsValidDestination(destination)) {
        throw JSONRPCError(RPC_INVALID_ADDRESS_OR_KEY, "Error: Invalid address");
    }

    NodeContext& node = EnsureAnyNodeContext(request.context);
    Mining& miner = EnsureMining(node);
    ChainstateManager& chainman = EnsureChainman(node);

    CScript coinbase_output_script = GetScriptForDestination(destination);

    return generateBlocks(chainman, miner, coinbase_output_script, num_blocks, max_tries);
},
    };
}

static RPCMethod generateblock()
{
    return RPCMethod{"generateblock",
        "Mine a set of ordered transactions to a specified address or descriptor and return the block hash.\n"
        "Transaction fees are not collected in the block reward.",
        {
            {"output", RPCArg::Type::STR, RPCArg::Optional::NO, "The address or descriptor to send the newly generated bitcoin to."},
            {"transactions", RPCArg::Type::ARR, RPCArg::Optional::NO, "An array of hex strings which are either txids or raw transactions.\n"
                "Txids must reference transactions currently in the mempool.\n"
                "All transactions must be valid and in valid order, otherwise the block will be rejected.",
                {
                    {"rawtx/txid", RPCArg::Type::STR_HEX, RPCArg::Optional::OMITTED, ""},
                },
            },
            {"submit", RPCArg::Type::BOOL, RPCArg::Default{true}, "Whether to submit the block before the RPC call returns or to return it as hex."},
        },
        RPCResult{
            RPCResult::Type::OBJ, "", "",
            {
                {RPCResult::Type::STR_HEX, "hash", "hash of generated block"},
                {RPCResult::Type::STR_HEX, "hex", /*optional=*/true, "hex of generated block, only present when submit=false"},
            }
        },
        RPCExamples{
            "\nGenerate a block to myaddress, with txs rawtx and mempool_txid\n"
            + HelpExampleCli("generateblock", R"("myaddress" '["rawtx", "mempool_txid"]')")
        },
        [](const RPCMethod& self, const JSONRPCRequest& request) -> UniValue
{
    const auto address_or_descriptor = request.params[0].get_str();
    CScript coinbase_output_script;
    std::string error;

    if (!getScriptFromDescriptor(address_or_descriptor, coinbase_output_script, error)) {
        const auto destination = DecodeDestination(address_or_descriptor);
        if (!IsValidDestination(destination)) {
            throw JSONRPCError(RPC_INVALID_ADDRESS_OR_KEY, "Error: Invalid address or descriptor");
        }

        coinbase_output_script = GetScriptForDestination(destination);
    }

    NodeContext& node = EnsureAnyNodeContext(request.context);
    Mining& miner = EnsureMining(node);
    const CTxMemPool& mempool = EnsureMemPool(node);

    std::vector<CTransactionRef> txs;
    const auto raw_txs_or_txids = request.params[1].get_array();
    for (size_t i = 0; i < raw_txs_or_txids.size(); i++) {
        const auto& str{raw_txs_or_txids[i].get_str()};

        CMutableTransaction mtx;
        if (auto txid{Txid::FromHex(str)}) {
            const auto tx{mempool.get(*txid)};
            if (!tx) {
                throw JSONRPCError(RPC_INVALID_ADDRESS_OR_KEY, strprintf("Transaction %s not in mempool.", str));
            }

            txs.emplace_back(tx);

        } else if (DecodeHexTx(mtx, str)) {
            txs.push_back(MakeTransactionRef(std::move(mtx)));

        } else {
            throw JSONRPCError(RPC_DESERIALIZATION_ERROR, strprintf("Transaction decode failed for %s. Make sure the tx has at least one input.", str));
        }
    }

    const bool process_new_block{request.params[2].isNull() ? true : request.params[2].get_bool()};
    CBlock block;

    ChainstateManager& chainman = EnsureChainman(node);
    {
        LOCK(chainman.GetMutex());
        {
            std::unique_ptr<BlockTemplate> block_template{miner.createNewBlock({.use_mempool = false, .coinbase_output_script = coinbase_output_script}, /*cooldown=*/false)};
            CHECK_NONFATAL(block_template);

            block = block_template->getBlock();
        }

        CHECK_NONFATAL(block.vtx.size() == 1);

        // Add transactions
        block.vtx.insert(block.vtx.end(), txs.begin(), txs.end());
        RegenerateCommitments(block, chainman);

        if (BlockValidationState state{TestBlockValidity(chainman.ActiveChainstate(), block, /*check_pow=*/false, /*check_merkle_root=*/false)}; !state.IsValid()) {
            throw JSONRPCError(RPC_VERIFY_ERROR, strprintf("TestBlockValidity failed: %s", state.ToString()));
        }
    }

    std::shared_ptr<const CBlock> block_out;
    uint64_t max_tries{DEFAULT_MAX_TRIES};

    if (!GenerateBlock(chainman, std::move(block), max_tries, block_out, process_new_block) || !block_out) {
        throw JSONRPCError(RPC_MISC_ERROR, "Failed to make block.");
    }

    UniValue obj(UniValue::VOBJ);
    obj.pushKV("hash", block_out->GetHash().GetHex());
    if (!process_new_block) {
        DataStream block_ser;
        block_ser << TX_WITH_WITNESS(*block_out);
        obj.pushKV("hex", HexStr(block_ser));
    }
    return obj;
},
    };
}

static RPCMethod getmininginfo()
{
    return RPCMethod{
        "getmininginfo",
        "Returns a json object containing mining-related information.",
                {},
                RPCResult{
                    RPCResult::Type::OBJ, "", "",
                    {
                        {RPCResult::Type::NUM, "blocks", "The current block"},
                        {RPCResult::Type::NUM, "currentblockweight", /*optional=*/true, "The block weight (including reserved weight for block header, txs count and coinbase tx) of the last assembled block (only present if a block was ever assembled)"},
                        {RPCResult::Type::NUM, "currentblocktx", /*optional=*/true, "The number of block transactions (excluding coinbase) of the last assembled block (only present if a block was ever assembled)"},
                        {RPCResult::Type::STR_HEX, "bits", "The current nBits, compact representation of the block difficulty target"},
                        {RPCResult::Type::NUM, "difficulty", "The current difficulty"},
                        {RPCResult::Type::STR_HEX, "target", "The current target"},
                        {RPCResult::Type::NUM, "networkhashps", "The network hashes per second"},
                        {RPCResult::Type::NUM, "pooledtx", "The size of the mempool"},
                        {RPCResult::Type::STR_AMOUNT, "blockmintxfee", "Minimum feerate of packages selected for block inclusion in " + CURRENCY_UNIT + "/kvB"},
                        {RPCResult::Type::STR, "chain", "current network name (" LIST_CHAIN_NAMES ")"},
                        {RPCResult::Type::STR_HEX, "signet_challenge", /*optional=*/true, "The block challenge (aka. block script), in hexadecimal (only present if the current network is a signet)"},
                        {RPCResult::Type::OBJ, "next", "The next block",
                        {
                            {RPCResult::Type::NUM, "height", "The next height"},
                            {RPCResult::Type::STR_HEX, "bits", "The next target nBits"},
                            {RPCResult::Type::NUM, "difficulty", "The next difficulty"},
                            {RPCResult::Type::STR_HEX, "target", "The next target"}
                        }},
                        (IsDeprecatedRPCEnabled("warnings") ?
                            RPCResult{RPCResult::Type::STR, "warnings", "any network and blockchain warnings (DEPRECATED)"} :
                            RPCResult{RPCResult::Type::ARR, "warnings", "any network and blockchain warnings (run with `-deprecatedrpc=warnings` to return the latest warning as a single string)",
                            {
                                {RPCResult::Type::STR, "", "warning"},
                            }
                            }
                        ),
                    }},
                RPCExamples{
                    HelpExampleCli("getmininginfo", "")
            + HelpExampleRpc("getmininginfo", "")
                },
        [](const RPCMethod& self, const JSONRPCRequest& request) -> UniValue
{
    NodeContext& node = EnsureAnyNodeContext(request.context);
    const CTxMemPool& mempool = EnsureMemPool(node);
    ChainstateManager& chainman = EnsureChainman(node);
    LOCK(cs_main);
    const CChain& active_chain = chainman.ActiveChain();
    CBlockIndex& tip{*CHECK_NONFATAL(active_chain.Tip())};

    UniValue obj(UniValue::VOBJ);
    obj.pushKV("blocks", active_chain.Height());
    if (BlockAssembler::m_last_block_weight) obj.pushKV("currentblockweight", *BlockAssembler::m_last_block_weight);
    if (BlockAssembler::m_last_block_num_txs) obj.pushKV("currentblocktx", *BlockAssembler::m_last_block_num_txs);
    obj.pushKV("bits", strprintf("%08x", tip.nBits));
    obj.pushKV("difficulty", GetDifficulty(tip));
    obj.pushKV("target", GetTarget(tip, chainman.GetConsensus().powLimit).GetHex());
    obj.pushKV("networkhashps",    getnetworkhashps().HandleRequest(request));
    obj.pushKV("pooledtx", mempool.size());
    const auto mining_options{node::FlattenMiningOptions(node.mining_args)};
    obj.pushKV("blockmintxfee", ValueFromAmount(CHECK_NONFATAL(mining_options.block_min_fee_rate)->GetFeePerK()));
    obj.pushKV("chain", chainman.GetParams().GetChainTypeString());

    UniValue next(UniValue::VOBJ);
    CBlockIndex next_index;
    NextEmptyBlockIndex(tip, chainman.GetConsensus(), next_index);

    next.pushKV("height", next_index.nHeight);
    next.pushKV("bits", strprintf("%08x", next_index.nBits));
    next.pushKV("difficulty", GetDifficulty(next_index));
    next.pushKV("target", GetTarget(next_index, chainman.GetConsensus().powLimit).GetHex());
    obj.pushKV("next", next);

    if (chainman.GetParams().GetChainType() == ChainType::SIGNET) {
        const std::vector<uint8_t>& signet_challenge =
            chainman.GetConsensus().signet_challenge;
        obj.pushKV("signet_challenge", HexStr(signet_challenge));
    }
    obj.pushKV("warnings", node::GetWarningsForRpc(*CHECK_NONFATAL(node.warnings), IsDeprecatedRPCEnabled("warnings")));
    return obj;
},
    };
}


// NOTE: Unlike wallet RPC (which use BTC values), mining RPCs follow GBT (BIP 22) in using satoshi amounts
static RPCMethod prioritisetransaction()
{
    return RPCMethod{"prioritisetransaction",
                "Accepts the transaction into mined blocks at a higher (or lower) priority\n",
                {
                    {"txid", RPCArg::Type::STR_HEX, RPCArg::Optional::NO, "The transaction id."},
                    {"dummy", RPCArg::Type::NUM, RPCArg::Optional::OMITTED, "API-Compatibility for previous API. Must be zero or null.\n"
            "                  DEPRECATED. For forward compatibility use named arguments and omit this parameter."},
                    {"fee_delta", RPCArg::Type::NUM, RPCArg::Optional::NO, "The fee value (in satoshis) to add (or subtract, if negative).\n"
            "                  Note, that this value is not a fee rate. It is a value to modify absolute fee of the TX.\n"
            "                  The fee is not actually paid, only the algorithm for selecting transactions into a block\n"
            "                  considers the transaction as it would have paid a higher (or lower) fee."},
                },
                RPCResult{
                    RPCResult::Type::BOOL, "", "Returns true"},
                RPCExamples{
                    HelpExampleCli("prioritisetransaction", "\"txid\" 0.0 10000")
            + HelpExampleRpc("prioritisetransaction", "\"txid\", 0.0, 10000")
                },
        [](const RPCMethod& self, const JSONRPCRequest& request) -> UniValue
{
    LOCK(cs_main);

    auto txid{Txid::FromUint256(ParseHashV(request.params[0], "txid"))};
    const auto dummy{self.MaybeArg<double>("dummy")};
    CAmount nAmount = request.params[2].getInt<int64_t>();

    if (dummy && *dummy != 0) {
        throw JSONRPCError(RPC_INVALID_PARAMETER, "Priority is no longer supported, dummy argument to prioritisetransaction must be 0.");
    }

    CTxMemPool& mempool = EnsureAnyMemPool(request.context);

    // Non-0 fee dust transactions are not allowed for entry, and modification not allowed afterwards
    const auto& tx = mempool.get(txid);
    if (mempool.m_opts.require_standard && tx && !GetDust(*tx, mempool.m_opts.dust_relay_feerate).empty()) {
        throw JSONRPCError(RPC_INVALID_PARAMETER, "Priority is not supported for transactions with dust outputs.");
    }

    mempool.PrioritiseTransaction(txid, nAmount);
    return true;
},
    };
}

static RPCMethod getprioritisedtransactions()
{
    return RPCMethod{"getprioritisedtransactions",
        "Returns a map of all user-created (see prioritisetransaction) fee deltas by txid, and whether the tx is present in mempool.",
        {},
        RPCResult{
            RPCResult::Type::OBJ_DYN, "", "prioritisation keyed by txid",
            {
                {RPCResult::Type::OBJ, "<transactionid>", "", {
                    {RPCResult::Type::NUM, "fee_delta", "transaction fee delta in satoshis"},
                    {RPCResult::Type::BOOL, "in_mempool", "whether this transaction is currently in mempool"},
                    {RPCResult::Type::NUM, "modified_fee", /*optional=*/true, "modified fee in satoshis. Only returned if in_mempool=true"},
                }}
            },
        },
        RPCExamples{
            HelpExampleCli("getprioritisedtransactions", "")
            + HelpExampleRpc("getprioritisedtransactions", "")
        },
        [](const RPCMethod& self, const JSONRPCRequest& request) -> UniValue
        {
            NodeContext& node = EnsureAnyNodeContext(request.context);
            CTxMemPool& mempool = EnsureMemPool(node);
            UniValue rpc_result{UniValue::VOBJ};
            for (const auto& delta_info : mempool.GetPrioritisedTransactions()) {
                UniValue result_inner{UniValue::VOBJ};
                result_inner.pushKV("fee_delta", delta_info.delta);
                result_inner.pushKV("in_mempool", delta_info.in_mempool);
                if (delta_info.in_mempool) {
                    result_inner.pushKV("modified_fee", *delta_info.modified_fee);
                }
                rpc_result.pushKV(delta_info.txid.GetHex(), std::move(result_inner));
            }
            return rpc_result;
        },
    };
}


// NOTE: Assumes a conclusive result; if result is inconclusive, it must be handled by caller
static UniValue BIP22ValidationResult(const BlockValidationState& state)
{
    if (state.IsValid())
        return UniValue::VNULL;

    if (state.IsError())
        throw JSONRPCError(RPC_VERIFY_ERROR, state.ToString());
    if (state.IsInvalid())
    {
        std::string strRejectReason = state.GetRejectReason();
        if (strRejectReason.empty())
            return "rejected";
        return strRejectReason;
    }
    // Should be impossible
    return "valid?";
}

// Prefix rule name with ! if not optional, see BIP9
static std::string gbt_rule_value(const std::string& name, bool gbt_optional_rule)
{
    std::string s{name};
    if (!gbt_optional_rule) {
        s.insert(s.begin(), '!');
    }
    return s;
}

static RPCMethod getblocktemplate()
{
    return RPCMethod{
        "getblocktemplate",
        "If the request parameters include a 'mode' key, that is used to explicitly select between the default 'template' request or a 'proposal'.\n"
        "It returns data needed to construct a block to work on.\n"
        "For full specification, see BIPs 22, 23, 9, and 145:\n"
        "    https://github.com/bitcoin/bips/blob/master/bip-0022.mediawiki\n"
        "    https://github.com/bitcoin/bips/blob/master/bip-0023.mediawiki\n"
        "    https://github.com/bitcoin/bips/blob/master/bip-0009.mediawiki#getblocktemplate_changes\n"
        "    https://github.com/bitcoin/bips/blob/master/bip-0145.mediawiki\n",
        {
            {"template_request", RPCArg::Type::OBJ, RPCArg::Optional::NO, "Format of the template",
            {
                {"mode", RPCArg::Type::STR, /* treat as named arg */ RPCArg::Optional::OMITTED, "This must be set to \"template\", \"proposal\" (see BIP 23), or omitted"},
                {"capabilities", RPCArg::Type::ARR, /* treat as named arg */ RPCArg::Optional::OMITTED, "A list of strings",
                {
                    {"str", RPCArg::Type::STR, RPCArg::Optional::OMITTED, "client side supported feature, 'longpoll', 'coinbasevalue', 'proposal', 'serverlist', 'workid'"},
                }},
                {"rules", RPCArg::Type::ARR, RPCArg::Optional::NO, "A list of strings",
                {
                    {"segwit", RPCArg::Type::STR, RPCArg::Optional::NO, "(literal) indicates client side segwit support"},
                    {"str", RPCArg::Type::STR, RPCArg::Optional::OMITTED, "other client side supported softfork deployment"},
                }},
                {"longpollid", RPCArg::Type::STR, RPCArg::Optional::OMITTED, "delay processing request until the result would vary significantly from the \"longpollid\" of a prior template"},
                {"data", RPCArg::Type::STR_HEX, RPCArg::Optional::OMITTED, "proposed block data to check, encoded in hexadecimal; valid only for mode=\"proposal\""},
            },
            },
        },
        {
            RPCResult{"If the proposal was accepted with mode=='proposal'", RPCResult::Type::NONE, "", ""},
            RPCResult{"If the proposal was not accepted with mode=='proposal'", RPCResult::Type::STR, "", "According to BIP22"},
            RPCResult{"Otherwise", RPCResult::Type::OBJ, "", "",
            {
                {RPCResult::Type::NUM, "version", "The preferred block version"},
                {RPCResult::Type::ARR, "rules", "specific block rules that are to be enforced",
                {
                    {RPCResult::Type::STR, "", "name of a rule the client must understand to some extent; see BIP 9 for format"},
                }},
                {RPCResult::Type::OBJ_DYN, "vbavailable", "set of pending, supported versionbit (BIP 9) softfork deployments",
                {
                    {RPCResult::Type::NUM, "rulename", "identifies the bit number as indicating acceptance and readiness for the named softfork rule"},
                }},
                {RPCResult::Type::ARR, "capabilities", "",
                {
                    {RPCResult::Type::STR, "value", "A supported feature, for example 'proposal'"},
                }},
                {RPCResult::Type::NUM, "vbrequired", "bit mask of versionbits the server requires set in submissions"},
                {RPCResult::Type::STR, "previousblockhash", "The hash of current highest block"},
                {RPCResult::Type::ARR, "transactions", "contents of non-coinbase transactions that should be included in the next block",
                {
                    {RPCResult::Type::OBJ, "", "",
                    {
                        {RPCResult::Type::STR_HEX, "data", "transaction data encoded in hexadecimal (byte-for-byte)"},
                        {RPCResult::Type::STR_HEX, "txid", "transaction hash excluding witness data, shown in byte-reversed hex"},
                        {RPCResult::Type::STR_HEX, "hash", "transaction hash including witness data, shown in byte-reversed hex"},
                        {RPCResult::Type::ARR, "depends", "array of numbers",
                        {
                            {RPCResult::Type::NUM, "", "transactions before this one (by 1-based index in 'transactions' list) that must be present in the final block if this one is"},
                        }},
                        {RPCResult::Type::NUM, "fee", "difference in value between transaction inputs and outputs (in satoshis); for coinbase transactions, this is a negative Number of the total collected block fees (ie, not including the block subsidy); if key is not present, fee is unknown and clients MUST NOT assume there isn't one"},
                        {RPCResult::Type::NUM, "sigops", "total SigOps cost, as counted for purposes of block limits; if key is not present, sigop cost is unknown and clients MUST NOT assume it is zero"},
                        {RPCResult::Type::NUM, "weight", "total transaction weight, as counted for purposes of block limits"},
                    }},
                }},
                {RPCResult::Type::OBJ_DYN, "coinbaseaux", "data that should be included in the coinbase's scriptSig content",
                {
                    {RPCResult::Type::STR_HEX, "key", "values must be in the coinbase (keys may be ignored)"},
                }},
                {RPCResult::Type::NUM, "coinbasevalue", "maximum allowable input to coinbase transaction, including the generation award and transaction fees (in satoshis)"},
                {RPCResult::Type::STR, "longpollid", "an id to include with a request to longpoll on an update to this template"},
                {RPCResult::Type::STR, "target", "The hash target"},
                {RPCResult::Type::NUM_TIME, "mintime", "The minimum timestamp appropriate for the next block time, expressed in " + UNIX_EPOCH_TIME + ". Adjusted for the proposed BIP94 timewarp rule."},
                {RPCResult::Type::ARR, "mutable", "list of ways the block template may be changed",
                {
                    {RPCResult::Type::STR, "value", "A way the block template may be changed, e.g. 'time', 'transactions', 'prevblock'"},
                }},
                {RPCResult::Type::STR_HEX, "noncerange", "A range of valid nonces"},
                {RPCResult::Type::NUM, "sigoplimit", "limit of sigops in blocks"},
                {RPCResult::Type::NUM, "sizelimit", "limit of block size"},
                {RPCResult::Type::NUM, "weightlimit", /*optional=*/true, "limit of block weight"},
                {RPCResult::Type::NUM_TIME, "curtime", "current timestamp in " + UNIX_EPOCH_TIME + ". Adjusted for the proposed BIP94 timewarp rule."},
                {RPCResult::Type::STR, "bits", "compressed target of next block"},
                {RPCResult::Type::NUM, "height", "The height of the next block"},
                {RPCResult::Type::STR_HEX, "signet_challenge", /*optional=*/true, "Only on signet"},
                {RPCResult::Type::STR_HEX, "default_witness_commitment", /*optional=*/true, "a valid witness commitment for the unmodified block template"},
            }},
        },
        RPCExamples{
                    HelpExampleCli("getblocktemplate", "'{\"rules\": [\"segwit\"]}'")
            + HelpExampleRpc("getblocktemplate", "{\"rules\": [\"segwit\"]}")
                },
        [](const RPCMethod& self, const JSONRPCRequest& request) -> UniValue
{
    NodeContext& node = EnsureAnyNodeContext(request.context);
    ChainstateManager& chainman = EnsureChainman(node);
    Mining& miner = EnsureMining(node);

    std::string strMode = "template";
    UniValue lpval = NullUniValue;
    std::set<std::string> setClientRules;
    if (!request.params[0].isNull())
    {
        const UniValue& oparam = request.params[0].get_obj();
        const UniValue& modeval = oparam.find_value("mode");
        if (modeval.isStr())
            strMode = modeval.get_str();
        else if (modeval.isNull())
        {
            /* Do nothing */
        }
        else
            throw JSONRPCError(RPC_INVALID_PARAMETER, "Invalid mode");
        lpval = oparam.find_value("longpollid");

        if (strMode == "proposal")
        {
            const UniValue& dataval = oparam.find_value("data");
            if (!dataval.isStr())
                throw JSONRPCError(RPC_TYPE_ERROR, "Missing data String key for proposal");

            CBlock block;
            if (!DecodeHexBlk(block, dataval.get_str()))
                throw JSONRPCError(RPC_DESERIALIZATION_ERROR, "Block decode failed");

            uint256 hash = block.GetHash();
            LOCK(cs_main);
            const CBlockIndex* pindex = chainman.m_blockman.LookupBlockIndex(hash);
            if (pindex) {
                if (pindex->IsValid(BLOCK_VALID_SCRIPTS))
                    return "duplicate";
                if (pindex->nStatus & BLOCK_FAILED_VALID)
                    return "duplicate-invalid";
                return "duplicate-inconclusive";
            }

            return BIP22ValidationResult(TestBlockValidity(chainman.ActiveChainstate(), block, /*check_pow=*/false, /*check_merkle_root=*/true));
        }

        const UniValue& aClientRules = oparam.find_value("rules");
        if (aClientRules.isArray()) {
            for (unsigned int i = 0; i < aClientRules.size(); ++i) {
                const UniValue& v = aClientRules[i];
                setClientRules.insert(v.get_str());
            }
        }
    }

    if (strMode != "template")
        throw JSONRPCError(RPC_INVALID_PARAMETER, "Invalid mode");

    if (!miner.isTestChain()) {
        const CConnman& connman = EnsureConnman(node);
        if (connman.GetNodeCount(ConnectionDirection::Both) == 0) {
            throw JSONRPCError(RPC_CLIENT_NOT_CONNECTED, CLIENT_NAME " is not connected!");
        }

        if (miner.isInitialBlockDownload()) {
            throw JSONRPCError(RPC_CLIENT_IN_INITIAL_DOWNLOAD, CLIENT_NAME " is in initial sync and waiting for blocks...");
        }
    }

    static unsigned int nTransactionsUpdatedLast;
    const CTxMemPool& mempool = EnsureMemPool(node);

    WAIT_LOCK(cs_main, cs_main_lock);
    uint256 tip{CHECK_NONFATAL(miner.getTip()).value().hash};

    // Long Polling (BIP22)
    if (!lpval.isNull()) {
        /**
         * Wait to respond until either the best block changes, OR there are more
         * transactions.
         *
         * The check for new transactions first happens after 1 minute and
         * subsequently every 10 seconds. BIP22 does not require this particular interval.
         * On mainnet the mempool changes frequently enough that in practice this RPC
         * returns after 60 seconds, or sooner if the best block changes.
         *
         * getblocktemplate is unlikely to be called by bitcoin-cli, so
         * -rpcclienttimeout is not a concern. BIP22 recommends a long request timeout.
         *
         * The longpollid is assumed to be a tip hash if it has the right format.
         */
        uint256 hashWatchedChain;
        unsigned int nTransactionsUpdatedLastLP;

        if (lpval.isStr())
        {
            // Format: <hashBestChain><nTransactionsUpdatedLast>
            const std::string& lpstr = lpval.get_str();

            // Assume the longpollid is a block hash. If it's not then we return
            // early below.
            hashWatchedChain = ParseHashV(lpstr.substr(0, 64), "longpollid");
            nTransactionsUpdatedLastLP = LocaleIndependentAtoi<int64_t>(lpstr.substr(64));
        }
        else
        {
            // NOTE: Spec does not specify behaviour for non-string longpollid, but this makes testing easier
            hashWatchedChain = tip;
            nTransactionsUpdatedLastLP = nTransactionsUpdatedLast;
        }

        // Release lock while waiting
        {
            REVERSE_LOCK(cs_main_lock, cs_main);
            MillisecondsDouble checktxtime{std::chrono::minutes(1)};
            while (IsRPCRunning()) {
                // If hashWatchedChain is not a real block hash, this will
                // return immediately.
                std::optional<BlockRef> maybe_tip{miner.waitTipChanged(hashWatchedChain, checktxtime)};
                // Node is shutting down
                if (!maybe_tip) break;
                tip = maybe_tip->hash;
                if (tip != hashWatchedChain) break;

                // Check transactions for update without holding the mempool
                // lock to avoid deadlocks.
                if (mempool.GetTransactionsUpdated() != nTransactionsUpdatedLastLP) {
                    break;
                }
                checktxtime = std::chrono::seconds(10);
            }
        }
        tip = CHECK_NONFATAL(miner.getTip()).value().hash;

        if (!IsRPCRunning())
            throw JSONRPCError(RPC_CLIENT_NOT_CONNECTED, "Shutting down");
        // TODO: Maybe recheck connections/IBD and (if something wrong) send an expires-immediately template to stop miners?
    }

    const Consensus::Params& consensusParams = chainman.GetParams().GetConsensus();

    // GBT must be called with 'signet' set in the rules for signet chains
    if (consensusParams.signet_blocks && !setClientRules.contains("signet")) {
        throw JSONRPCError(RPC_INVALID_PARAMETER, "getblocktemplate must be called with the signet rule set (call with {\"rules\": [\"segwit\", \"signet\"]})");
    }

    // GBT must be called with 'segwit' set in the rules
    if (!setClientRules.contains("segwit")) {
        throw JSONRPCError(RPC_INVALID_PARAMETER, "getblocktemplate must be called with the segwit rule set (call with {\"rules\": [\"segwit\"]})");
    }

    // Update block
    static CBlockIndex* pindexPrev;
    static int64_t time_start;
    static std::unique_ptr<BlockTemplate> block_template;
    if (!pindexPrev || pindexPrev->GetBlockHash() != tip ||
        (mempool.GetTransactionsUpdated() != nTransactionsUpdatedLast && GetTime() - time_start > 5))
    {
        // Clear pindexPrev so future calls make a new block, despite any failures from here on
        pindexPrev = nullptr;

        // Store the pindexBest used before createNewBlock, to avoid races
        nTransactionsUpdatedLast = mempool.GetTransactionsUpdated();
        CBlockIndex* pindexPrevNew = chainman.m_blockman.LookupBlockIndex(tip);
        time_start = GetTime();

        // Create new block. Opt-out of cooldown mechanism, because it would add
        // a delay to each getblocktemplate call. This differs from typical
        // long-lived IPC usage, where the overhead is paid only when creating
        // the initial template.
        block_template = miner.createNewBlock({ .coinbase_output_script = g_progpow_coinbase_script }, /*cooldown=*/false);
        CHECK_NONFATAL(block_template);


        // Need to update only after we know createNewBlock succeeded
        pindexPrev = pindexPrevNew;
    }
    CHECK_NONFATAL(pindexPrev);
    CBlock block{block_template->getBlock()};

    // Update nTime
    UpdateTime(&block, consensusParams, pindexPrev);
    block.nNonce64 = 0;
    block.mix_hash.SetNull();

    // NOTE: If at some point we support pre-segwit miners post-segwit-activation, this needs to take segwit support into consideration
    const bool fPreSegWit = !DeploymentActiveAfter(pindexPrev, chainman, Consensus::DEPLOYMENT_SEGWIT);

    UniValue aCaps(UniValue::VARR); aCaps.push_back("proposal");

    UniValue transactions(UniValue::VARR);
    std::map<Txid, int64_t> setTxIndex;
    std::vector<CAmount> tx_fees{block_template->getTxFees()};
    std::vector<int64_t> tx_sigops{block_template->getTxSigops()};

    int i = 0;
    for (const auto& it : block.vtx) {
        const CTransaction& tx = *it;
        Txid txHash = tx.GetHash();
        setTxIndex[txHash] = i++;

        if (tx.IsCoinBase())
            continue;

        UniValue entry(UniValue::VOBJ);

        entry.pushKV("data", EncodeHexTx(tx));
        entry.pushKV("txid", txHash.GetHex());
        entry.pushKV("hash", tx.GetWitnessHash().GetHex());

        UniValue deps(UniValue::VARR);
        for (const CTxIn &in : tx.vin)
        {
            if (setTxIndex.contains(in.prevout.hash))
                deps.push_back(setTxIndex[in.prevout.hash]);
        }
        entry.pushKV("depends", std::move(deps));

        int index_in_template = i - 2;
        entry.pushKV("fee", tx_fees.at(index_in_template));
        int64_t nTxSigOps{tx_sigops.at(index_in_template)};
        if (fPreSegWit) {
            CHECK_NONFATAL(nTxSigOps % WITNESS_SCALE_FACTOR == 0);
            nTxSigOps /= WITNESS_SCALE_FACTOR;
        }
        entry.pushKV("sigops", nTxSigOps);
        entry.pushKV("weight", GetTransactionWeight(tx));

        transactions.push_back(std::move(entry));
    }

    UniValue aux(UniValue::VOBJ);

    arith_uint256 hashTarget = arith_uint256().SetCompact(block.nBits);

    UniValue aMutable(UniValue::VARR);
    aMutable.push_back("time");
    aMutable.push_back("transactions");
    aMutable.push_back("prevblock");

    UniValue result(UniValue::VOBJ);
    result.pushKV("capabilities", std::move(aCaps));

    UniValue aRules(UniValue::VARR);
    // See getblocktemplate changes in BIP 9:
    // ! indicates a more subtle change to the block structure or generation transaction
    // Otherwise clients may assume the rule will not impact usage of the template as-is.
    aRules.push_back("csv");
    if (!fPreSegWit) {
        aRules.push_back("!segwit");
        aRules.push_back("taproot");
    }
    if (consensusParams.signet_blocks) {
        // indicate to miner that they must understand signet rules
        // when attempting to mine with this template
        aRules.push_back("!signet");
    }

    UniValue vbavailable(UniValue::VOBJ);
    const auto gbtstatus = chainman.m_versionbitscache.GBTStatus(*pindexPrev, consensusParams);

    for (const auto& [name, info] : gbtstatus.signalling) {
        vbavailable.pushKV(gbt_rule_value(name, info.gbt_optional_rule), info.bit);
        if (!info.gbt_optional_rule && !setClientRules.contains(name)) {
            // If the client doesn't support this, don't indicate it in the [default] version
            block.nVersion &= ~info.mask;
        }
    }

    for (const auto& [name, info] : gbtstatus.locked_in) {
        block.nVersion |= info.mask;
        vbavailable.pushKV(gbt_rule_value(name, info.gbt_optional_rule), info.bit);
        if (!info.gbt_optional_rule && !setClientRules.contains(name)) {
            // If the client doesn't support this, don't indicate it in the [default] version
            block.nVersion &= ~info.mask;
        }
    }

    for (const auto& [name, info] : gbtstatus.active) {
        aRules.push_back(gbt_rule_value(name, info.gbt_optional_rule));
        if (!info.gbt_optional_rule && !setClientRules.contains(name)) {
            // Not supported by the client; make sure it's safe to proceed
            throw JSONRPCError(RPC_INVALID_PARAMETER, strprintf("Support for '%s' rule requires explicit client support", name));
        }
    }

    result.pushKV("version", block.nVersion);
    result.pushKV("rules", std::move(aRules));
    result.pushKV("vbavailable", std::move(vbavailable));
    result.pushKV("vbrequired", 0);

    result.pushKV("previousblockhash", block.hashPrevBlock.GetHex());
    result.pushKV("transactions", std::move(transactions));
    result.pushKV("coinbaseaux", std::move(aux));
    result.pushKV("coinbasevalue", block.vtx[0]->vout[0].nValue);
    result.pushKV("longpollid", tip.GetHex() + ToString(nTransactionsUpdatedLast));
    result.pushKV("target", hashTarget.GetHex());
    // GPU-mined-crypto / Sharecoin note: the two fields below are what any
    // existing ProgPoW/KawPow-aware GPU miner (T-Rex, kawpowminer, gminer,
    // etc.) actually reads from getblocktemplate to do real GPU mining -
    // named to match the same de facto convention Ravencoin's own KAWPOW
    // fork established (checked directly against Ravencoin's real
    // rpc/mining.cpp, not guessed), so miner software already built for
    // that convention has the best chance of working against this chain
    // with no changes of its own.
    // Real GBT/BIP22 miners normally compute their own merkle root after
    // assembling the final transaction set themselves before submitting -
    // this RPC's own in-memory  never sets hashMerkleRoot for that
    // reason. But pprpcsb below submits this EXACT cached object directly
    // (an RPC-based GPU miner never rebuilds anything itself, it only adds
    // nonce/mix_hash), so it must be set correctly here or the submitted
    // block fails with bad-txnmrklroot despite valid proof-of-work - found
    // by actually testing pprpcsb end-to-end, not assumed.
    block.hashMerkleRoot = BlockMerkleRoot(block);
    result.pushKV("pprpcheader", block.GetPoWHeaderHash().GetHex());
    result.pushKV("pprpcepoch", ethash::get_epoch_number(static_cast<int>(block.nHeight)));
    g_progpow_block_templates[block.GetPoWHeaderHash().GetHex()] = block;
    // Plain, non-reversed hex fields for bridging to Ethereum-style
    // eth_getWork clients (see pow.h's GetEthashNativeWork for why
    // uint256::GetHex() above is the wrong encoding for that use case -
    // this project's own solo-mining bridge script uses these instead).
    {
        const EthashNativeWork native{GetEthashNativeWork(block, block.nBits, consensusParams)};
        result.pushKV("ethash_header_hex", native.header_hex);
        result.pushKV("ethash_boundary_hex", native.boundary_hex);
        result.pushKV("ethash_seed_hex", native.seed_hex);
    }
    result.pushKV("mintime", GetMinimumTime(pindexPrev, consensusParams.DifficultyAdjustmentInterval()));
    result.pushKV("mutable", std::move(aMutable));
    result.pushKV("noncerange", "00000000ffffffff");
    int64_t nSigOpLimit = MAX_BLOCK_SIGOPS_COST;
    int64_t nSizeLimit = MAX_BLOCK_SERIALIZED_SIZE;
    if (fPreSegWit) {
        CHECK_NONFATAL(nSigOpLimit % WITNESS_SCALE_FACTOR == 0);
        nSigOpLimit /= WITNESS_SCALE_FACTOR;
        CHECK_NONFATAL(nSizeLimit % WITNESS_SCALE_FACTOR == 0);
        nSizeLimit /= WITNESS_SCALE_FACTOR;
    }
    result.pushKV("sigoplimit", nSigOpLimit);
    result.pushKV("sizelimit", nSizeLimit);
    if (!fPreSegWit) {
        result.pushKV("weightlimit", MAX_BLOCK_WEIGHT);
    }
    result.pushKV("curtime", block.GetBlockTime());
    result.pushKV("bits", strprintf("%08x", block.nBits));
    result.pushKV("height", pindexPrev->nHeight + 1);

    if (consensusParams.signet_blocks) {
        result.pushKV("signet_challenge", HexStr(consensusParams.signet_challenge));
    }

    if (auto coinbase{block_template->getCoinbaseTx()}; coinbase.required_outputs.size() > 0) {
        CHECK_NONFATAL(coinbase.required_outputs.size() == 1); // Only one output is currently expected
        result.pushKV("default_witness_commitment", HexStr(coinbase.required_outputs[0].scriptPubKey));
    }

    return result;
},
    };
}

class submitblock_StateCatcher final : public CValidationInterface
{
public:
    uint256 hash;
    bool found{false};
    BlockValidationState state;

    explicit submitblock_StateCatcher(const uint256 &hashIn) : hash(hashIn), state() {}

protected:
    void BlockChecked(const std::shared_ptr<const CBlock>& block, const BlockValidationState& stateIn) override
    {
        if (block->GetHash() != hash) return;
        found = true;
        state = stateIn;
    }
};

static RPCMethod submitblock()
{
    // We allow 2 arguments for compliance with BIP22. Argument 2 is ignored.
    return RPCMethod{
        "submitblock",
        "Attempts to submit new block to network.\n"
        "See https://en.bitcoin.it/wiki/BIP_0022 for full specification.\n",
        {
            {"hexdata", RPCArg::Type::STR_HEX, RPCArg::Optional::NO, "the hex-encoded block data to submit"},
            {"dummy", RPCArg::Type::STR, RPCArg::DefaultHint{"ignored"}, "dummy value, for compatibility with BIP22. This value is ignored."},
        },
        {
            RPCResult{"If the block was accepted", RPCResult::Type::NONE, "", ""},
            RPCResult{"Otherwise", RPCResult::Type::STR, "", "According to BIP22"},
        },
        RPCExamples{
                    HelpExampleCli("submitblock", "\"mydata\"")
            + HelpExampleRpc("submitblock", "\"mydata\"")
                },
        [](const RPCMethod& self, const JSONRPCRequest& request) -> UniValue
{
    std::shared_ptr<CBlock> blockptr = std::make_shared<CBlock>();
    CBlock& block = *blockptr;
    if (!DecodeHexBlk(block, request.params[0].get_str())) {
        throw JSONRPCError(RPC_DESERIALIZATION_ERROR, "Block decode failed");
    }

    ChainstateManager& chainman = EnsureAnyChainman(request.context);
    {
        LOCK(cs_main);
        const CBlockIndex* pindex = chainman.m_blockman.LookupBlockIndex(block.hashPrevBlock);
        if (pindex) {
            chainman.UpdateUncommittedBlockStructures(block, pindex);
        }
    }

    bool new_block;
    auto sc = std::make_shared<submitblock_StateCatcher>(block.GetHash());
    CHECK_NONFATAL(chainman.m_options.signals)->RegisterSharedValidationInterface(sc);
    bool accepted = chainman.ProcessNewBlock(blockptr, /*force_processing=*/true, /*min_pow_checked=*/true, /*new_block=*/&new_block);
    CHECK_NONFATAL(chainman.m_options.signals)->UnregisterSharedValidationInterface(sc);
    if (!new_block && accepted) {
        return "duplicate";
    }
    if (!sc->found) {
        return "inconclusive";
    }
    return BIP22ValidationResult(sc->state);
},
    };
}

namespace {
// Parses a hex-encoded 64-bit nonce (an optional 0x/0X prefix is accepted,
// matching how GPU miner software commonly reports it) - modern Bitcoin
// Core has no equivalent of the old ParseUInt64 helper Ravencoin's version
// of this RPC used, so this is a small local replacement using <charconv>
// rather than locale-sensitive strtoull.
bool ParseHexNonce(std::string_view str, uint64_t& out)
{
    if (str.size() > 2 && str[0] == '0' && (str[1] == 'x' || str[1] == 'X')) {
        str.remove_prefix(2);
    }
    if (str.empty()) return false;
    const auto* first = str.data();
    const auto* last = str.data() + str.size();
    auto [ptr, ec] = std::from_chars(first, last, out, 16);
    return ec == std::errc() && ptr == last;
}
} // namespace

static RPCMethod pprpcsb()
{
    return RPCMethod{
        "pprpcsb",
        "Attempts to submit a new block to the network, mined by a ProgPoW/KawPow GPU miner via RPC.\n"
        "Looks up the cached block template by header_hash (the \"pprpcheader\" value a prior "
        "getblocktemplate call returned), applies the miner's found nonce/mix_hash, and submits the "
        "resulting block - mirrors Ravencoin's own pprpcsb RPC (same name, same argument order) so "
        "GPU miner software already built for that convention needs no changes to work here.\n",
        {
            {"header_hash", RPCArg::Type::STR_HEX, RPCArg::Optional::NO, "the pprpcheader value returned by getblocktemplate"},
            {"mix_hash", RPCArg::Type::STR_HEX, RPCArg::Optional::NO, "the mix hash found by the GPU miner"},
            {"nonce", RPCArg::Type::STR, RPCArg::Optional::NO, "the hex-encoded nonce found by the GPU miner"},
        },
        RPCResult{
            RPCResult::Type::STR, "", "\"duplicate\", \"inconclusive\", or per BIP22"},
        RPCExamples{
                    HelpExampleCli("pprpcsb", "\"headerhash\" \"mixhash\" \"1a2b3c\"")
            + HelpExampleRpc("pprpcsb", "\"headerhash\" \"mixhash\" \"1a2b3c\"")
                },
        [](const RPCMethod& self, const JSONRPCRequest& request) -> UniValue
{
    const std::string header_hash{request.params[0].get_str()};
    const uint256 mix_hash{ParseHashV(request.params[1], "mix_hash")};
    uint64_t nonce;
    if (!ParseHexNonce(request.params[2].get_str(), nonce)) {
        throw JSONRPCError(RPC_INVALID_PARAMETER, "Invalid hex nonce");
    }

    const auto it = g_progpow_block_templates.find(header_hash);
    if (it == g_progpow_block_templates.end()) {
        throw JSONRPCError(RPC_INVALID_PARAMETER, "Block header hash not found in cached templates - "
                                                   "call getblocktemplate again to get a fresh one");
    }

    auto blockptr = std::make_shared<CBlock>(it->second);
    blockptr->nNonce64 = nonce;
    blockptr->mix_hash = mix_hash;

    if (blockptr->vtx.empty() || !blockptr->vtx[0]->IsCoinBase()) {
        throw JSONRPCError(RPC_DESERIALIZATION_ERROR, "Cached template does not start with a coinbase");
    }

    ChainstateManager& chainman = EnsureAnyChainman(request.context);
    {
        LOCK(cs_main);
        const CBlockIndex* pindex = chainman.m_blockman.LookupBlockIndex(blockptr->hashPrevBlock);
        if (pindex) {
            chainman.UpdateUncommittedBlockStructures(*blockptr, pindex);
        }
    }

    bool new_block;
    auto sc = std::make_shared<submitblock_StateCatcher>(blockptr->GetHash());
    CHECK_NONFATAL(chainman.m_options.signals)->RegisterSharedValidationInterface(sc);
    bool accepted = chainman.ProcessNewBlock(blockptr, /*force_processing=*/true, /*min_pow_checked=*/true, /*new_block=*/&new_block);
    CHECK_NONFATAL(chainman.m_options.signals)->UnregisterSharedValidationInterface(sc);
    if (!new_block && accepted) {
        return "duplicate";
    }
    if (!sc->found) {
        return "inconclusive";
    }
    return BIP22ValidationResult(sc->state);
},
    };
}

static RPCMethod getrandombeacon()
{
    return RPCMethod{
        "getrandombeacon",
        "Returns a combined randomness value derived from the ProgPoW mix_hash of "
        "window_size consecutive blocks starting at start_height, only once every block "
        "in that window is already confirmed on the active chain.\n"
        "\n"
        "Combining several blocks' mix_hash values (rather than using a single block's "
        "own mix_hash) mitigates the \"last revealer\" bias: a miner who finds a block "
        "sees its mix_hash before deciding whether to broadcast it, and could otherwise "
        "freely withhold and retry until they get one they prefer. Biasing this combined "
        "value requires controlling multiple CONSECUTIVE blocks in the window - to do so, "
        "an attacker must forfeit a real, already-earned block reward and race being "
        "orphaned by someone else's competing block, for a bounded, quantifiable amount of "
        "influence (one bit per block they control in the window), not full control of the "
        "outcome. This does not eliminate bias entirely (see this project's own README/notes) "
        "but bounds it to a small, known amount that shrinks as window_size grows.\n",
        {
            {"start_height", RPCArg::Type::NUM, RPCArg::Optional::NO, "the first block height in the combination window"},
            {"window_size", RPCArg::Type::NUM, RPCArg::Default{100}, "how many consecutive blocks' mix_hash values to combine (1-10000)"},
        },
        RPCResult{
            RPCResult::Type::OBJ, "", "",
            {
                {RPCResult::Type::NUM, "start_height", "the first block height in the window"},
                {RPCResult::Type::NUM, "end_height", "the last block height in the window"},
                {RPCResult::Type::NUM, "window_size", "the number of blocks combined"},
                {RPCResult::Type::STR_HEX, "beacon", "the combined randomness value"},
            }},
        RPCExamples{
                    HelpExampleCli("getrandombeacon", "1000")
            + HelpExampleCli("getrandombeacon", "1000 250")
            + HelpExampleRpc("getrandombeacon", "1000")
                },
        [](const RPCMethod& self, const JSONRPCRequest& request) -> UniValue
{
    const int start_height{request.params[0].getInt<int>()};
    const int window_size{self.Arg<int>("window_size")};

    if (start_height < 0) {
        throw JSONRPCError(RPC_INVALID_PARAMETER, "start_height must be non-negative");
    }
    if (window_size < 1 || window_size > 10000) {
        throw JSONRPCError(RPC_INVALID_PARAMETER, "window_size must be between 1 and 10000");
    }

    const int end_height{start_height + window_size - 1};

    ChainstateManager& chainman = EnsureAnyChainman(request.context);
    LOCK(cs_main);
    const CChain& active_chain = chainman.ActiveChain();
    const int tip_height{active_chain.Height()};

    if (end_height > tip_height) {
        const int blocks_needed{end_height - tip_height};
        throw JSONRPCError(RPC_INVALID_PARAMETER,
            strprintf("Beacon window not yet fully confirmed: needs %d more block(s) "
                      "(window is [%d, %d], chain tip is at height %d)",
                      blocks_needed, start_height, end_height, tip_height));
    }

    HashWriter hw{};
    for (int h = start_height; h <= end_height; ++h) {
        const CBlockIndex* pindex = active_chain[h];
        CHECK_NONFATAL(pindex);
        hw << pindex->mix_hash;
    }
    const uint256 beacon{hw.GetHash()};

    UniValue ret(UniValue::VOBJ);
    ret.pushKV("start_height", start_height);
    ret.pushKV("end_height", end_height);
    ret.pushKV("window_size", window_size);
    ret.pushKV("beacon", beacon.GetHex());
    return ret;
},
    };
}

static RPCMethod getkawpowhash()
{
    return RPCMethod{
        "getkawpowhash",
        "Computes the ProgPoW/KawPow hash for the given header hash, nonce, and height, and reports "
        "whether it matches a candidate mix hash and (optionally) whether it meets a target - a "
        "read-only, local verification helper for pool/miner software, independent of chain state. "
        "Mirrors Ravencoin's own getkawpowhash RPC (same name, same argument order) for compatibility.\n",
        {
            {"header_hash", RPCArg::Type::STR_HEX, RPCArg::Optional::NO, "the ProgPoW header hash that was given to the GPU miner"},
            {"mix_hash", RPCArg::Type::STR_HEX, RPCArg::Optional::NO, "the mix hash reported by the GPU miner, to check against"},
            {"nonce", RPCArg::Type::STR, RPCArg::Optional::NO, "the hex-encoded nonce reported by the GPU miner"},
            {"height", RPCArg::Type::NUM, RPCArg::Optional::NO, "the block height being hashed (selects the DAG epoch)"},
            {"target", RPCArg::Type::STR_HEX, RPCArg::Optional::OMITTED, "optional target to also check the result against"},
        },
        RPCResult{
            RPCResult::Type::OBJ, "", "",
            {
                {RPCResult::Type::STR_HEX, "digest", "the resulting final hash"},
                {RPCResult::Type::STR_HEX, "mix_hash", "the resulting mix hash"},
                {RPCResult::Type::BOOL, "result", "whether the computed mix hash matches the supplied mix_hash"},
                {RPCResult::Type::BOOL, "meets_target", /*optional=*/true, "whether digest meets the supplied target (only present if target was given)"},
            }},
        RPCExamples{
                    HelpExampleCli("getkawpowhash", "\"headerhash\" \"mixhash\" \"1a2b3c\" 2456")
            + HelpExampleRpc("getkawpowhash", "\"headerhash\" \"mixhash\" \"1a2b3c\" 2456")
                },
        [](const RPCMethod& self, const JSONRPCRequest& request) -> UniValue
{
    const uint256 header_hash{ParseHashV(request.params[0], "header_hash")};
    const uint256 candidate_mix_hash{ParseHashV(request.params[1], "mix_hash")};
    uint64_t nonce;
    if (!ParseHexNonce(request.params[2].get_str(), nonce)) {
        throw JSONRPCError(RPC_INVALID_PARAMETER, "Invalid hex nonce");
    }
    const int height{request.params[3].getInt<int>()};

    const bool has_target{!request.params[4].isNull()};
    const uint256 target{has_target ? ParseHashV(request.params[4], "target") : uint256()};

    const ProgPowHashCheckResult result{CheckProgPowHash(height, header_hash, nonce, candidate_mix_hash,
                                                          has_target ? &target : nullptr)};

    UniValue ret(UniValue::VOBJ);
    ret.pushKV("digest", result.final_hash.GetHex());
    ret.pushKV("mix_hash", result.computed_mix_hash.GetHex());
    ret.pushKV("result", result.mix_hash_matches);
    if (result.has_target_check) {
        ret.pushKV("meets_target", result.meets_target);
    }
    return ret;
},
    };
}

static RPCMethod setprogpowminingaddress()
{
    return RPCMethod{
        "setprogpowminingaddress",
        "Sets the coinbase payout address used by getblocktemplate's internally-built block "
        "(and therefore by pprpcsb, which submits that same cached block unmodified). Needed "
        "because, unlike a real BIP22 pool, pprpcsb never lets the external GPU miner rebuild "
        "the coinbase itself - without this the payout script defaults to empty/anyone-can-spend.\n",
        {
            {"address", RPCArg::Type::STR, RPCArg::Optional::NO, "the address to pay future block rewards to"},
        },
        RPCResult{
            RPCResult::Type::NONE, "", "None"},
        RPCExamples{
                    HelpExampleCli("setprogpowminingaddress", "\"address\"")
            + HelpExampleRpc("setprogpowminingaddress", "\"address\"")
                },
        [](const RPCMethod& self, const JSONRPCRequest& request) -> UniValue
{
    const CTxDestination destination{DecodeDestination(request.params[0].get_str())};
    if (!IsValidDestination(destination)) {
        throw JSONRPCError(RPC_INVALID_ADDRESS_OR_KEY, "Invalid address");
    }
    g_progpow_coinbase_script = GetScriptForDestination(destination);
    return UniValue::VNULL;
},
    };
}

static RPCMethod submitheader()
{
    return RPCMethod{
        "submitheader",
        "Decode the given hexdata as a header and submit it as a candidate chain tip if valid."
                "\nThrows when the header is invalid.\n",
                {
                    {"hexdata", RPCArg::Type::STR_HEX, RPCArg::Optional::NO, "the hex-encoded block header data"},
                },
                RPCResult{
                    RPCResult::Type::NONE, "", "None"},
                RPCExamples{
                    HelpExampleCli("submitheader", "\"aabbcc\"") +
                    HelpExampleRpc("submitheader", "\"aabbcc\"")
                },
        [](const RPCMethod& self, const JSONRPCRequest& request) -> UniValue
{
    CBlockHeader h;
    if (!DecodeHexBlockHeader(h, request.params[0].get_str())) {
        throw JSONRPCError(RPC_DESERIALIZATION_ERROR, "Block header decode failed");
    }
    ChainstateManager& chainman = EnsureAnyChainman(request.context);
    {
        LOCK(cs_main);
        if (!chainman.m_blockman.LookupBlockIndex(h.hashPrevBlock)) {
            throw JSONRPCError(RPC_VERIFY_ERROR, "Must submit previous header (" + h.hashPrevBlock.GetHex() + ") first");
        }
    }

    BlockValidationState state;
    chainman.ProcessNewBlockHeaders({{h}}, /*min_pow_checked=*/true, state);
    if (state.IsValid()) return UniValue::VNULL;
    if (state.IsError()) {
        throw JSONRPCError(RPC_VERIFY_ERROR, state.ToString());
    }
    throw JSONRPCError(RPC_VERIFY_ERROR, state.GetRejectReason());
},
    };
}

void RegisterMiningRPCCommands(CRPCTable& t)
{
    static const CRPCCommand commands[]{
        {"mining", &getnetworkhashps},
        {"mining", &getmininginfo},
        {"mining", &prioritisetransaction},
        {"mining", &getprioritisedtransactions},
        {"mining", &getblocktemplate},
        {"mining", &submitblock},
        {"mining", &pprpcsb},
        {"mining", &getkawpowhash},
        {"mining", &getrandombeacon},
        {"mining", &setprogpowminingaddress},
        {"mining", &submitheader},

        {"hidden", &generatetoaddress},
        {"hidden", &generatetodescriptor},
        {"hidden", &generateblock},
        {"hidden", &generate},
    };
    for (const auto& c : commands) {
        t.appendCommand(c.name, &c);
    }
}

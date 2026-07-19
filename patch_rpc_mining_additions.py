"""
Completes src/rpc/mining.cpp's Sharecoin/ProgPoW changes beyond what
patch_rpc_mining_new_rpcs.py adds (that script adds the pprpcsb/
getkawpowhash RPC method bodies and a ParseHexNonce helper, but on its own
produces code that doesn't even compile - it uses std::from_chars without
<charconv>, and references g_progpow_block_templates/g_progpow_coinbase_script
without ever declaring them). Run this AFTER patch_rpc_mining_new_rpcs.py.

Adds, in order:
  - the missing <charconv> include
  - the ethash.hpp include + g_progpow_block_templates/g_progpow_coinbase_script
    file-scope globals
  - GenerateBlock's manual nonce loop replaced with a MineBlock() call
  - getblocktemplate's internal createNewBlock() call passing
    coinbase_output_script (so pprpcsb-submitted blocks pay out somewhere
    spendable instead of an anyone-can-spend empty script)
  - block.nNonce = 0 -> nNonce64 = 0 + mix_hash.SetNull()
  - getblocktemplate's own result gaining pprpcheader/pprpcepoch/ethash_*_hex
    fields (and computing hashMerkleRoot up front, which real BIP22 miners
    normally do themselves but pprpcsb's cached-template-resubmission model
    needs done here instead - found by testing pprpcsb end-to-end, not
    assumed)
  - the new setprogpowminingaddress RPC
  - registering pprpcsb/getkawpowhash/setprogpowminingaddress in the RPC table
"""
path = 'src/rpc/mining.cpp'
text = open(path).read()

# ---- missing <charconv> include (patch_rpc_mining_new_rpcs.py's
# ParseHexNonce helper uses std::from_chars without it) ----
old_charconv = '''#include <limits>
#include <map>'''
new_charconv = '''#include <limits>
#include <charconv>
#include <map>'''
assert old_charconv in text, 'charconv include anchor not found verbatim'
text = text.replace(old_charconv, new_charconv, 1)

# ---- ethash.hpp include, right after pow.h ----
old_pow_include = '''#include <pow.h>
#include <primitives/block.h>'''
new_pow_include = '''#include <pow.h>
#include <crypto/ethash/include/ethash/ethash.hpp>
#include <primitives/block.h>'''
assert old_pow_include in text, 'pow.h include anchor not found verbatim'
text = text.replace(old_pow_include, new_pow_include, 1)

# ---- the two file-scope globals, in their own anonymous namespace right
# after the include list (namespaces can be reopened, so this doesn't need
# to touch/conflict with any other namespace block elsewhere in the file) ----
old_using = '''using interfaces::BlockRef;'''
new_using = '''namespace {
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

using interfaces::BlockRef;'''
assert old_using in text, 'using-declarations anchor not found verbatim'
text = text.replace(old_using, new_using, 1)

# ---- GenerateBlock's manual nonce loop -> MineBlock() ----
old_genblock = '''    block_out.reset();
    block.hashMerkleRoot = BlockMerkleRoot(block);

    while (max_tries > 0 && block.nNonce < std::numeric_limits<uint32_t>::max() && !CheckProofOfWork(block.GetHash(), block.nBits, chainman.GetConsensus()) && !chainman.m_interrupt) {
        ++block.nNonce;
        --max_tries;
    }
    if (max_tries == 0 || chainman.m_interrupt) {
        return false;
    }
    if (block.nNonce == std::numeric_limits<uint32_t>::max()) {
        return true;
    }
'''
new_genblock = '''    block_out.reset();
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
'''
assert old_genblock in text, 'GenerateBlock nonce loop not found verbatim'
text = text.replace(old_genblock, new_genblock, 1)

# ---- getblocktemplate's own createNewBlock() call: pass coinbase_output_script ----
old_ctb = '''        block_template = miner.createNewBlock({}, /*cooldown=*/false);'''
new_ctb = '''        block_template = miner.createNewBlock({ .coinbase_output_script = g_progpow_coinbase_script }, /*cooldown=*/false);'''
assert text.count(old_ctb) == 1, 'getblocktemplate createNewBlock call not found verbatim (or not unique)'
text = text.replace(old_ctb, new_ctb, 1)

# ---- nonce reset ----
old_reset = '''    block.nNonce = 0;

    // NOTE: If at some point we support pre-segwit miners post-segwit-activation, this needs to take segwit support into consideration'''
new_reset = '''    block.nNonce64 = 0;
    block.mix_hash.SetNull();

    // NOTE: If at some point we support pre-segwit miners post-segwit-activation, this needs to take segwit support into consideration'''
assert old_reset in text, 'nNonce reset not found verbatim'
text = text.replace(old_reset, new_reset, 1)

# ---- getblocktemplate result: new fields ----
old_result = '''    result.pushKV("target", hashTarget.GetHex());
    result.pushKV("mintime", GetMinimumTime(pindexPrev, consensusParams.DifficultyAdjustmentInterval()));'''
new_result = '''    result.pushKV("target", hashTarget.GetHex());
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
    // this RPC's own in-memory block never sets hashMerkleRoot for that
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
    result.pushKV("mintime", GetMinimumTime(pindexPrev, consensusParams.DifficultyAdjustmentInterval()));'''
assert old_result in text, 'getblocktemplate result block not found verbatim'
text = text.replace(old_result, new_result, 1)

# ---- new setprogpowminingaddress RPC (inserted right before submitheader,
# the same anchor patch_rpc_mining_new_rpcs.py's own additions end on) ----
anchor_submitheader = '''static RPCMethod submitheader()
{'''
assert text.count(anchor_submitheader) == 1, 'submitheader anchor not found verbatim (or not unique)'

setprogpowminingaddress_rpc = '''static RPCMethod setprogpowminingaddress()
{
    return RPCMethod{
        "setprogpowminingaddress",
        "Sets the coinbase payout address used by getblocktemplate's internally-built block "
        "(and therefore by pprpcsb, which submits that same cached block unmodified). Needed "
        "because, unlike a real BIP22 pool, pprpcsb never lets the external GPU miner rebuild "
        "the coinbase itself - without this the payout script defaults to empty/anyone-can-spend.\\n",
        {
            {"address", RPCArg::Type::STR, RPCArg::Optional::NO, "the address to pay future block rewards to"},
        },
        RPCResult{
            RPCResult::Type::NONE, "", "None"},
        RPCExamples{
                    HelpExampleCli("setprogpowminingaddress", "\\"address\\"")
            + HelpExampleRpc("setprogpowminingaddress", "\\"address\\"")
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
{'''
text = text.replace(anchor_submitheader, setprogpowminingaddress_rpc, 1)

# ---- register the three new RPCs in the command table ----
old_table = '''        {"mining", &submitblock},
        {"mining", &submitheader},'''
new_table = '''        {"mining", &submitblock},
        {"mining", &pprpcsb},
        {"mining", &getkawpowhash},
        {"mining", &setprogpowminingaddress},
        {"mining", &submitheader},'''
assert old_table in text, 'RPC table registration anchor not found verbatim'
text = text.replace(old_table, new_table, 1)

open(path, 'w').write(text)
print('mining.cpp additions patched OK')

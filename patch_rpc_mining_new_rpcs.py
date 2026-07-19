path = 'src/rpc/mining.cpp'
text = open(path).read()

anchor = '''    return BIP22ValidationResult(sc->state);
},
    };
}

static RPCMethod submitheader()
{'''
assert text.count(anchor) == 1, 'anchor not found verbatim'

new_rpcs = '''    return BIP22ValidationResult(sc->state);
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
        "Attempts to submit a new block to the network, mined by a ProgPoW/KawPow GPU miner via RPC.\\n"
        "Looks up the cached block template by header_hash (the \\"pprpcheader\\" value a prior "
        "getblocktemplate call returned), applies the miner's found nonce/mix_hash, and submits the "
        "resulting block - mirrors Ravencoin's own pprpcsb RPC (same name, same argument order) so "
        "GPU miner software already built for that convention needs no changes to work here.\\n",
        {
            {"header_hash", RPCArg::Type::STR_HEX, RPCArg::Optional::NO, "the pprpcheader value returned by getblocktemplate"},
            {"mix_hash", RPCArg::Type::STR_HEX, RPCArg::Optional::NO, "the mix hash found by the GPU miner"},
            {"nonce", RPCArg::Type::STR, RPCArg::Optional::NO, "the hex-encoded nonce found by the GPU miner"},
        },
        RPCResult{
            RPCResult::Type::STR, "", "\\"duplicate\\", \\"inconclusive\\", or per BIP22"},
        RPCExamples{
                    HelpExampleCli("pprpcsb", "\\"headerhash\\" \\"mixhash\\" \\"1a2b3c\\"")
            + HelpExampleRpc("pprpcsb", "\\"headerhash\\" \\"mixhash\\" \\"1a2b3c\\"")
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

static RPCMethod getkawpowhash()
{
    return RPCMethod{
        "getkawpowhash",
        "Computes the ProgPoW/KawPow hash for the given header hash, nonce, and height, and reports "
        "whether it matches a candidate mix hash and (optionally) whether it meets a target - a "
        "read-only, local verification helper for pool/miner software, independent of chain state. "
        "Mirrors Ravencoin's own getkawpowhash RPC (same name, same argument order) for compatibility.\\n",
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
                    HelpExampleCli("getkawpowhash", "\\"headerhash\\" \\"mixhash\\" \\"1a2b3c\\" 2456")
            + HelpExampleRpc("getkawpowhash", "\\"headerhash\\" \\"mixhash\\" \\"1a2b3c\\" 2456")
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

static RPCMethod submitheader()
{'''

text = text.replace(anchor, new_rpcs, 1)
open(path, 'w').write(text)
print('pprpcsb and getkawpowhash RPC methods added OK')

"""
Adds getrandombeacon to src/rpc/mining.cpp - a K-block-combined randomness
beacon derived from already-mined ProgPoW mix_hash values.

Why: a single block's own mix_hash can't safely be used as "the randomness"
for anything, because whoever mines it sees the value before deciding
whether to broadcast it - a miner who dislikes their own mix_hash (e.g. it
disqualifies them from a lottery) can simply withhold the block and keep
re-mining until they get one they prefer, for free.

Design: beacon(start) = SHA256(mix_hash[start] || mix_hash[start+1] || ...
|| mix_hash[start+window-1]) - only computable/queryable once every block
in that window is already confirmed on the active chain. Biasing this
combined value requires controlling multiple CONSECUTIVE blocks in the
window, not just one - the same "last revealer" tradeoff Ethereum's own
RANDAO accepts (bounded, quantifiable bias that shrinks as window_size
grows, not full control of the outcome). This requires no consensus
changes at all - it's a pure read-only derivation over already-stored,
already-validated CBlockIndex::mix_hash values.

Run this after patch_rpc_mining_new_rpcs.py and patch_rpc_mining_additions.py
(anchors on getkawpowhash, which those scripts add).
"""
path = 'src/rpc/mining.cpp'
text = open(path).read()

old_include = '''#include <crypto/hex_base.h>'''
new_include = '''#include <crypto/hex_base.h>
#include <hash.h>'''
assert old_include in text, 'crypto/hex_base.h include anchor not found verbatim'
text = text.replace(old_include, new_include, 1)

old_charconv = '''#include <limits>
#include <map>'''
new_charconv = '''#include <limits>
#include <map>'''
# (charconv already added by patch_rpc_mining_additions.py - no-op check only)

anchor = 'static RPCMethod getkawpowhash()'
assert text.count(anchor) == 1, 'getkawpowhash anchor not found verbatim (or not unique) - run patch_rpc_mining_new_rpcs.py first'

new_rpc = '''static RPCMethod getrandombeacon()
{
    return RPCMethod{
        "getrandombeacon",
        "Returns a combined randomness value derived from the ProgPoW mix_hash of "
        "window_size consecutive blocks starting at start_height, only once every block "
        "in that window is already confirmed on the active chain.\\n"
        "\\n"
        "Combining several blocks' mix_hash values (rather than using a single block's "
        "own mix_hash) mitigates the \\"last revealer\\" bias: a miner who finds a block "
        "sees its mix_hash before deciding whether to broadcast it, and could otherwise "
        "freely withhold and retry until they get one they prefer. Biasing this combined "
        "value requires controlling multiple CONSECUTIVE blocks in the window - to do so, "
        "an attacker must forfeit a real, already-earned block reward and race being "
        "orphaned by someone else's competing block, for a bounded, quantifiable amount of "
        "influence (one bit per block they control in the window), not full control of the "
        "outcome. This does not eliminate bias entirely but bounds it to a small, known "
        "amount that shrinks as window_size grows.\\n",
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

static RPCMethod getkawpowhash()'''

text = text.replace(anchor, new_rpc, 1)

old_table = '''        {"mining", &getkawpowhash},
        {"mining", &setprogpowminingaddress},'''
new_table = '''        {"mining", &getkawpowhash},
        {"mining", &getrandombeacon},
        {"mining", &setprogpowminingaddress},'''
assert old_table in text, 'RPC table registration anchor not found verbatim'
text = text.replace(old_table, new_table, 1)

open(path, 'w').write(text)
print('getrandombeacon added to mining.cpp OK')

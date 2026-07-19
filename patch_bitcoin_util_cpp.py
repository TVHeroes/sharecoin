"""
Patches src/bitcoin-util.cpp's Grind command - replaces the hand-rolled,
multi-threaded SHA-256d nonce grinder with a single MineBlock() call (the
same real ProgPoW search every other mining path in this codebase uses).
This is what actually mines a genesis block for a network whose genesis
isn't already hardcoded in kernel/chainparams.cpp (see patch_chainparams.py
and README.md's "Known limitations" - only regtest's genesis here is
actually mined this way).

A real, deliberate regression: this drops the multi-threading, so Grind is
single-threaded here where it used to spread across
hardware_concurrency() threads. Accepted on purpose - correctness and
reusing the one real search implementation mattered more than raw grind
throughput for what is fundamentally a genesis/test-header utility, not a
production miner.
"""
path = 'src/bitcoin-util.cpp'
text = open(path).read()

old_include = '''#include <compat/compat.h>
#include <core_io.h>
#include <streams.h>'''
new_include = '''#include <compat/compat.h>
#include <core_io.h>
#include <pow.h>
#include <streams.h>'''
assert old_include in text, 'includes block not found verbatim'
text = text.replace(old_include, new_include, 1)

old_grind = '''static void grind_task(uint32_t nBits, CBlockHeader header, uint32_t offset, uint32_t step, std::atomic<bool>& found, uint32_t& proposed_nonce)
{
    arith_uint256 target;
    bool neg, over;
    target.SetCompact(nBits, &neg, &over);
    if (target == 0 || neg || over) return;
    header.nNonce = offset;

    uint32_t finish = std::numeric_limits<uint32_t>::max() - step;
    finish = finish - (finish % step) + offset;

    while (!found && header.nNonce < finish) {
        const uint32_t next = (finish - header.nNonce < 5000*step) ? finish : header.nNonce + 5000*step;
        do {
            if (UintToArith256(header.GetHash()) <= target) {
                if (!found.exchange(true)) {
                    proposed_nonce = header.nNonce;
                }
                return;
            }
            header.nNonce += step;
        } while(header.nNonce != next);
    }
}

static int Grind(const std::vector<std::string>& args, std::string& strPrint)'''
new_grind = '''// GPU-mined-crypto note: this used to be a hand-rolled multi-threaded
// SHA-256d nonce grinder (grind_task, run across hardware_concurrency()
// threads). Replaced with a single call into MineBlock (pow.cpp) - the
// same real ProgPoW search every other mining path in this codebase uses
// (rpc/mining.cpp's GenerateBlock, node/miner.cpp) - rather than
// reimplementing (and re-parallelizing) the search loop a third time for
// a hash function it no longer even checks against. Single-threaded here
// is a real regression in raw speed for this one CLI tool specifically,
// accepted deliberately: correctness and reuse mattered more than grind
// throughput for what is fundamentally a genesis/test-header utility, not
// a production miner.
static int Grind(const std::vector<std::string>& args, std::string& strPrint)'''
assert old_grind in text, 'grind_task/Grind declaration not found verbatim'
text = text.replace(old_grind, new_grind, 1)

old_body = '''    uint32_t nBits = header.nBits;
    std::atomic<bool> found{false};
    uint32_t proposed_nonce{};

    std::vector<std::thread> threads;
    int n_tasks = std::max(1u, std::thread::hardware_concurrency());
    threads.reserve(n_tasks);
    for (int i = 0; i < n_tasks; ++i) {
        threads.emplace_back(grind_task, nBits, header, i, n_tasks, std::ref(found), std::ref(proposed_nonce));
    }
    for (auto& t : threads) {
        t.join();
    }
    if (found) {
        header.nNonce = proposed_nonce;
    } else {
        strPrint = "Could not satisfy difficulty target";
        return EXIT_FAILURE;
    }'''
new_body = '''    uint64_t max_iterations{std::numeric_limits<uint32_t>::max()};
    if (!MineBlock(header, /*start_nonce=*/0, max_iterations)) {
        strPrint = "Could not satisfy difficulty target";
        return EXIT_FAILURE;
    }'''
assert old_body in text, 'Grind body not found verbatim'
text = text.replace(old_body, new_body, 1)

open(path, 'w').write(text)
print('bitcoin-util.cpp patched OK')

// Copyright (c) 2009-2010 Satoshi Nakamoto
// Copyright (c) 2009-present The Bitcoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include <pow.h>

#include <arith_uint256.h>
#include <chain.h>
#include <crypto/hex_base.h>
#include <primitives/block.h>
#include <uint256.h>
#include <util/check.h>

#include <crypto/ethash/include/ethash/ethash.hpp>
#include <crypto/ethash/include/ethash/progpow.hpp>

#include <cstring>
#include <span>

// GPU-mined-crypto note (see ../NOTES.md): CheckProofOfWorkImpl's hash
// computation (below) is still unmodified upstream logic aside from which
// hash function it checks against the target. GetNextWorkRequired,
// however, now dispatches to LwmaCalculateNextWorkRequired instead of
// upstream's fixed-window CalculateNextWorkRequired (kept below, unused by
// GetNextWorkRequired but left in place since pow_tests.cpp/fuzz/pow.cpp
// still reference it directly) - see consensus/params.h's field comments
// for why.
namespace {

ethash::hash256 ToEthashHash256(const uint256& h)
{
    // Opaque 32-byte copy, no byte-order conversion needed - h is either an
    // input seed (GetPoWHeaderHash()) or a value ProgPoW itself produced
    // and we're just handing back (mix_hash); neither is ever numerically
    // COMPARED outside the ethash/progpow library's own internal logic, so
    // there's nothing that needs reinterpreting, only carrying the same 32
    // bytes across the two libraries' otherwise-unrelated type definitions.
    ethash::hash256 out;
    static_assert(sizeof(out.bytes) == 32);
    std::memcpy(out.bytes, h.data(), 32);
    return out;
}

// Bitcoin's arith_uint256/uint256 store bytes little-endian internally
// (uint256.h: "ArithToUint256() converts the number to a blob in
// little-endian format"). ethash's own boundary comparison
// (is_less_or_equal in ethash-internal.hpp) reads hash256.bytes as
// big-endian/MSB-first (word64s[0] compared first, via a big-endian
// uint64 read). Converting the target to ethash's boundary therefore
// requires reversing the 32 bytes - confirmed both by inspecting each
// library's own source/comments and by an empirical standalone test
// (see NOTES.md) that a target built this way behaves as "smaller
// target = harder" against the real ProgPoW implementation, not
// backwards or orientation-independent by coincidence.
ethash::hash256 TargetToBoundary(const arith_uint256& target)
{
    const uint256 little_endian{ArithToUint256(target)};
    ethash::hash256 out;
    for (int i = 0; i < 32; ++i) {
        out.bytes[i] = little_endian.data()[31 - i];
    }
    return out;
}

} // namespace

unsigned int GetNextWorkRequired(const CBlockIndex* pindexLast, const CBlockHeader *pblock, const Consensus::Params& params)
{
    assert(pindexLast != nullptr);

    if (params.fPowNoRetargeting)
        return pindexLast->nBits;

    // Bootstrap period: not enough history yet for a meaningful weighted
    // average, so hold at genesis's own difficulty until there is. Once
    // past it, LWMA takes over and stays responsive to real hashrate for
    // every block after, not just at fixed-window boundaries.
    if (pindexLast->nHeight + 1 <= params.nLwmaAveragingWindow) {
        return pindexLast->GetAncestor(0)->nBits;
    }

    return LwmaCalculateNextWorkRequired(pindexLast, params);
}

unsigned int LwmaCalculateNextWorkRequired(const CBlockIndex* pindexLast, const Consensus::Params& params)
{
    const int64_t T = params.nPowTargetSpacing;
    const int64_t N = params.nLwmaAveragingWindow;
    const int64_t k = params.nLwmaAdjustedWeight;
    const int64_t dnorm = params.nLwmaMinDenominator;
    const int height = pindexLast->nHeight + 1;
    assert(height > N);

    arith_uint256 sum_target;
    int64_t t = 0, j = 0;

    // Loop through the N most recent blocks, weighting each block's
    // solvetime by its position in the window (j=1 for the oldest block
    // counted, j=N for the most recent) - see consensus/params.h for why.
    for (int i = height - N; i < height; i++) {
        const CBlockIndex* block = pindexLast->GetAncestor(i);
        const CBlockIndex* block_prev = block->GetAncestor(i - 1);
        int64_t solvetime = block->GetBlockTime() - block_prev->GetBlockTime();

        if (params.fLwmaSolvetimeLimitation && solvetime > 6 * T) {
            solvetime = 6 * T;
        }

        j++;
        t += solvetime * j;

        // Target sum divided by (k * N^2) here rather than after the loop,
        // to keep intermediate values well within arith_uint256's range.
        arith_uint256 target;
        target.SetCompact(block->nBits);
        sum_target += target / (k * N * N);
    }

    // Floor t so a run of implausibly-fast solvetimes can't push the next
    // target toward zero.
    int64_t t_min = N * k / dnorm;
    if (t < t_min) {
        t = t_min;
    }

    const arith_uint256 pow_limit = UintToArith256(params.powLimit);
    arith_uint256 next_target = t * sum_target;
    if (next_target > pow_limit) {
        next_target = pow_limit;
    }

    return next_target.GetCompact();
}

unsigned int CalculateNextWorkRequired(const CBlockIndex* pindexLast, int64_t nFirstBlockTime, const Consensus::Params& params)
{
    if (params.fPowNoRetargeting)
        return pindexLast->nBits;

    // Limit adjustment step
    int64_t nActualTimespan = pindexLast->GetBlockTime() - nFirstBlockTime;
    if (nActualTimespan < params.nPowTargetTimespan/4)
        nActualTimespan = params.nPowTargetTimespan/4;
    if (nActualTimespan > params.nPowTargetTimespan*4)
        nActualTimespan = params.nPowTargetTimespan*4;

    // Retarget
    const arith_uint256 bnPowLimit = UintToArith256(params.powLimit);
    arith_uint256 bnNew;

    // Special difficulty rule for Testnet4
    if (params.enforce_BIP94) {
        // Here we use the first block of the difficulty period. This way
        // the real difficulty is always preserved in the first block as
        // it is not allowed to use the min-difficulty exception.
        int nHeightFirst = pindexLast->nHeight - (params.DifficultyAdjustmentInterval()-1);
        const CBlockIndex* pindexFirst = pindexLast->GetAncestor(nHeightFirst);
        bnNew.SetCompact(pindexFirst->nBits);
    } else {
        bnNew.SetCompact(pindexLast->nBits);
    }

    bnNew *= nActualTimespan;
    bnNew /= params.nPowTargetTimespan;

    if (bnNew > bnPowLimit)
        bnNew = bnPowLimit;

    return bnNew.GetCompact();
}

// Check that on difficulty adjustments, the new difficulty does not increase
// or decrease beyond the permitted limits.
bool PermittedDifficultyTransition(const Consensus::Params&, int64_t, uint32_t, uint32_t)
{
    // See this function's declaration comment in pow.h: LWMA changes bits
    // every block, which upstream's fixed-window bounds check (built for
    // Bitcoin's own retargeting) can't correctly express. The real
    // consensus rule lives in validation.cpp via GetNextWorkRequired, not
    // here - this is only a headers-presync fast-path heuristic.
    return true;
}

// Bypasses the actual proof of work check during fuzz testing with a simplified validation checking whether
// the most significant bit of the last byte of the hash is set.
bool CheckProofOfWork(const CBlockHeader& block, unsigned int nBits, const Consensus::Params& params)
{
    if (EnableFuzzDeterminism()) return (block.GetHash().data()[31] & 0x80) == 0;
    return CheckProofOfWorkImpl(block, nBits, params);
}

std::optional<arith_uint256> DeriveTarget(unsigned int nBits, const uint256 pow_limit)
{
    bool fNegative;
    bool fOverflow;
    arith_uint256 bnTarget;

    bnTarget.SetCompact(nBits, &fNegative, &fOverflow);

    // Check range
    if (fNegative || bnTarget == 0 || fOverflow || bnTarget > UintToArith256(pow_limit))
        return {};

    return bnTarget;
}

bool CheckProofOfWorkImpl(const CBlockHeader& block, unsigned int nBits, const Consensus::Params& params)
{
    auto bnTarget{DeriveTarget(nBits, params.powLimit)};
    if (!bnTarget) return false;

    // The actual GPU-favorable, ASIC-resistant proof check - everything
    // above this point (target derivation, range/overflow checks) is
    // unchanged upstream Bitcoin Core logic; only the hash being checked
    // against that target is different.
    const ethash::hash256 boundary{TargetToBoundary(*bnTarget)};
    const ethash::hash256 header_hash{ToEthashHash256(block.GetPoWHeaderHash())};
    const ethash::hash256 mix_hash{ToEthashHash256(block.mix_hash)};
    const int block_number{static_cast<int>(block.nHeight)};
    const ethash::epoch_context& context{ethash::get_global_epoch_context(ethash::get_epoch_number(block_number))};

    return progpow::verify(context, block_number, header_hash, mix_hash, block.nNonce64, boundary);
}

bool MineBlock(CBlockHeader& block, uint64_t start_nonce, uint64_t& max_iterations)
{
    // A miner is trying to find a solution for whatever target the block
    // already declares (block.nBits) - the powLimit passed to DeriveTarget
    // here is intentionally the loosest possible value (all-ones) purely
    // so DeriveTarget's own range/overflow check can never itself be the
    // reason mining fails; the real difficulty is entirely governed by
    // block.nBits, exactly as CheckProofOfWorkImpl above will
    // independently re-derive and enforce when the resulting block is
    // actually validated.
    const uint256 max_pow_limit{ArithToUint256(~arith_uint256(0))};
    auto bnTarget{DeriveTarget(block.nBits, max_pow_limit)};
    if (!bnTarget) {
        max_iterations = 0;
        return false;
    }

    const ethash::hash256 boundary{TargetToBoundary(*bnTarget)};
    const ethash::hash256 header_hash{ToEthashHash256(block.GetPoWHeaderHash())};
    const int block_number{static_cast<int>(block.nHeight)};
    const ethash::epoch_context& context{ethash::get_global_epoch_context(ethash::get_epoch_number(block_number))};

    // search_light (cache-based, not the full DAG) - appropriate for CPU
    // mining paths in this codebase (RPC-driven test/regtest block
    // generation, node/miner.cpp's own fallback) rather than a real GPU
    // miner, which would use the full-DAG search() for speed. Both produce
    // solutions any node's CheckProofOfWork accepts identically - light
    // vs. full is a performance choice, not a validity difference.
    const progpow::search_result result{
        progpow::search_light(context, block_number, header_hash, boundary, start_nonce,
                               static_cast<size_t>(max_iterations))};

    if (!result.solution_found) {
        // The whole budget was tried and none worked.
        max_iterations = 0;
        return false;
    }

    // Only as many nonces as it actually took were consumed, not the full
    // budget - matches the shared-budget semantics the original manual
    // mining loops relied on across repeated GenerateBlock calls.
    const uint64_t consumed = (result.nonce - start_nonce) + 1;
    max_iterations = (consumed < max_iterations) ? (max_iterations - consumed) : 0;

    block.nNonce64 = result.nonce;
    std::memcpy(block.mix_hash.begin(), result.mix_hash.bytes, 32);
    return true;
}

ProgPowHashCheckResult CheckProgPowHash(int height, const uint256& header_hash, uint64_t nonce,
                                         const uint256& candidate_mix_hash,
                                         const uint256* target)
{
    const ethash::hash256 header_hash_eth{ToEthashHash256(header_hash)};
    const ethash::epoch_context& context{ethash::get_global_epoch_context(ethash::get_epoch_number(height))};
    const progpow::result result{progpow::hash(context, height, header_hash_eth, nonce)};

    ProgPowHashCheckResult out;
    std::memcpy(out.final_hash.begin(), result.final_hash.bytes, 32);
    std::memcpy(out.computed_mix_hash.begin(), result.mix_hash.bytes, 32);
    out.mix_hash_matches = (out.computed_mix_hash == candidate_mix_hash);

    out.has_target_check = (target != nullptr);
    out.meets_target = false;
    if (target) {
        const ethash::hash256 boundary{TargetToBoundary(UintToArith256(*target))};
        // Reuses the public progpow::verify() API (already validated in
        // this project's own standalone endianness tests, see NOTES.md)
        // rather than reaching into ethash-internal.hpp's private
        // is_less_or_equal - that header lives under lib/, not include/,
        // and isn't meant to be called from outside the vendored library.
        // Passing this call's own freshly-computed mix hash back in simply
        // re-verifies the result just computed, without duplicating the
        // comparison logic ourselves.
        out.meets_target = progpow::verify(context, height, header_hash_eth, result.mix_hash, nonce, boundary);
    }
    return out;
}

EthashNativeWork GetEthashNativeWork(const CBlockHeader& block, unsigned int nBits, const Consensus::Params& params)
{
    EthashNativeWork out;

    // Plain, non-reversed hex - deliberately NOT uint256::GetHex() (see the
    // declaration comment in pow.h for why that would be wrong here).
    const uint256 header_hash{block.GetPoWHeaderHash()};
    out.header_hex = HexStr(std::span<const uint8_t>(header_hash.begin(), header_hash.size()));

    const auto bnTarget{DeriveTarget(nBits, params.powLimit)};
    if (bnTarget) {
        const ethash::hash256 boundary{TargetToBoundary(*bnTarget)};
        out.boundary_hex = HexStr(std::span<const uint8_t>(boundary.bytes, 32));
    }

    const int epoch_number{ethash::get_epoch_number(static_cast<int>(block.nHeight))};
    const ethash::hash256 seed{ethash::calculate_epoch_seed(epoch_number)};
    out.seed_hex = HexStr(std::span<const uint8_t>(seed.bytes, 32));

    return out;
}

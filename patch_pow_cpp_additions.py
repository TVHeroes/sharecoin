"""
Adds MineBlock(), CheckProgPowHash(), and GetEthashNativeWork() to
src/pow.cpp - the real proof-of-work search function (used by every mining
call site instead of each reimplementing its own nonce loop), the
getkawpowhash RPC's verification helper, and the eth_getWork bridge's
native-hex-encoding helper, respectively.

Run this AFTER patch_pow_cpp.py (which does the CheckProofOfWork/
CheckProofOfWorkImpl rewrite this file's insertion point anchors on) and
alongside patch_pow_h.py (which declares these same functions).
"""
path = 'src/pow.cpp'
text = open(path).read()

old_include = '''#include <arith_uint256.h>
#include <chain.h>
#include <primitives/block.h>
#include <uint256.h>
#include <util/check.h>

#include <crypto/ethash/include/ethash/ethash.hpp>
#include <crypto/ethash/include/ethash/progpow.hpp>

#include <cstring>'''
new_include = '''#include <arith_uint256.h>
#include <chain.h>
#include <crypto/hex_base.h>
#include <primitives/block.h>
#include <uint256.h>
#include <util/check.h>

#include <crypto/ethash/include/ethash/ethash.hpp>
#include <crypto/ethash/include/ethash/progpow.hpp>

#include <cstring>
#include <span>'''

assert old_include in text, 'pow.cpp includes block not found verbatim (run patch_pow_cpp.py first)'
text = text.replace(old_include, new_include, 1)

anchor = '''    return progpow::verify(context, block_number, header_hash, mix_hash, block.nNonce64, boundary);
}'''

additions = '''    return progpow::verify(context, block_number, header_hash, mix_hash, block.nNonce64, boundary);
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
        // this project's own standalone endianness tests) rather than
        // reaching into ethash-internal.hpp's private is_less_or_equal -
        // that header lives under lib/, not include/, and isn't meant to
        // be called from outside the vendored library. Passing this
        // call's own freshly-computed mix hash back in simply re-verifies
        // the result just computed, without duplicating the comparison
        // logic ourselves.
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
}'''

assert anchor in text, 'CheckProofOfWorkImpl body not found verbatim (run patch_pow_cpp.py first)'
text = text.replace(anchor, additions, 1)

open(path, 'w').write(text)
print('pow.cpp additions patched OK')

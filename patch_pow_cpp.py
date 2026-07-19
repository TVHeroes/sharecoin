path = 'src/pow.cpp'
text = open(path).read()

old_include = '''#include <pow.h>

#include <arith_uint256.h>
#include <chain.h>
#include <primitives/block.h>
#include <uint256.h>
#include <util/check.h>'''

new_include = '''#include <pow.h>

#include <arith_uint256.h>
#include <chain.h>
#include <primitives/block.h>
#include <uint256.h>
#include <util/check.h>

#include <crypto/ethash/include/ethash/ethash.hpp>
#include <crypto/ethash/include/ethash/progpow.hpp>

#include <cstring>

// GPU-mined-crypto note (see ../NOTES.md): the ONLY change in this file is
// how CheckProofOfWorkImpl computes the hash it checks against the target -
// GetNextWorkRequired/CalculateNextWorkRequired/PermittedDifficultyTransition
// below are completely unmodified from upstream Bitcoin Core, since the
// retargeting math only ever manipulates nBits/arith_uint256 targets and
// doesn't care what hash function produced the block. This is deliberate:
// reuse everything that isn't the actual mining algorithm.
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

} // namespace'''

assert old_include in text, 'pow.cpp includes block not found verbatim'
text = text.replace(old_include, new_include, 1)

old_check = '''// Bypasses the actual proof of work check during fuzz testing with a simplified validation checking whether
// the most significant bit of the last byte of the hash is set.
bool CheckProofOfWork(uint256 hash, unsigned int nBits, const Consensus::Params& params)
{
    if (EnableFuzzDeterminism()) return (hash.data()[31] & 0x80) == 0;
    return CheckProofOfWorkImpl(hash, nBits, params);
}'''

new_check = '''// Bypasses the actual proof of work check during fuzz testing with a simplified validation checking whether
// the most significant bit of the last byte of the hash is set.
bool CheckProofOfWork(const CBlockHeader& block, unsigned int nBits, const Consensus::Params& params)
{
    if (EnableFuzzDeterminism()) return (block.GetHash().data()[31] & 0x80) == 0;
    return CheckProofOfWorkImpl(block, nBits, params);
}'''

assert old_check in text, 'CheckProofOfWork body not found verbatim'
text = text.replace(old_check, new_check, 1)

old_impl = '''bool CheckProofOfWorkImpl(uint256 hash, unsigned int nBits, const Consensus::Params& params)
{
    auto bnTarget{DeriveTarget(nBits, params.powLimit)};
    if (!bnTarget) return false;

    // Check proof of work matches claimed amount
    if (UintToArith256(hash) > bnTarget)
        return false;

    return true;
}'''

new_impl = '''bool CheckProofOfWorkImpl(const CBlockHeader& block, unsigned int nBits, const Consensus::Params& params)
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
}'''

assert old_impl in text, 'CheckProofOfWorkImpl body not found verbatim'
text = text.replace(old_impl, new_impl, 1)

open(path, 'w').write(text)
print('pow.cpp patched OK')

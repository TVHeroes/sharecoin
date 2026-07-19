"""
Patches src/pow.h - declarations for the new proof-of-work functions whose
bodies patch_pow_cpp.py and patch_pow_cpp_additions.py add to pow.cpp.
Apply after patch_pow_cpp.py (order doesn't matter relative to it, but
run both before building).
"""
path = 'src/pow.h'
text = open(path).read()

old_include = '''#include <consensus/params.h>

#include <cstdint>'''
new_include = '''#include <consensus/params.h>

#include <cstdint>
#include <string>'''

assert old_include in text, 'pow.h includes block not found verbatim'
text = text.replace(old_include, new_include, 1)

old_decls = '''/** Check whether a block hash satisfies the proof-of-work requirement specified by nBits */
bool CheckProofOfWork(uint256 hash, unsigned int nBits, const Consensus::Params&);
bool CheckProofOfWorkImpl(uint256 hash, unsigned int nBits, const Consensus::Params&);'''

new_decls = '''/** Check whether a block satisfies the proof-of-work requirement specified by nBits.
 * GPU-mined-crypto note: takes the full CBlockHeader, not just a precomputed
 * hash, because the actual proof-of-work hash (ProgPoW, see pow.cpp) needs
 * the header's nHeight/nNonce64/mix_hash fields, not just its identity hash
 * (CBlockHeader::GetHash(), used for indexing/chain-linkage, is unrelated -
 * see the class-level comment in primitives/block.h). */
bool CheckProofOfWork(const CBlockHeader& block, unsigned int nBits, const Consensus::Params&);
bool CheckProofOfWorkImpl(const CBlockHeader& block, unsigned int nBits, const Consensus::Params&);

/** Searches for a valid nonce for block (whose nHeight/nBits/hashPrevBlock/
 * hashMerkleRoot/etc. must already be set), trying nonces starting at
 * start_nonce. max_iterations is BOTH the input try-budget and an output:
 * it is decremented by however many nonces were actually tried (matching
 * the original manual mining loops' own semantics, where the same budget
 * is shared and depleted across repeated calls generating multiple
 * blocks) - not simply zeroed, since a caller generating several blocks in
 * one RPC call needs to know how much budget is left for the next one. On
 * success, sets block.nNonce64 and block.mix_hash to the found solution
 * and returns true - the only real proof-of-work search logic in this
 * codebase, used by both rpc/mining.cpp's GenerateBlock and
 * node/miner.cpp, rather than duplicating the ProgPoW/ethash plumbing at
 * each call site. */
bool MineBlock(CBlockHeader& block, uint64_t start_nonce, uint64_t& max_iterations);

/** Result of an independent ProgPoW hash check - used by the getkawpowhash
 * RPC (a read-only verification helper for pool/miner software, mirroring
 * Ravencoin's own RPC of the same name for compatibility). Keeps every
 * ethash/progpow type private to pow.cpp - callers only ever see uint256/
 * bool, the same boundary this file already keeps elsewhere. */
struct ProgPowHashCheckResult {
    uint256 final_hash;
    uint256 computed_mix_hash;
    bool mix_hash_matches;
    bool has_target_check;
    bool meets_target;
};

/** Independently computes the ProgPoW hash for (height, header_hash, nonce),
 * reporting whether the result's mix hash matches candidate_mix_hash and,
 * if target is provided, whether the final hash meets it - reusing the
 * exact same TargetToBoundary conversion CheckProofOfWorkImpl relies on,
 * rather than re-deriving a second, possibly-inconsistent comparison. */
ProgPowHashCheckResult CheckProgPowHash(int height, const uint256& header_hash, uint64_t nonce,
                                         const uint256& candidate_mix_hash,
                                         const uint256* target);

/** Returns (header, boundary, seed) all in ethash-native, PLAIN hex encoding
 * - i.e. a straightforward left-to-right hex string of the same raw bytes
 * progpow::hash/verify actually operate on, NOT Bitcoin's uint256::GetHex(),
 * which deliberately reverses bytes for display (see uint256.h's own
 * documented convention: "unusual, since it shows bytes ... in reverse
 * order", unlike "typical byte-array / hex conversion functions").
 * Ethereum-style getwork clients (eth_getWork, which kawpowminer's simplest
 * connection mode uses) parse hex the plain way - handing them a
 * GetHex()-produced string would silently make them hash something
 * different from what this chain's own validation checks. Used to bridge
 * getblocktemplate's Bitcoin-convention output to an eth_getWork-compatible
 * proxy. */
struct EthashNativeWork {
    std::string header_hex;
    std::string boundary_hex;
    std::string seed_hex;
};
EthashNativeWork GetEthashNativeWork(const CBlockHeader& block, unsigned int nBits, const Consensus::Params& params);'''

assert old_decls in text, 'pow.h proof-of-work declarations not found verbatim'
text = text.replace(old_decls, new_decls, 1)

open(path, 'w').write(text)
print('pow.h patched OK')

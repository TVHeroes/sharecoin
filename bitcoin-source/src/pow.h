// Copyright (c) 2009-2010 Satoshi Nakamoto
// Copyright (c) 2009-present The Bitcoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#ifndef BITCOIN_POW_H
#define BITCOIN_POW_H

#include <consensus/params.h>

#include <cstdint>
#include <string>

class CBlockHeader;
class CBlockIndex;
class uint256;
class arith_uint256;

/**
 * Convert nBits value to target.
 *
 * @param[in] nBits     compact representation of the target
 * @param[in] pow_limit PoW limit (consensus parameter)
 *
 * @return              the proof-of-work target or nullopt if the nBits value
 *                      is invalid (due to overflow or exceeding pow_limit)
 */
std::optional<arith_uint256> DeriveTarget(unsigned int nBits, uint256 pow_limit);

unsigned int GetNextWorkRequired(const CBlockIndex* pindexLast, const CBlockHeader *pblock, const Consensus::Params&);
unsigned int CalculateNextWorkRequired(const CBlockIndex* pindexLast, int64_t nFirstBlockTime, const Consensus::Params&);

/** LWMA (Linearly Weighted Moving Average) retargeting - see the field
 * comments in consensus/params.h for why this fork uses it instead of
 * Bitcoin's fixed-window retargeting. Requires pindexLast->nHeight + 1 to
 * be greater than params.nLwmaAveragingWindow; callers (GetNextWorkRequired)
 * handle the earlier bootstrap period separately. */
unsigned int LwmaCalculateNextWorkRequired(const CBlockIndex* pindexLast, const Consensus::Params& params);

/** Check whether a block satisfies the proof-of-work requirement specified by nBits.
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
EthashNativeWork GetEthashNativeWork(const CBlockHeader& block, unsigned int nBits, const Consensus::Params& params);

/**
 * Return false if the proof-of-work requirement specified by new_nbits at a
 * given height is not possible, given the proof-of-work on the prior block as
 * specified by old_nbits.
 *
 * Upstream, this only checks that the new value is within a factor of 4 of
 * the old value for blocks at the difficulty adjustment interval, and
 * otherwise requires the values to be the same - a bounds check that
 * assumes Bitcoin's fixed-window retargeting (bits only ever change once
 * every DifficultyAdjustmentInterval() blocks). This fork's LWMA
 * retargeting changes bits on every block, which that assumption can't
 * express, so this function always returns true here - it's only ever
 * used as a fast-path sanity heuristic during headers presync
 * (headerssync.cpp), not the actual consensus rule (validation.cpp's
 * ContextualCheckBlockHeader independently recomputes and requires an
 * exact match via GetNextWorkRequired regardless of this function).
 */
bool PermittedDifficultyTransition(const Consensus::Params& params, int64_t height, uint32_t old_nbits, uint32_t new_nbits);

#endif // BITCOIN_POW_H

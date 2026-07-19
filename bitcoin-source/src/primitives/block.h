// Copyright (c) 2009-2010 Satoshi Nakamoto
// Copyright (c) 2009-present The Bitcoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#ifndef BITCOIN_PRIMITIVES_BLOCK_H
#define BITCOIN_PRIMITIVES_BLOCK_H

#include <primitives/transaction.h>
#include <serialize.h>
#include <uint256.h>
#include <util/time.h>

#include <cstdint>
#include <string>
#include <utility>
#include <vector>

/** Nodes collect new transactions into a block, hash them into a hash tree,
 * and scan through nonce values to make the block's hash satisfy proof-of-work
 * requirements.  When they solve the proof-of-work, they broadcast the block
 * to everyone and the block is added to the block chain.  The first transaction
 * in the block is a special one that creates a new coin owned by the creator
 * of the block.
 */
/** GPU-mined-crypto note (see ../../NOTES.md): this project forks Bitcoin
 * Core, reusing essentially all of it unchanged, and swaps ONLY the
 * proof-of-work algorithm used to actually MINE a block - every other
 * SHA-256 use in this codebase (txids, merkle roots, addresses, checksums)
 * is deliberately left untouched, since those are never brute-forced and
 * changing them would not affect which hardware is competitive at mining.
 *
 * nHeight, nNonce64, and mix_hash are new fields, added following the same
 * real-world pattern Ravencoin's actual KawPow fork used (verified against
 * Ravencoin's own source, not guessed): nNonce widens from 32 to 64 bits
 * because a GPU exhausts a 32-bit nonce space in a small fraction of a
 * second; mix_hash is ProgPoW's own proof output, stored so a verifier only
 * has to recompute and check ONE value rather than redo the miner's search;
 * nHeight is embedded directly in the header (redundant with CBlockIndex's
 * own tracked height) so ProgPoW's epoch/DAG lookup is self-contained from
 * the header alone, since several call sites that check proof-of-work
 * (mining RPC, tests) construct/verify headers without a CBlockIndex handy.
 *
 * GetHash() is UNCHANGED in signature and role - still the block's identity
 * hash used everywhere for indexing and hashPrevBlock linkage, computed the
 * same double-SHA256 way as upstream Bitcoin Core, just now covering the
 * new fields too. GetPoWHeaderHash() is new: a reduced hash EXCLUDING
 * nNonce64/mix_hash, which is what actually gets fed into the real
 * GPU-favorable ProgPoW algorithm (see pow.cpp) as its "header hash" input -
 * excluding the nonce/mix_hash is required, not optional: they are the two
 * things a miner is searching over, so hashing them in would make every
 * nonce attempt hash to something different for reasons having nothing to
 * do with ProgPoW's own internal mixing. */

class CBlockHeader
{
public:
    // header
    int32_t nVersion;
    uint256 hashPrevBlock;
    uint256 hashMerkleRoot;
    uint32_t nTime;
    uint32_t nBits;
    uint32_t nHeight;
    uint64_t nNonce64;
    uint256 mix_hash;

    CBlockHeader()
    {
        SetNull();
    }

    SERIALIZE_METHODS(CBlockHeader, obj) { READWRITE(obj.nVersion, obj.hashPrevBlock, obj.hashMerkleRoot, obj.nTime, obj.nBits, obj.nHeight, obj.nNonce64, obj.mix_hash); }

    void SetNull()
    {
        nVersion = 0;
        hashPrevBlock.SetNull();
        hashMerkleRoot.SetNull();
        nTime = 0;
        nBits = 0;
        nHeight = 0;
        nNonce64 = 0;
        mix_hash.SetNull();
    }

    bool IsNull() const
    {
        return (nBits == 0);
    }

    uint256 GetHash() const;

    /** Reduced header hash EXCLUDING nNonce64/mix_hash - the actual input
     * fed into the ProgPoW algorithm (see pow.cpp's CheckProofOfWorkImpl). */
    uint256 GetPoWHeaderHash() const;

    NodeSeconds Time() const
    {
        return NodeSeconds{std::chrono::seconds{nTime}};
    }

    int64_t GetBlockTime() const
    {
        return (int64_t)nTime;
    }
};


class CBlock : public CBlockHeader
{
public:
    // network and disk
    std::vector<CTransactionRef> vtx;

    // Memory-only flags for caching expensive checks
    mutable bool fChecked;                            // CheckBlock()
    mutable bool m_checked_witness_commitment{false}; // CheckWitnessCommitment()
    mutable bool m_checked_merkle_root{false};        // CheckMerkleRoot()

    CBlock()
    {
        SetNull();
    }

    CBlock(const CBlockHeader &header)
    {
        SetNull();
        *(static_cast<CBlockHeader*>(this)) = header;
    }

    SERIALIZE_METHODS(CBlock, obj)
    {
        READWRITE(AsBase<CBlockHeader>(obj), obj.vtx);
    }

    void SetNull()
    {
        CBlockHeader::SetNull();
        vtx.clear();
        fChecked = false;
        m_checked_witness_commitment = false;
        m_checked_merkle_root = false;
    }

    std::string ToString() const;
};

/** Describes a place in the block chain to another node such that if the
 * other node doesn't have the same branch, it can find a recent common trunk.
 * The further back it is, the further before the fork it may be.
 */
struct CBlockLocator
{
    /** Historically CBlockLocator's version field has been written to network
     * streams as the negotiated protocol version and to disk streams as the
     * client version, but the value has never been used.
     *
     * Hard-code to the highest protocol version ever written to a network stream.
     * SerParams can be used if the field requires any meaning in the future,
     **/
    static constexpr int DUMMY_VERSION = 70016;

    std::vector<uint256> vHave;

    CBlockLocator() = default;

    explicit CBlockLocator(std::vector<uint256>&& have) : vHave(std::move(have)) {}

    SERIALIZE_METHODS(CBlockLocator, obj)
    {
        int nVersion = DUMMY_VERSION;
        READWRITE(nVersion);
        READWRITE(obj.vHave);
    }

    void SetNull()
    {
        vHave.clear();
    }

    bool IsNull() const
    {
        return vHave.empty();
    }
};

#endif // BITCOIN_PRIMITIVES_BLOCK_H

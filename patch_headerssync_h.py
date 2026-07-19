path = 'src/headerssync.h'
text = open(path).read()

old = '''// A compressed CBlockHeader, which leaves out the prevhash
struct CompressedHeader {
    // header
    int32_t nVersion{0};
    uint256 hashMerkleRoot;
    uint32_t nTime{0};
    uint32_t nBits{0};
    uint32_t nNonce{0};

    CompressedHeader()
    {
        hashMerkleRoot.SetNull();
    }

    explicit CompressedHeader(const CBlockHeader& header)
        : nVersion{header.nVersion},
          hashMerkleRoot{header.hashMerkleRoot},
          nTime{header.nTime},
          nBits{header.nBits},
          nNonce{header.nNonce}
    {
    }

    CBlockHeader GetFullHeader(const uint256& hash_prev_block) const
    {
        CBlockHeader ret;
        ret.nVersion = nVersion;
        ret.hashPrevBlock = hash_prev_block;
        ret.hashMerkleRoot = hashMerkleRoot;
        ret.nTime = nTime;
        ret.nBits = nBits;
        ret.nNonce = nNonce;
        return ret;
    };
};'''

new = '''// A compressed CBlockHeader, which leaves out the prevhash
struct CompressedHeader {
    // header
    int32_t nVersion{0};
    uint256 hashMerkleRoot;
    uint32_t nTime{0};
    uint32_t nBits{0};
    uint32_t nHeight{0};
    uint64_t nNonce64{0};
    uint256 mix_hash;

    CompressedHeader()
    {
        hashMerkleRoot.SetNull();
        mix_hash.SetNull();
    }

    explicit CompressedHeader(const CBlockHeader& header)
        : nVersion{header.nVersion},
          hashMerkleRoot{header.hashMerkleRoot},
          nTime{header.nTime},
          nBits{header.nBits},
          nHeight{header.nHeight},
          nNonce64{header.nNonce64},
          mix_hash{header.mix_hash}
    {
    }

    CBlockHeader GetFullHeader(const uint256& hash_prev_block) const
    {
        CBlockHeader ret;
        ret.nVersion = nVersion;
        ret.hashPrevBlock = hash_prev_block;
        ret.hashMerkleRoot = hashMerkleRoot;
        ret.nTime = nTime;
        ret.nBits = nBits;
        ret.nHeight = nHeight;
        ret.nNonce64 = nNonce64;
        ret.mix_hash = mix_hash;
        return ret;
    };
};'''

assert old in text, 'CompressedHeader block not found verbatim'
text = text.replace(old, new, 1)
open(path, 'w').write(text)
print('headerssync.h patched OK')

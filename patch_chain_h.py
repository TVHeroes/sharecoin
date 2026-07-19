path = 'src/chain.h'
text = open(path).read()

replacements = [
    (
        '''    //! block header
    int32_t nVersion{0};
    uint256 hashMerkleRoot{};
    uint32_t nTime{0};
    uint32_t nBits{0};
    uint32_t nNonce{0};''',
        '''    //! block header
    int32_t nVersion{0};
    uint256 hashMerkleRoot{};
    uint32_t nTime{0};
    uint32_t nBits{0};
    uint64_t nNonce64{0};
    uint256 mix_hash{};''',
    ),
    (
        '''    explicit CBlockIndex(const CBlockHeader& block)
        : nVersion{block.nVersion},
          hashMerkleRoot{block.hashMerkleRoot},
          nTime{block.nTime},
          nBits{block.nBits},
          nNonce{block.nNonce}
    {
    }''',
        '''    explicit CBlockIndex(const CBlockHeader& block)
        : nVersion{block.nVersion},
          hashMerkleRoot{block.hashMerkleRoot},
          nTime{block.nTime},
          nBits{block.nBits},
          nNonce64{block.nNonce64},
          mix_hash{block.mix_hash}
    {
    }''',
    ),
    (
        '''    CBlockHeader GetBlockHeader() const
    {
        CBlockHeader block;
        block.nVersion = nVersion;
        if (pprev)
            block.hashPrevBlock = pprev->GetBlockHash();
        block.hashMerkleRoot = hashMerkleRoot;
        block.nTime = nTime;
        block.nBits = nBits;
        block.nNonce = nNonce;
        return block;
    }''',
        '''    CBlockHeader GetBlockHeader() const
    {
        CBlockHeader block;
        block.nVersion = nVersion;
        if (pprev)
            block.hashPrevBlock = pprev->GetBlockHash();
        block.hashMerkleRoot = hashMerkleRoot;
        block.nTime = nTime;
        block.nBits = nBits;
        block.nHeight = static_cast<uint32_t>(nHeight);
        block.nNonce64 = nNonce64;
        block.mix_hash = mix_hash;
        return block;
    }''',
    ),
    (
        '''        // block header
        READWRITE(obj.nVersion);
        READWRITE(obj.hashPrev);
        READWRITE(obj.hashMerkleRoot);
        READWRITE(obj.nTime);
        READWRITE(obj.nBits);
        READWRITE(obj.nNonce);
    }''',
        '''        // block header
        READWRITE(obj.nVersion);
        READWRITE(obj.hashPrev);
        READWRITE(obj.hashMerkleRoot);
        READWRITE(obj.nTime);
        READWRITE(obj.nBits);
        READWRITE(obj.nNonce64);
        READWRITE(obj.mix_hash);
    }''',
    ),
    (
        '''    uint256 ConstructBlockHash() const
    {
        CBlockHeader block;
        block.nVersion = nVersion;
        block.hashPrevBlock = hashPrev;
        block.hashMerkleRoot = hashMerkleRoot;
        block.nTime = nTime;
        block.nBits = nBits;
        block.nNonce = nNonce;
        return block.GetHash();
    }''',
        '''    uint256 ConstructBlockHash() const
    {
        CBlockHeader block;
        block.nVersion = nVersion;
        block.hashPrevBlock = hashPrev;
        block.hashMerkleRoot = hashMerkleRoot;
        block.nTime = nTime;
        block.nBits = nBits;
        block.nHeight = static_cast<uint32_t>(nHeight);
        block.nNonce64 = nNonce64;
        block.mix_hash = mix_hash;
        return block.GetHash();
    }''',
    ),
]

for old, new in replacements:
    assert old in text, f'pattern not found verbatim:\\n{old[:80]}...'
    text = text.replace(old, new, 1)

open(path, 'w').write(text)
print(f'chain.h patched OK, {len(replacements)} replacements applied')

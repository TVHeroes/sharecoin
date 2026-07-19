path = 'src/primitives/block.cpp'
text = open(path).read()

old = '''uint256 CBlockHeader::GetHash() const
{
    return (HashWriter{} << *this).GetHash();
}

std::string CBlock::ToString() const
{
    std::stringstream s;
    s << strprintf("CBlock(hash=%s, ver=0x%08x, hashPrevBlock=%s, hashMerkleRoot=%s, nTime=%u, nBits=%08x, nNonce=%u, vtx=%u)\\n",
        GetHash().ToString(),
        nVersion,
        hashPrevBlock.ToString(),
        hashMerkleRoot.ToString(),
        nTime, nBits, nNonce,
        vtx.size());
    for (const auto& tx : vtx) {
        s << "  " << tx->ToString() << "\\n";
    }
    return s.str();
}'''

new = '''uint256 CBlockHeader::GetHash() const
{
    return (HashWriter{} << *this).GetHash();
}

uint256 CBlockHeader::GetPoWHeaderHash() const
{
    // Deliberately excludes nNonce64/mix_hash - see the class-level comment
    // in block.h for why. This is what actually gets passed as ProgPoW's
    // "header_hash" argument in pow.cpp.
    HashWriter hw{};
    hw << nVersion << hashPrevBlock << hashMerkleRoot << nTime << nBits << nHeight;
    return hw.GetHash();
}

std::string CBlock::ToString() const
{
    std::stringstream s;
    s << strprintf("CBlock(hash=%s, ver=0x%08x, hashPrevBlock=%s, hashMerkleRoot=%s, nTime=%u, nBits=%08x, nHeight=%u, nNonce64=%u, mix_hash=%s, vtx=%u)\\n",
        GetHash().ToString(),
        nVersion,
        hashPrevBlock.ToString(),
        hashMerkleRoot.ToString(),
        nTime, nBits, nHeight, nNonce64, mix_hash.ToString(),
        vtx.size());
    for (const auto& tx : vtx) {
        s << "  " << tx->ToString() << "\\n";
    }
    return s.str();
}'''

assert old in text, 'old block.cpp content not found verbatim'
text = text.replace(old, new, 1)
open(path, 'w').write(text)
print('block.cpp patched OK')

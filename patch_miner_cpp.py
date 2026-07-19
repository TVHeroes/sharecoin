"""
Patches src/node/miner.cpp - the two places CreateNewBlock's header-filling
and AddMerkleRootAndCoinbase touch the nonce/mix_hash fields directly (both
mechanical follow-ons of the field rename in primitives/block.h, not new
logic of their own).
"""
path = 'src/node/miner.cpp'
text = open(path).read()

old_header_fill = '''    // Fill in header
    pblock->hashPrevBlock  = pindexPrev->GetBlockHash();
    UpdateTime(pblock, chainparams.GetConsensus(), pindexPrev);
    pblock->nBits          = GetNextWorkRequired(pindexPrev, pblock, chainparams.GetConsensus());
    pblock->nNonce         = 0;'''
new_header_fill = '''    // Fill in header
    pblock->hashPrevBlock  = pindexPrev->GetBlockHash();
    pblock->nHeight        = static_cast<uint32_t>(pindexPrev->nHeight + 1);
    UpdateTime(pblock, chainparams.GetConsensus(), pindexPrev);
    pblock->nBits          = GetNextWorkRequired(pindexPrev, pblock, chainparams.GetConsensus());
    pblock->nNonce64       = 0;
    pblock->mix_hash.SetNull();'''

assert old_header_fill in text, 'CreateNewBlock header-fill block not found verbatim'
text = text.replace(old_header_fill, new_header_fill, 1)

old_addmerkle = '''void AddMerkleRootAndCoinbase(CBlock& block, CTransactionRef coinbase, uint32_t version, uint32_t timestamp, uint32_t nonce)
{
    if (block.vtx.size() == 0) {
        block.vtx.emplace_back(coinbase);
    } else {
        block.vtx[0] = coinbase;
    }
    block.nVersion = version;
    block.nTime = timestamp;
    block.nNonce = nonce;
    block.hashMerkleRoot = BlockMerkleRoot(block);'''
new_addmerkle = '''void AddMerkleRootAndCoinbase(CBlock& block, CTransactionRef coinbase, uint32_t version, uint32_t timestamp, uint64_t nonce, const uint256& mix_hash)
{
    if (block.vtx.size() == 0) {
        block.vtx.emplace_back(coinbase);
    } else {
        block.vtx[0] = coinbase;
    }
    block.nVersion = version;
    block.nTime = timestamp;
    block.nNonce64 = nonce;
    block.mix_hash = mix_hash;
    block.hashMerkleRoot = BlockMerkleRoot(block);'''

assert old_addmerkle in text, 'AddMerkleRootAndCoinbase not found verbatim'
text = text.replace(old_addmerkle, new_addmerkle, 1)

open(path, 'w').write(text)
print('miner.cpp patched OK')

"""
Patches src/node/blockstorage.cpp - three call sites needing the field
rename (nNonce -> nNonce64 + mix_hash) and CheckProofOfWork's new signature
(takes the full header/block, not a precomputed hash - see patch_pow_h.py).
"""
path = 'src/node/blockstorage.cpp'
text = open(path).read()

old_index_load = '''                pindexNew->nNonce         = diskindex.nNonce;
                pindexNew->nStatus        = diskindex.nStatus;
                pindexNew->nTx            = diskindex.nTx;

'''
new_index_load = '''                pindexNew->nNonce64       = diskindex.nNonce64;
                pindexNew->mix_hash       = diskindex.mix_hash;
                pindexNew->nStatus        = diskindex.nStatus;
                pindexNew->nTx            = diskindex.nTx;

'''
assert old_index_load in text, 'index-load block not found verbatim'
text = text.replace(old_index_load, new_index_load, 1)

old_check1 = '''                if (!CheckProofOfWork(pindexNew->GetBlockHash(), pindexNew->nBits, consensusParams)) {'''
new_check1 = '''                if (!CheckProofOfWork(pindexNew->GetBlockHeader(), pindexNew->nBits, consensusParams)) {'''
assert old_check1 in text, 'first CheckProofOfWork call site not found verbatim'
text = text.replace(old_check1, new_check1, 1)

old_check2 = '''    if (!CheckProofOfWork(block_hash, block.nBits, GetConsensus())) {'''
new_check2 = '''    if (!CheckProofOfWork(block, block.nBits, GetConsensus())) {'''
assert old_check2 in text, 'second CheckProofOfWork call site not found verbatim'
text = text.replace(old_check2, new_check2, 1)

open(path, 'w').write(text)
print('blockstorage.cpp patched OK')

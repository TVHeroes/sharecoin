"""
Patches src/node/miner.h - the AddMerkleRootAndCoinbase declaration,
matching its widened nonce/added mix_hash parameter in miner.cpp
(see patch_miner_cpp.py).
"""
path = 'src/node/miner.h'
text = open(path).read()

old = '''void AddMerkleRootAndCoinbase(CBlock& block, CTransactionRef coinbase, uint32_t version, uint32_t timestamp, uint32_t nonce);'''
new = '''void AddMerkleRootAndCoinbase(CBlock& block, CTransactionRef coinbase, uint32_t version, uint32_t timestamp, uint64_t nonce, const uint256& mix_hash);'''

assert old in text, 'AddMerkleRootAndCoinbase declaration not found verbatim'
text = text.replace(old, new, 1)

open(path, 'w').write(text)
print('miner.h patched OK')

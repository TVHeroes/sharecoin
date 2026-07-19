"""
Patches src/node/interfaces.cpp - the submitSolution() implementation,
matching the widened nonce/added mix_hash parameter from
patch_interfaces_mining_h.py, threading mix_hash through to
AddMerkleRootAndCoinbase (see patch_miner_cpp.py).
"""
path = 'src/node/interfaces.cpp'
text = open(path).read()

old = '''    bool submitSolution(uint32_t version, uint32_t timestamp, uint32_t nonce, CTransactionRef coinbase) override
    {
        if (!coinbase) return false;
        AddMerkleRootAndCoinbase(m_block_template->block, std::move(coinbase), version, timestamp, nonce);'''
new = '''    bool submitSolution(uint32_t version, uint32_t timestamp, uint64_t nonce, const uint256& mix_hash, CTransactionRef coinbase) override
    {
        if (!coinbase) return false;
        AddMerkleRootAndCoinbase(m_block_template->block, std::move(coinbase), version, timestamp, nonce, mix_hash);'''

assert old in text, 'submitSolution implementation not found verbatim'
text = text.replace(old, new, 1)

open(path, 'w').write(text)
print('interfaces.cpp patched OK')

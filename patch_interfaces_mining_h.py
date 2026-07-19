"""
Patches src/interfaces/mining.h - widens submitSolution's nonce to 64-bit
and adds a mix_hash parameter, since ProgPoW's proof is a (nonce, mix_hash)
pair, not a single value the way Bitcoin's original SHA-256d PoW was - an
external miner submitting a found solution back to the node (e.g. over
GBT/pprpcsb) must report both.
"""
path = 'src/interfaces/mining.h'
text = open(path).read()

old = '''    virtual bool submitSolution(uint32_t version, uint32_t timestamp, uint32_t nonce, CTransactionRef coinbase) = 0;'''
new = '''    // GPU-mined-crypto note: mix_hash added alongside nonce (now uint64_t,
    // widened from uint32_t) - ProgPoW's proof is a (nonce, mix_hash) pair,
    // not just a nonce the way Bitcoin's original SHA-256d PoW was, so an
    // external miner submitting a found solution must report both.
    virtual bool submitSolution(uint32_t version, uint32_t timestamp, uint64_t nonce, const uint256& mix_hash, CTransactionRef coinbase) = 0;'''

assert old in text, 'submitSolution declaration not found verbatim'
text = text.replace(old, new, 1)

open(path, 'w').write(text)
print('mining.h patched OK')

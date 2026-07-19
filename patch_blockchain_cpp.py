"""
Patches src/rpc/blockchain.cpp - getblock/getblockheader's own nonce display
gains a mix_hash field alongside it (ProgPoW's proof is a (nonce, mix_hash)
pair, not just a nonce).
"""
path = 'src/rpc/blockchain.cpp'
text = open(path).read()

old = '''    result.pushKV("nonce", blockindex.nNonce);'''
new = '''    result.pushKV("nonce", blockindex.nNonce64);
    result.pushKV("mix_hash", blockindex.mix_hash.GetHex());'''

assert old in text, 'nonce pushKV not found verbatim'
text = text.replace(old, new, 1)

open(path, 'w').write(text)
print('blockchain.cpp patched OK')

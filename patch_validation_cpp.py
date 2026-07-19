"""
Patches src/validation.cpp - two CheckProofOfWork call sites updated for
its new signature (takes the full header/block, not a precomputed hash -
see patch_pow_h.py).
"""
path = 'src/validation.cpp'
text = open(path).read()

old1 = '''    if (fCheckPOW && !CheckProofOfWork(block.GetHash(), block.nBits, consensusParams))'''
new1 = '''    if (fCheckPOW && !CheckProofOfWork(block, block.nBits, consensusParams))'''
assert old1 in text, 'first CheckProofOfWork call site not found verbatim'
text = text.replace(old1, new1, 1)

old2 = '''                               [&](const auto& header) { return CheckProofOfWork(header.GetHash(), header.nBits, consensusParams); });'''
new2 = '''                               [&](const auto& header) { return CheckProofOfWork(header, header.nBits, consensusParams); });'''
assert old2 in text, 'second CheckProofOfWork call site not found verbatim'
text = text.replace(old2, new2, 1)

open(path, 'w').write(text)
print('validation.cpp patched OK')

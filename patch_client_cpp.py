"""
Patches src/rpc/client.cpp's argument-type conversion table - without this
entry, bitcoin-cli sends getkawpowhash's height parameter as a JSON string
instead of a number, since new custom RPCs aren't in that table by default
(a real, easy-to-miss step for any new RPC with non-string arguments).
"""
path = 'src/rpc/client.cpp'
text = open(path).read()

old = '''    { "generatetoaddress", 0, "nblocks" },
    { "generatetoaddress", 2, "maxtries" },
    { "generatetodescriptor", 0, "num_blocks" },'''
new = '''    { "generatetoaddress", 0, "nblocks" },
    { "generatetoaddress", 2, "maxtries" },
    { "getkawpowhash", 3, "height" },
    { "generatetodescriptor", 0, "num_blocks" },'''

assert old in text, 'client.cpp anchor not found verbatim'
text = text.replace(old, new, 1)

open(path, 'w').write(text)
print('client.cpp patched OK')

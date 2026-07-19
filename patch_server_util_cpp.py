"""
Patches src/rpc/server_util.cpp's NextEmptyBlockIndex helper - fills in
nHeight (needed by ProgPoW's epoch/DAG lookup, see primitives/block.h) and
renames nNonce -> nNonce64.
"""
path = 'src/rpc/server_util.cpp'
text = open(path).read()

old = '''    CBlockHeader next_header{};
    next_header.hashPrevBlock  = tip.GetBlockHash();
    UpdateTime(&next_header, consensusParams, &tip);
    next_header.nBits = GetNextWorkRequired(&tip, &next_header, consensusParams);
    next_header.nNonce = 0;

    next_index.pprev = &tip;
    next_index.nTime = next_header.nTime;
    next_index.nBits = next_header.nBits;
    next_index.nNonce = next_header.nNonce;
    next_index.nHeight = tip.nHeight + 1;'''
new = '''    CBlockHeader next_header{};
    next_header.hashPrevBlock  = tip.GetBlockHash();
    next_header.nHeight = static_cast<uint32_t>(tip.nHeight + 1);
    UpdateTime(&next_header, consensusParams, &tip);
    next_header.nBits = GetNextWorkRequired(&tip, &next_header, consensusParams);
    next_header.nNonce64 = 0;

    next_index.pprev = &tip;
    next_index.nTime = next_header.nTime;
    next_index.nBits = next_header.nBits;
    next_index.nNonce64 = next_header.nNonce64;
    next_index.nHeight = tip.nHeight + 1;'''

assert old in text, 'NextEmptyBlockIndex body not found verbatim'
text = text.replace(old, new, 1)

open(path, 'w').write(text)
print('server_util.cpp patched OK')

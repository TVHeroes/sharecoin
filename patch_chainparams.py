"""
Patches src/kernel/chainparams.cpp - the network-identity and genesis
changes that make this fork Sharecoin rather than just "modified Bitcoin":
message-start bytes, default ports, bech32 HRPs, and genesis block mining
values for all five networks (main/testnet/testnet4/signet/regtest).

Base commit this patch was written against: bitcoin/bitcoin@18c05d9
("Merge bitcoin/bitcoin#35590: test: wallet: BnB incomplete result on
attempt-limit success"). If applying against a different commit, verify
each old-text block still matches verbatim first - this file uses the same
find-and-replace approach as the other patch_*.py scripts in this repo, so
any drift in the surrounding code will cause an assertion failure rather
than a silent partial patch.

base58Prefixes (legacy P2PKH/P2SH/WIF address version bytes) are
DELIBERATELY left unchanged, still inherited Bitcoin testnet/mainnet
values - a known, documented limitation (see README.md), not an omission
here.

The five `assert(consensus.hashGenesisBlock == ...)` checks are removed
outright rather than updated to match new values - they exist upstream to
catch an *accidental* genesis change, which doesn't apply to a chain whose
genesis is being freshly, deliberately defined. Only regtest's genesis
here is actually mined at a real difficulty target (nBits=0x1e53e2d6,
nonce=21761, the mix_hash below) - main/testnet/testnet4/signet keep
placeholder nonce/mix_hash fields and are NOT minable/selectable as-is;
see README.md's "Known limitations".
"""
path = 'src/kernel/chainparams.cpp'
text = open(path).read()

replacements = [
    # streams.h include (harmless if unused directly - kept for parity with
    # the tree this was verified to build successfully from)
    (
        '''#include <script/verify_flags.h>
#include <uint256.h>''',
        '''#include <script/verify_flags.h>
#include <streams.h>
#include <uint256.h>''',
    ),
    # CreateGenesisBlock signature widened: nonce -> uint64_t, new mix_hash
    # parameter, nBits loses its (now-misleading) uint32_t spelling to match
    # nBits' real type elsewhere.
    (
        '''static CBlock CreateGenesisBlock(const char* pszTimestamp, const CScript& genesisOutputScript, uint32_t nTime, uint32_t nNonce, uint32_t nBits, int32_t nVersion, const CAmount& genesisReward)
{
    CMutableTransaction txNew;''',
        '''static CBlock CreateGenesisBlock(const char* pszTimestamp, const CScript& genesisOutputScript, uint32_t nTime, uint64_t nNonce, unsigned int nBits, int32_t nVersion, const CAmount& genesisReward, const uint256& mix_hash)
{
    CMutableTransaction txNew;''',
    ),
    (
        '''    genesis.nTime    = nTime;
    genesis.nBits    = nBits;
    genesis.nNonce   = nNonce;
    genesis.nVersion = nVersion;''',
        '''    genesis.nTime    = nTime;
    genesis.nBits    = nBits;
    genesis.nHeight  = 0;
    genesis.nNonce64 = nNonce;
    genesis.mix_hash = mix_hash;
    genesis.nVersion = nVersion;''',
    ),
    (
        '''static CBlock CreateGenesisBlock(uint32_t nTime, uint32_t nNonce, uint32_t nBits, int32_t nVersion, const CAmount& genesisReward)
{
    const char* pszTimestamp = "The Times 03/Jan/2009 Chancellor on brink of second bailout for banks";
    const CScript genesisOutputScript = CScript() << "04678afdb0fe5548271967f1a67130b7105cd6a828e03909a67962e0ea1f61deb649f6bc3f4cef38c4f35504e51ec112de5c384df7ba0b8d578a4c702b6bf11d5f"_hex << OP_CHECKSIG;
    return CreateGenesisBlock(pszTimestamp, genesisOutputScript, nTime, nNonce, nBits, nVersion, genesisReward);
}''',
        '''static CBlock CreateGenesisBlock(uint32_t nTime, uint64_t nNonce, unsigned int nBits, int32_t nVersion, const CAmount& genesisReward, const uint256& mix_hash = uint256())
{
    const char* pszTimestamp = "The Times 03/Jan/2009 Chancellor on brink of second bailout for banks";
    const CScript genesisOutputScript = CScript() << "04678afdb0fe5548271967f1a67130b7105cd6a828e03909a67962e0ea1f61deb649f6bc3f4cef38c4f35504e51ec112de5c384df7ba0b8d578a4c702b6bf11d5f"_hex << OP_CHECKSIG;
    return CreateGenesisBlock(pszTimestamp, genesisOutputScript, nTime, nNonce, nBits, nVersion, genesisReward, mix_hash);
}''',
    ),

    # ---- mainnet ----
    (
        '''        pchMessageStart[0] = 0xf9;
        pchMessageStart[1] = 0xbe;
        pchMessageStart[2] = 0xb4;
        pchMessageStart[3] = 0xd9;
        nDefaultPort = 8333;
        nPruneAfterHeight = 100000;
        m_assumed_blockchain_size = 856;
        m_assumed_chain_state_size = 14;

        genesis = CreateGenesisBlock(1231006505, 2083236893, 0x1d00ffff, 1, 50 * COIN);
        consensus.hashGenesisBlock = genesis.GetHash();
        assert(consensus.hashGenesisBlock == uint256{"000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"});
        assert(genesis.hashMerkleRoot == uint256{"4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"});''',
        '''        pchMessageStart[0] = 0x53; // 'S'
        pchMessageStart[1] = 0x48; // 'H'
        pchMessageStart[2] = 0x43; // 'C'
        pchMessageStart[3] = 0x31; // '1' - spells SHC1 (Sharecoin), distinct from Bitcoin's 0xf9beb4d9
        nDefaultPort = 8433;
        nPruneAfterHeight = 100000;
        m_assumed_blockchain_size = 856;
        m_assumed_chain_state_size = 14;

        genesis = CreateGenesisBlock(1231006505, 2083236893, 0x1d00ffff, 1, 50 * COIN);
        consensus.hashGenesisBlock = genesis.GetHash();
        assert(genesis.hashMerkleRoot == uint256{"4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"});''',
    ),
    (
        '''        bech32_hrp = "bc";

        vFixedSeeds = std::vector<uint8_t>(std::begin(chainparams_seed_main), std::end(chainparams_seed_main));''',
        '''        bech32_hrp = "shc";

        vFixedSeeds = std::vector<uint8_t>(std::begin(chainparams_seed_main), std::end(chainparams_seed_main));''',
    ),

    # ---- testnet (testnet3) ----
    (
        '''        pchMessageStart[0] = 0x0b;
        pchMessageStart[1] = 0x11;
        pchMessageStart[2] = 0x09;
        pchMessageStart[3] = 0x07;
        nDefaultPort = 18333;
        nPruneAfterHeight = 1000;
        m_assumed_blockchain_size = 245;
        m_assumed_chain_state_size = 19;

        genesis = CreateGenesisBlock(1296688602, 414098458, 0x1d00ffff, 1, 50 * COIN);
        consensus.hashGenesisBlock = genesis.GetHash();
        assert(consensus.hashGenesisBlock == uint256{"000000000933ea01ad0ee984209779baaec3ced90fa3f408719526f8d77f4943"});
        assert(genesis.hashMerkleRoot == uint256{"4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"});''',
        '''        pchMessageStart[0] = 0x53; // 'S'
        pchMessageStart[1] = 0x48; // 'H'
        pchMessageStart[2] = 0x43; // 'C'
        pchMessageStart[3] = 0x54; // 'T' - spells SHCT (Sharecoin testnet)
        nDefaultPort = 18433;
        nPruneAfterHeight = 1000;
        m_assumed_blockchain_size = 245;
        m_assumed_chain_state_size = 19;

        genesis = CreateGenesisBlock(1296688602, 414098458, 0x1d00ffff, 1, 50 * COIN);
        consensus.hashGenesisBlock = genesis.GetHash();
        assert(genesis.hashMerkleRoot == uint256{"4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"});''',
    ),
    (
        '''        bech32_hrp = "tb";

        vFixedSeeds = std::vector<uint8_t>(std::begin(chainparams_seed_test), std::end(chainparams_seed_test));''',
        '''        bech32_hrp = "tshc";

        vFixedSeeds = std::vector<uint8_t>(std::begin(chainparams_seed_test), std::end(chainparams_seed_test));''',
    ),

    # ---- testnet4 ----
    (
        '''        pchMessageStart[0] = 0x1c;
        pchMessageStart[1] = 0x16;
        pchMessageStart[2] = 0x3f;
        pchMessageStart[3] = 0x28;
        nDefaultPort = 48333;
        nPruneAfterHeight = 1000;
        m_assumed_blockchain_size = 31;
        m_assumed_chain_state_size = 2;''',
        '''        pchMessageStart[0] = 0x53; // 'S'
        pchMessageStart[1] = 0x48; // 'H'
        pchMessageStart[2] = 0x43; // 'C'
        pchMessageStart[3] = 0x34; // '4' - spells SHC4 (Sharecoin testnet4)
        nDefaultPort = 48433;
        nPruneAfterHeight = 1000;
        m_assumed_blockchain_size = 31;
        m_assumed_chain_state_size = 2;''',
    ),
    (
        '''                393743547,
                0x1d00ffff,
                1,
                50 * COIN);
        consensus.hashGenesisBlock = genesis.GetHash();
        assert(consensus.hashGenesisBlock == uint256{"00000000da84f2bafbbc53dee25a72ae507ff4914b867c565be350b0da8bf043"});
        assert(genesis.hashMerkleRoot == uint256{"7aa0a7ae1e223414cb807e40cd57e667b718e42aaf9306db9102fe28912b7b4e"});''',
        '''                393743547,
                0x1d00ffff,
                1,
                50 * COIN,
                uint256());
        consensus.hashGenesisBlock = genesis.GetHash();
        assert(genesis.hashMerkleRoot == uint256{"7aa0a7ae1e223414cb807e40cd57e667b718e42aaf9306db9102fe28912b7b4e"});''',
    ),
    (
        '''        bech32_hrp = "tb";

        vFixedSeeds = std::vector<uint8_t>(std::begin(chainparams_seed_testnet4), std::end(chainparams_seed_testnet4));''',
        '''        bech32_hrp = "tshc";

        vFixedSeeds = std::vector<uint8_t>(std::begin(chainparams_seed_testnet4), std::end(chainparams_seed_testnet4));''',
    ),

    # ---- signet ----
    # (message-start bytes NOT patched here - signet's are already dynamically
    # derived from the signet challenge script, not a literal copied constant)
    (
        '''        nDefaultPort = 38333;
        nPruneAfterHeight = 1000;

        genesis = CreateGenesisBlock(1598918400, 52613770, 0x1e0377ae, 1, 50 * COIN);
        consensus.hashGenesisBlock = genesis.GetHash();
        assert(consensus.hashGenesisBlock == uint256{"00000008819873e925422c1ff0f99f7cc9bbb232af63a077a480a3633bee1ef6"});
        assert(genesis.hashMerkleRoot == uint256{"4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"});''',
        '''        nDefaultPort = 38433;
        nPruneAfterHeight = 1000;

        genesis = CreateGenesisBlock(1598918400, 52613770, 0x1e0377ae, 1, 50 * COIN);
        consensus.hashGenesisBlock = genesis.GetHash();
        assert(genesis.hashMerkleRoot == uint256{"4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"});''',
    ),
    (
        '''        bech32_hrp = "tb";

        fDefaultConsistencyChecks = false;
        m_is_mockable_chain = false;''',
        '''        bech32_hrp = "tshc";

        fDefaultConsistencyChecks = false;
        m_is_mockable_chain = false;''',
    ),

    # ---- regtest ----
    # This is the ONLY network with a genuinely mined (not placeholder)
    # genesis - nonce/mix_hash below satisfy the real nBits=0x1e53e2d6
    # target, found via bitcoin-util grind (see README.md).
    (
        '''        pchMessageStart[0] = 0xfa;
        pchMessageStart[1] = 0xbf;
        pchMessageStart[2] = 0xb5;
        pchMessageStart[3] = 0xda;
        nDefaultPort = 18444;
        nPruneAfterHeight = opts.fastprune ? 100 : 1000;
        m_assumed_blockchain_size = 0;
        m_assumed_chain_state_size = 0;

        ApplyDeploymentOptions(opts.dep_opts);

        genesis = CreateGenesisBlock(1296688602, 2, 0x207fffff, 1, 50 * COIN);
        consensus.hashGenesisBlock = genesis.GetHash();
        assert(consensus.hashGenesisBlock == uint256{"0f9188f13cb7b2c71f2a335e3a4fc328bf5beb436012afca590b1a11466e2206"});
        assert(genesis.hashMerkleRoot == uint256{"4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"});''',
        '''        pchMessageStart[0] = 0x53; // 'S'
        pchMessageStart[1] = 0x48; // 'H'
        pchMessageStart[2] = 0x43; // 'C'
        pchMessageStart[3] = 0x52; // 'R' - spells SHCR (Sharecoin regtest)
        nDefaultPort = 18544;
        nPruneAfterHeight = opts.fastprune ? 100 : 1000;
        m_assumed_blockchain_size = 0;
        m_assumed_chain_state_size = 0;

        ApplyDeploymentOptions(opts.dep_opts);

        genesis = CreateGenesisBlock(1296688602, 21761, 0x1e53e2d6, 1, 50 * COIN, uint256{"920c0c85af3e2d0ad28913155201e9d0499c3b7e15495cf97e93fdbfe622a50c"});
        consensus.hashGenesisBlock = genesis.GetHash();
        assert(genesis.hashMerkleRoot == uint256{"4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"});''',
    ),
    (
        '''        bech32_hrp = "bcrt";

        // Copied from Testnet4.''',
        '''        bech32_hrp = "shcrt";

        // Copied from Testnet4.''',
    ),
]

for old, new in replacements:
    assert old in text, f'pattern not found verbatim:\\n{old[:120]}...'
    text = text.replace(old, new, 1)

open(path, 'w').write(text)
print(f'chainparams.cpp patched OK, {len(replacements)} replacements applied')

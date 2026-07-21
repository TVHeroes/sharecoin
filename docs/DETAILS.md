# Sharecoin - technical details

The README keeps things short, matching how Bitcoin Core/Litecoin/Dogecoin/
Ravencoin all structure theirs. Everything below is the detail that used to
live there - not required reading to just use the wallet or mine, but useful
if you want to build from source, run your own network, understand the
randomness beacon, or audit exactly what changed from upstream Bitcoin Core.

## Building, in detail

`bitcoin-source/` is the actual patched tree (already includes the
vendored ethash/ProgPoW library, already has every fix applied) - it
builds the same way upstream Bitcoin Core does:
- Linux/WSL: standard CMake + vcpkg or system deps, see
  `bitcoin-source/doc/build-*.md`.
- Windows GUI wallet (`bitcoin-qt`): `bitcoin-source/doc/build-windows-msvc.md`,
  with Visual Studio + vcpkg (`BUILD_GUI=ON`). After building, the Qt
  plugin folders (`platforms/`, `generic/`, etc.) from
  `vcpkg_installed/x64-windows/Qt6/plugins/` must be copied next to the
  built `.exe` - vcpkg's Qt port doesn't do this automatically on Windows.
  (Not needed if you're just using the prebuilt binaries in `wallet/` -
  see `docs/WINDOWS.md`.)

## Importing a generated key into the GUI wallet

After running `generate_wallet.py`: open `sharecoin-qt`, create a wallet,
then in **Window → Console**, import the generated key with:
```
getdescriptorinfo "pkh(YOUR_WIF_HERE)"
```
then take the returned checksum and run:
```
importdescriptors [{"desc":"pkh(YOUR_WIF_HERE)#CHECKSUM_HERE","timestamp":"now"}]
```

## How the fork was made

**Base commit:** [`bitcoin/bitcoin@18c05d9`](https://github.com/bitcoin/bitcoin/commit/18c05d9)
("Merge bitcoin/bitcoin#35590: test: wallet: BnB incomplete result on
attempt-limit success"). `bitcoin-source/` already has every change
applied - the `patch_*.py` scripts in this repo aren't a required step to
use anything; they're kept as an exact, literal record of what changed and
why, file by file, verified against the real base commit (each was run
against the pristine upstream file and its output compared byte-for-byte
against this project's own real, already-built source - a handful differ
only in code-comment wording, never in anything that affects compiled
behavior). Useful if you want to understand or re-derive the diff, port it
to a different base commit, or audit exactly what changed; not useful as
a "run these to get the source" step, since the source is just already
here.

The dependency order, if you do want to re-apply them against a fresh
Bitcoin Core clone at the same base commit: `patch_block_h.py` →
`patch_block_cpp.py` → `patch_chain_h.py` → `patch_headerssync_h.py` →
`patch_pow_h.py` → `patch_pow_cpp.py` → `patch_pow_cpp_additions.py` →
`patch_chainparams.py` → `patch_src_cmakelists.py` → `patch_miner_h.py` →
`patch_miner_cpp.py` → `patch_interfaces_mining_h.py` →
`patch_interfaces_cpp.py` → `patch_blockstorage_cpp.py` →
`patch_blockchain_cpp.py` → `patch_client_cpp.py` →
`patch_server_util_cpp.py` → `patch_validation_cpp.py` →
`patch_bitcoin_util_cpp.py` → `patch_rpc_mining_new_rpcs.py` →
`patch_rpc_mining_additions.py` → `patch_rpc_randombeacon.py`.
`patch_branding_sweep.py` (renames remaining user-visible "Bitcoin" strings
to "Sharecoin") has no ordering dependency on the others and can be applied
any time after the base patches above. `patch_chainparams_msvc_compat.py`
is a Windows/MSVC-only fix (a `consteval` constructor MSVC rejects that
GCC/Clang accept as-is) - skip it entirely when building on Linux/WSL. You'd
also need to vendor
`src/crypto/ethash/` from
[Ravencoin's own repo](https://github.com/RavenProject/Ravencoin/tree/master/src/crypto/ethash)
first (real, independent upstream code, Apache-2.0, copyright 2018-2019
Pawel Bylica - not a Ravencoin invention; its `LICENSE` file isn't at that
path in Ravencoin's own repo, pull it from
[chfast/ethash](https://github.com/chfast/ethash) instead; one real bug
needs fixing for a modern Bitcoin Core codebase, `lib/ethash/managed.cpp`'s
`CCriticalSection` renamed to `RecursiveMutex`; its `CMakeLists.txt` is new,
written for this fork (see `bitcoin-source/src/crypto/ethash/CMakeLists.txt`))
- none of which you need to do, since `bitcoin-source/` already has all of it.

## Mining in detail

A live, already-running Sharecoin network is reachable by default at
`sharecoin.duckdns.org:10000` - so mining against it needs no
server setup of your own, just kawpowminer and a wallet address (see the
README's "Mining" section for the download link and an example
invocation).

Real GPU miner software other than kawpowminer (T-Rex, GMiner, NBMiner -
anything that speaks Stratum for KawPow) can point at the same address
directly with its own `-o`/`-P` flag.

**A caveat worth being honest about:** `sharecoin.duckdns.org` is
one person's own machine on residential broadband, reachable via a
router port-forward and dynamic DNS - not a permanent, dedicated
service. It may not always be running, and its address could
occasionally change if dynamic DNS lags a real IP change. If it's down,
or if you'd rather run your own independent network instead of joining
that one, see "Running your own network" below.

### Running your own network

Run the `sharecoind` you built (always with `-regtest` - see the README's
warning on this; without it you get a real Bitcoin mainnet node instead,
which crashes outright in this fork - or, on Windows, `start-node.bat`
with the prebuilt binaries - see `docs/WINDOWS.md`):

```
./sharecoind -regtest -daemon
```

You'll also need a Stratum
proxy in front of it - real GPU miners speak Stratum, not Bitcoin's own
`getblocktemplate`/`submitblock` RPC directly. This repo does **not**
bundle one - the one used during this fork's own development is based on
[kralverde/ravencoin-stratum-proxy](https://github.com/kralverde/ravencoin-stratum-proxy),
which carries no explicit license, so redistributing a modified copy here
would be legally unclear. To set one up yourself (plain Python, same
steps regardless of OS):

1. Clone `kralverde/ravencoin-stratum-proxy` and follow its own setup
   instructions (Python 3.8+, `pip install -r requirements.txt` - note
   `pysha3` may fail to build on modern Python/GCC; a `pycryptodome`-backed
   shim for `keccak_256` is a drop-in fix if so).
2. Apply these fixes on top of its `stratum-converter.py` (all found and
   verified empirically against this fork's own conventions, not assumed):
   - `getblocktemplate` must be called with `"params": [{"rules": ["segwit"]}]`
     - modern Bitcoin Core rejects the bare/no-params call the original
     code uses.
   - `coinbaseaux.flags` may not exist in modern `getblocktemplate` output -
     read it with `.get("flags", "")`, not a direct key lookup.
   - The mix_hash reported by the miner should **not** be byte-reversed
     before use (only the nonce needs reversal) - this fork's header-hash
     convention matches Ethereum/KawPow's own non-reversed `h256` style, not
     Ravencoin's.
   - The block header hash sent to the miner should **not** be
     byte-reversed (`dsha256(header)`, not `dsha256(header)[::-1]`) - same
     reasoning as above.
   - BIP34 coinbase height encoding for heights 1-16 needs the single-byte
     `OP_1`..`OP_16` opcode form, not the generic length-prefixed push the
     original code always uses - real Bitcoin Core rejects the generic form
     at these heights as `bad-cb-height`.
   - Each connecting miner should get their own coinbase/job built from
     their own submitted address, not just whoever connects first - the
     original code's `TemplateState` is shared per-address; splitting this
     into a shared "chain template" plus a per-session "miner job" (own
     coinbase, merkle root, header) is what makes multi-miner reward
     attribution work correctly.
   - Do **not** send kawpowminer the `client.show_message` notification
     (used to report found blocks) - kawpowminer doesn't support this
     method and disconnects shortly after receiving it. Log it locally
     instead.
3. Run it pointed at your node's RPC port (`127.0.0.1:19710` by
   convention in this project's own scripts, credentials matching
   whatever you set with `-rpcuser`/`-rpcpassword`), then point miners
   at the proxy's own listening port.

### GPU batch size

At low/regtest-style difficulty, a real GPU can find many valid nonces
within a single kernel launch before the miner picks up a new job, causing
a stream of harmless "stale batch" rejections. Pass smaller batch flags
(kawpowminer: `--cu-grid-size 1 --cu-streams 1`) if this happens, or raise
the difficulty to something realistic for the actual hashrate involved.

## Randomness beacon, in full

`getrandombeacon start_height (window_size)` derives a public randomness
value from blocks that are already mined and confirmed - useful for
anything that needs unpredictable-in-advance, publicly-verifiable
randomness (a lottery, fair matchmaking, sortition), without running any
separate randomness service.

Why not just use one block's own `mix_hash`? Whoever mines a block sees its
`mix_hash` before deciding whether to broadcast it, so they could withhold
and re-mine until they get a value they like - free for them, since they
keep re-trying at no extra cost until satisfied. `getrandombeacon` instead
combines the `mix_hash` of `window_size` **consecutive** confirmed blocks
(SHA-256 of them concatenated in order). Biasing the combined result now
requires controlling multiple consecutive blocks in that window, not just
one - each block an attacker wants to bias costs them a real, already-earned
block reward they must forfeit, and races them against being orphaned by a
competing miner's block. This bounds their influence to roughly one bit per
block they control in the window, shrinking as `window_size` grows - the
same withhold-and-bias tradeoff Ethereum's own RANDAO accepts, not a
Verifiable Delay Function (a true VDF needs specialized hardware to be
useful and would just favor whoever has the fastest one, working against
the ASIC-resistance ProgPoW is chosen for in the first place).

The RPC only returns a value once every block in `[start_height,
start_height + window_size - 1]` is on the active chain - it errors out
(naming exactly how many more blocks are needed) if the window isn't fully
confirmed yet. No consensus change is required for this: it's a read-only
derivation over `mix_hash` values every node already stores and has already
validated.

```
sharecoin-cli getrandombeacon 1000        # combines blocks [1000, 1099]
sharecoin-cli getrandombeacon 1000 250    # combines blocks [1000, 1249]
```

## Known limitations

- Only sharenet's genesis is actually mined at a real difficulty target;
  main/testnet/testnet4/signet ship with placeholder genesis fields and
  would need the same treatment before use.
- Legacy base58 address version bytes (P2PKH/P2SH/WIF) are still inherited
  Bitcoin testnet/mainnet values - bech32 addresses ARE correctly
  distinguished via a renamed HRP, but legacy-encoded addresses
  superficially resemble real Bitcoin/testnet ones at that encoding layer.
- No real GPU/CUDA kernel is implemented in this repo's own code - mining
  relies entirely on third-party miner software (kawpowminer etc.)
  implementing ProgPoW/KawPow themselves; this project's own code only
  implements the node-side consensus check and job-serving infrastructure.

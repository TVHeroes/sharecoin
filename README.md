# Sharecoin (SHC)

A real fork of Bitcoin Core's C++ source, swapping the mining
proof-of-work algorithm from SHA-256d to ProgPoW/KawPow - the same
GPU-favorable, ASIC-resistant algorithm Ravencoin uses. Everything else
(transactions, scripts, wallets, P2P networking, RPC) is untouched
upstream Bitcoin Core.

The build instructions below assume Linux, the standard way to build any
Bitcoin Core fork. You don't have to build anything to use Sharecoin,
though - see the prebuilt-package callout right below, or
[docs/WINDOWS.md](docs/WINDOWS.md) for the Windows-specific path if you'd
rather use prebuilt binaries there instead.

**Just want to get mining, no cloning or building?** Grab a prebuilt
package from [Releases](https://github.com/TVHeroes/sharecoin/releases/latest) -
Windows gets a portable wallet + launchers (unzip, then follow
[START-HERE.txt](START-HERE.txt)); Linux gets stripped `sharecoind`/
`sharecoin-cli`/`sharecoin-util` binaries (CLI only, no GUI - see the
README.txt inside the tarball).

## The pitch

Here's what almost every Bitcoin fork quietly throws away: all that GPU
compute is producing something genuinely valuable, and nobody's bothered
to use it for anything but itself. Sharecoin does.

Every ProgPoW block mined here comes with a `mix_hash` - an
unpredictable, cryptographically-earned number that costs real GPU-hours
to produce and can't be faked, front-run, or bought after the fact.
That's not exhaust. That's raw material. `getrandombeacon` turns it into
the one thing every lottery, raffle, NFT reveal, matchmaking system, and
sortition-based DAO on the internet is quietly hungry for: **randomness
nobody can rig.** No oracle to trust, no backend quietly rolling dice in
someone's data center, no vendor lock-in - just math, GPUs, and a chain
that was mining anyway.

Decentralization here isn't a promise baked in from day one - it's a
function of who actually shows up and mines. The mechanism doesn't care
how many nodes exist; the security guarantee does. Every independent
miner and node that joins makes the beacon harder for any single party
to bias, and every block mined spends real work turning unpredictability
into a public good instead of a corporate product. What's true right now,
already, no matter how many nodes are running: the mechanism is real,
live, and callable over RPC - not a whitepaper promise, a feature you can
query this second.

Bitcoin proved you could mine money. Sharecoin's here to prove you can
mine trust.

## Contents

- `bitcoin-source/` - the patched Bitcoin Core source tree, builds the
  same way upstream does (`bitcoin-source/doc/build-*.md`).
- `generate_wallet.py` - standalone offline wallet/keypair generator,
  pure Python, works on any OS.
- `patch_*.py` - a literal, file-by-file record of every change from
  upstream Bitcoin Core - not required reading to just use this, see
  `docs/DETAILS.md` if you want to audit or re-derive the diff.
- `wallet/` - prebuilt Windows binaries and `.bat` launcher scripts, see
  `docs/WINDOWS.md` - not needed on Linux.
- `START-HERE.txt` - plain-language quick-start for anyone using the
  prebuilt Windows package from Releases, not building from source.

Real GPU mining software (kawpowminer etc.) isn't bundled here - see
"Mining" below.

## Building

Build `bitcoin-source/` the same way you'd build upstream Bitcoin Core -
standard CMake + vcpkg or system deps, see `bitcoin-source/doc/build-*.md`.
The resulting binaries are named `sharecoind`, `sharecoin-cli`,
`sharecoin-qt` (with `BUILD_GUI=ON`), etc. - same build, same flags, as
any Bitcoin Core fork, just renamed and running ProgPoW/KawPow instead of
SHA-256d.

## Getting a wallet address

Run `generate_wallet.py` (`pip install base58 pycryptodome ecdsa`) to
generate a real secp256k1 keypair entirely offline - no node or wallet
software required. **Keep the printed private key secret and backed up**
- there's no recovery if it's lost.

If you built `sharecoin-qt`, it works like any Bitcoin-Qt build: create a
wallet, then use the **Receive** tab to generate an address directly (or
import the key generated above instead - see `docs/DETAILS.md` for the
exact console commands).

**On Windows**, you don't need to build anything to get a wallet: run
`wallet/start-wallet.bat` (launches the prebuilt `sharecoin-qt.exe`). On
first run it prompts you to create a wallet - accept the defaults. Once
it's open, go to the **Receive** tab and click **Create new receiving
address**. That's it - the wallet holds the private key for you,
encrypted if you set a passphrase when creating it (**Settings → Encrypt
Wallet**, recommended before receiving anything real). See
[docs/WINDOWS.md](docs/WINDOWS.md) for the rest of the Windows path
(mining, running your own node).

## Mining

**You need real GPU mining software - this repo does not include it.**
Sharecoin's own binaries (`sharecoind`/`sharecoin-qt`) validate and relay
blocks, but the actual GPU proof-of-work computation only happens inside
a separate KawPow-capable miner - **kawpowminer** (the same one Ravencoin
uses) is the one this fork has actually been tested against.

Get it from [RavenCommunity/kawpowminer's GitHub Releases](https://github.com/RavenCommunity/kawpowminer/releases)
(Linux: Ubuntu 18/20 builds, CUDA or OpenCL) - verify its published
`.sha256sum` against the download, then point it at a live Sharecoin
network:

```
./kawpowminer -P stratum+tcp://YOUR_ADDRESS.worker1@stormforge.tail0b8084.ts.net:10000 --cu-grid-size 1 --cu-streams 1 --display-interval 2
```

See `docs/DETAILS.md` for running your own node/network/Stratum proxy
instead of joining that one, and GPU batch-size quirks at low difficulty.

## Randomness beacon

`getrandombeacon start_height (window_size)` is a public, verifiable
randomness source derived from already-confirmed blocks, designed to
resist the "last revealer" bias that a single block's own `mix_hash`
would have. See `docs/DETAILS.md` for the full design rationale.

## License

MIT, see [LICENSE](LICENSE). Bitcoin Core's own copyright is preserved
throughout, as its license requires, alongside this fork's own changes.

## Known limitations

See `docs/DETAILS.md`.

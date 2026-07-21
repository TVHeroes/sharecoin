# Sharecoin on Windows

The main README's build instructions assume Linux. This is the
Windows-specific path: prebuilt binaries and `.bat` launcher scripts, so
nothing needs to be built from source.

## What's in `wallet/`

Prebuilt Windows binaries - `sharecoind.exe`, `sharecoin-cli.exe`,
`sharecoin-qt.exe` - plus the Qt DLLs/plugin folders the GUI needs. These
were built the same way `bitcoin-source/doc/build-windows-msvc.md`
describes (Visual Studio + vcpkg, `BUILD_GUI=ON`); you don't need to
repeat that build to use them.

## Getting a wallet address

Run `wallet/start-wallet.bat` (launches the prebuilt `sharecoin-qt.exe`).
On first run it prompts you to create a wallet - accept the defaults.
Once it's open, go to the **Receive** tab and click **Create new
receiving address** to get a Sharecoin address. That's it - the wallet
holds the private key for you, encrypted if you set a passphrase when
creating it (**Settings → Encrypt Wallet**, recommended before receiving
anything real).

Prefer generating a key offline instead? `generate_wallet.py`
(`pip install base58 pycryptodome ecdsa`) works identically on Windows;
see `docs/DETAILS.md` for how to import a key generated this way into
the Qt wallet.

## Mining

`start-mining.bat` is a launcher; it expects a separate program called
**kawpowminer** to already be downloaded - this repo does not include it.
Get the Windows CUDA build from
[RavenCommunity/kawpowminer's GitHub Releases](https://github.com/RavenCommunity/kawpowminer/releases)
(`kawpowminer-windows-cuda11-1.2.4.zip` as of writing), verify its
published `.sha256sum`, then extract it either right next to
`start-mining.bat`, or into its own `kawpowminer-windows-x.x.x\`
subfolder alongside it - the script checks both locations automatically.

Run `start-mining.bat`, enter your address and a worker name, done - it
connects to a live, already-running Sharecoin network by default. Real
GPU miner software other than kawpowminer (T-Rex, GMiner, NBMiner -
anything that speaks Stratum for KawPow) can point at the same address
directly with its own `-o`/`-P` flag instead of using the `.bat` file.

**A caveat worth being honest about:** the default network
(`sharecoin.duckdns.org`) is one person's own machine on residential
broadband, reachable via a router port-forward and dynamic DNS - not a
permanent, dedicated service. It may not always be running, and its
address could occasionally change if dynamic DNS lags a real IP change.
If it's down, or you'd rather run your own independent network, see
"Running your own network" below.

## Running your own network

Run `start-node.bat` (uses the prebuilt `wallet/sharecoind.exe`/
`sharecoin-cli.exe` directly - no WSL/Linux needed; edit the placeholder
`RPCPASSWORD` in the script first). Stop it later with `stop-node.bat`.

You'll also need a Stratum proxy in front of it - real GPU miners speak
Stratum, not Bitcoin's own `getblocktemplate`/`submitblock` RPC directly.
This repo does **not** bundle one; see `docs/DETAILS.md`'s "Running your
own network" section for the proxy setup and the specific fixes it needs
on top of the third-party project it's based on. That section is written
generically (the proxy is plain Python, same steps regardless of OS) -
just point it at `start-node.bat`'s RPC port, `127.0.0.1:19710` by
default, and point miners at the proxy's own listening port instead.

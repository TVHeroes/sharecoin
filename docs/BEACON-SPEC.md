# Beacon parameters: current version and permanence policy

The `getrandombeacon` RPC's underlying data is permanent and independently
verifiable (any node can recompute it from `mix_hash` values it has already
validated, no trust in the maintainer required). But the *usage
conventions* around it, what window size to use, how long to wait, what
it's recommended for, live in documentation and demo code that one person
controls and can edit at any time. Nothing previously stopped that from
changing quietly, with no record of what the guidance used to say.

This file is the fix: a single, dedicated, versioned place for those
conventions, timestamped independently of this repository.

## What is and isn't a protocol rule

**Fixed by the protocol** (true for every caller, cannot be changed without
a consensus-level fork):

- `getrandombeacon start_height [window_size]` only returns a value once
  every block in `[start_height, start_height + window_size - 1]` is on the
  active chain. It errors out, naming exactly how many more blocks are
  needed, if the window isn't fully confirmed yet.
- The value itself is the SHA-256 of the `mix_hash` values of that window's
  blocks, concatenated in order. Any node can recompute it independently
  from data it has already validated.
- If `window_size` is omitted, the RPC itself defaults to **100**.

**Not fixed by the protocol** (caller/application choices, documented here
only as recommendations):

- What window size to actually use.
- How many blocks ahead of "now" to lock in a target height.
- What the result is recommended to be used for.

Nothing enforces these at the consensus level. Any application can call
`getrandombeacon` with whatever parameters it wants. The table below
records what this repository's own reference implementations currently
use, so that changing them later means a new tagged version of this file,
not a silent edit.

## Version 1 (current)

| Parameter | Value | Notes |
|---|---|---|
| Reference window size | 8 blocks | Smaller than the RPC's own default of 100, chosen across this repo's demo scripts for faster, easier-to-follow illustrations. Larger windows bound an attacker's influence more tightly (see `docs/DETAILS.md`); 8 is a usability tradeoff, not a security-optimal value. |
| Lead time before locking a target height | Use-case dependent, see table below | There is no single fixed value; each demo picks a lead time appropriate to its own purpose. |
| Minimum confirmations before treating a result as final | 0 beyond the window itself | The reference demos treat a beacon value as final the moment the RPC returns one, with no additional confirmation buffer. Applications with a lower risk tolerance for chain reorganizations may reasonably choose to wait for additional confirmations past `start_height + window_size - 1`; this repo's demos currently do not. |

Lead time by reference demo, as actually implemented in this repo:

| Demo | Lead time | Reasoning |
|---|---|---|
| Oracle selector | 0 (uses the current tip immediately) | Needs an answer right away, not after a delay. |
| Raffle / roulette web demos | 1 block | Kept short so a live demo resolves quickly; still strictly in the future at commit time. |
| Sortition selector | 5 blocks (default, caller-adjustable) | Committee selection tolerates a short wait. |
| Time-locked vault | 10 blocks (default, caller-adjustable) | Deliberately longer, since the use case is a delayed reveal. |

## Intended applications (documented, not exhaustive, not enforced)

Lotteries and raffles, NFT/collectible reveals, fair matchmaking, DAO or
committee sortition, delayed-reveal commitments, oracle/validator subset
selection. This list describes what the reference demos in this repo
illustrate. It is not a claim that these are the only valid uses, nor a
guarantee that any of them are appropriate for real-money stakes without
your own risk assessment, see `docs/DETAILS.md`'s "Known limitations"
section.

## Permanence policy

Any future change to the values in this document will be published as a
new version of this file (`Version 2`, `Version 3`, ...), never a silent
edit to `Version 1`'s numbers. Each version is:

1. Committed to this repository's git history (ordinary, but permanent
   and diffable as long as history isn't force-rewritten).
2. Tagged as a git release (e.g. `beacon-spec-v1`), giving a permanent,
   unambiguous reference for "what this document said, as of this
   version."
3. Timestamped with [OpenTimestamps](https://opentimestamps.org/), which
   anchors a hash of this exact file into the real Bitcoin blockchain,
   infrastructure this project's maintainer does not control and cannot
   rewrite. The proof file (`BEACON-SPEC.md.ots`) is committed alongside
   this document. Anyone can independently verify, using only Bitcoin
   itself, that this exact text existed unchanged at the time it claims,
   with no need to trust this repository, GitHub, or its maintainer.

This does not make the parameters themselves immutable, they are usage
conventions, not consensus rules, and may reasonably need to change. What
it makes immutable is the *record* of what was recommended and when, so
no earlier version can be quietly rewritten out of history.

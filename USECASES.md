# Sharecoin randomness beacon: use cases

A running log of use cases discussed for `getrandombeacon`, both ones built as
working demos in this repo and ones proposed and evaluated but not built.
Kept honest on purpose: a use case that doesn't actually fit the technology
is recorded as such, not smoothed over. See `docs/BEACON-SPEC.md` for what
the beacon actually guarantees versus what's just demo convention.

## Implemented and demonstrated

These have working reference code and have been tested against a live node.

- **Lotteries and raffles** - `raffle_app.py`. Locks an entrant list at a
  block height, resolves against a future block's beacon value. Live web
  demo.
- **Simulated-stakes gaming (roulette)** - `roulette_app.py`. Same
  underlying mechanic, framed as a pitch for how a real-money game could be
  built on top, deliberately not itself a real-money product (see chat
  history for why: unlicensed real-money gambling is a legal/regulatory
  problem independent of the code being correct).
- **DAO/committee sortition** - `sharecoin-sortition-selector.py`. Draws a
  committee from a candidate pool without replacement.
- **Oracle/validator subset selection** - `sharecoin-oracle-selector.py`.
  Selects an active node subset for the current confirmed block, no
  scheduled wait, reselects each new block.
- **Delayed-reveal commitments (time-locked vault)** -
  `sharecoin-timelock-vault.py`. Important honesty note carried from its own
  docstring: this is a commit-then-reveal scheme with a verifiable trigger
  condition, not true cryptographic timelock encryption. The key is held by
  the operator and could in principle be used early if they break their own
  word - the beacon makes that detectable after the fact, not impossible.
  Real timelock encryption (key mathematically inaccessible until the
  condition is met) would need identity-based encryption, e.g. drand's
  "tlock", which a plain hash-output beacon isn't built for.

## Proposed and evaluated, not built

- **High-value wholesale settlement / interbank RTGS batching** (proposed
  2026-07-23). Idea: batch high-value interbank transfers into 10-minute
  blocks, use the beacon to shuffle/clear them, eliminating front-running.
  Evaluated as a poor fit:
  - RTGS (CHAPS, Fedwire) exists specifically to settle transactions
    individually and immediately, precisely to avoid the systemic risk of
    a batch not fully clearing before a participant fails. Batching
    reintroduces the exact risk RTGS is designed to eliminate.
  - Scale/trust mismatch: real interbank settlement requires central-bank
    oversight, audits, and legal frameworks far beyond a single-maintainer,
    unaudited PoC chain.
  - The front-running/MEV framing doesn't map cleanly - MEV is a public
    mempool/order-book problem; interbank transfers aren't typically
    visible to other banks before settlement in the first place.

- **Time-locked interbank escrow / treasury bond auctions** (proposed
  2026-07-23). Idea: banks submit encrypted sealed bids, decryption tied to
  a future block height, preventing early leaks or late/backdated bids.
  Better conceptual fit (this is genuinely the timelock-vault pattern), but
  the pitch overstated the guarantee: it described true cryptographic
  timelock encryption ("bids automatically unpack the exact moment miners
  solve block X"), which is not what the current beacon provides - see the
  timelock vault caveat above. What it *can* honestly support: normal
  encryption keeps bids private regardless of timing, and the beacon makes
  the reveal moment itself unpredictable in advance and verifiable after
  the fact, so a late bid can't be disguised as an early one. The
  "operator could technically peek early and just not tell anyone" gap
  remains open under the current design.

- **Randomised AML/compliance audit selection** (proposed 2026-07-23, then
  corrected). Idea: banks pick which flagged transactions get a secondary
  compliance review by seeding a deterministic selection from the beacon
  value of a target block, so no internal actor can bias which accounts get
  audited. Best conceptual fit of the three proposed so far - this is
  exactly the sortition-selector pattern already built and proven. First
  draft of the pitch had two factual errors, corrected in the second pass:
  - Claimed the beacon makes manipulation "mathematically impossible" -
    corrected to the actual model: economically discouraged and bounded
    (biasing it needs controlling multiple consecutive blocks in the
    window, each forfeiting a real block reward and risking being
    orphaned), not literally impossible.
  - Claimed the audit roster is proven via a "Zero-Knowledge Proof" -
    corrected: nothing here is zero-knowledge (which proves a statement
    without revealing the underlying data). This is the opposite - full
    public verifiability, where anyone can recompute the exact same
    selection from openly published inputs.
  - Real dependency correctly identified in the corrected version: this
    only neutralises a corrupt insider if the chain's hashrate is genuinely
    external to the bank. A bank's own small private deployment could be
    dominated by that same insider with enough resources, collapsing the
    guarantee.
  - Minor unresolved detail: "the block mined exactly at midnight" needs
    the same real-time-trigger scheduling the raffle demo uses (wait for
    the clock time, then take whatever height is current), since blocks
    aren't scheduled to timestamps.

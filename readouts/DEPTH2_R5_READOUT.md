# JOURNEY 11.5 — depth-1 vs depth-2 on the R5 ladder committee, off Foul Play @20

Committed provenance. `results/` is gitignored, so this file plus
`scripts/depth2_r5_readout.py` are the only record that survives losing
`results/depth2_r5/`. Pre-reg: `configs/eval/depth2_r5.yaml` (registered
2026-09-16 at be0d7a3, before any arm ran; δ pinned mechanically at 3eb232b).

```
bash scripts/depth2_r5_queue.sh          # server up; phase S ~1 h, phase R ~14 h
python scripts/depth2_r5_readout.py
```

**Both Foul Play @20 disclosures travel with every number here, forever: the
equivalence test is weakly powered, and the point estimate flatters us. FP@20
is an INSTRUMENT, not a rung, and nothing here projects to the ladder.**

## The verdict in four lines

1. **Depth-2 is a NULL at matched override rate: −0.0007 ± 0.0128 (0.05 se),
   n=3000 per arm, for 3.27× the compute.** It does not clear the credit line
   and does not come close.
2. **The apparent depth effect in every earlier read was an OVERRIDE-RATE
   effect.** The same depth-2 arm at the naive δ reads −0.053 at 3.34 se —
   which anyone would write up as "depth hurts, significantly". Only δ moved.
3. **Search of either depth is a null against the greedy committee**: −0.006
   (0.38 se) at depth 1, −0.007 (0.43 se) at depth 2.
4. **A null here may NOT retire MCTS.** This tested ONE vehicle — the matrix
   family's selective ply — and the scope limit saying so was written into the
   pre-reg before the arms ran. See "The ruling this owes the maintainer".

## Phase S — the δ sweep (the experiment that had never been run)

`docs/search_relook/DEPTH_IS_THE_UNTESTED_AXIS.md` closes with: *"Nobody has
swept delta for depth 2-3. That sweep is the cheap first step before any
engine-native depth-2 build, and it is the one experiment on this axis that has
not been run."* This is it. **No win rate from phase S is a read** — at n=60
its se is 0.065.

| cell | depth | δ | override rate | ms/decision | decisions/s | ply fired | grandchildren/dec |
|---|---|---|---|---|---|---|---|
| S1A | 1 | 0.10 | **0.0723** | 87.9 | 11.38 | — | — |
| S1B | 1 | 0.20 | 0.0208 | 84.8 | 11.79 | — | — |
| S1C | 1 | 0.35 | 0.0005 | 81.5 | 12.27 | — | — |
| S2A | 2 | 0.10 | **0.1349** | 269.0 | 3.72 | 1.000 | 893 |
| **S2B** | **2** | **0.20** | **0.0629** | 270.0 | 3.70 | 1.000 | 888 |
| S2C | 2 | 0.35 | 0.0169 | 271.9 | 3.68 | 1.000 | 894 |
| S2D | 2 | 0.50 | 0.0073 | 259.5 | 3.85 | 1.000 | 846 |

**At the same δ the extra ply overrides the policy 1.87× as often** (13.5% vs
7.2%). That is the confound, measured on the axis the read runs on. Rule R1
then picked S2B's δ=0.20 mechanically, reading `search/override_rate` and
nothing else; realized rates in the read came out 6.8% vs 6.2%, a 0.6-point gap
against a 2-point threshold fixed before any depth-2 cell existed.

Note also that **cost is flat in δ and 3.2× in depth.** The gate changes how
often the search is *believed*, not how much it costs.

## Phase R — the read

| arm | depth | δ | override | win rate | n | ties | ms/dec | wall |
|---|---|---|---|---|---|---|---|---|
| **D1** | 1 | 0.10 | 0.0682 | **0.5687** | 3000 | 1 | 81.7 | 2.54 h |
| **D2M** | 2 | 0.20 | 0.0620 | **0.5680** | 3000 | 0 | 267.3 | 7.27 h |
| D2N | 2 | 0.10 | 0.1626 | 0.5160 | 1500 | 1 | 266.1 | 3.84 h |
| G0 | greedy | — | — | 0.5747 | 1500 | 1 | — | 0.66 h |

Mean turns 29.0–30.4 across all four, so the arms played the same game.

### PRIMARY — depth-2 vs depth-1, matched override rate

**0.5680 − 0.5687 = −0.0007, se_diff 0.0128, 0.05 se.** The floor (≥ +0.025)
fails and 2·se_diff fails. **NOT CREDITED.**

se_diff is the pooled binomial; the **seed-clustered half is UNAVAILABLE by
construction** — one committee, one arm per cell, no per-seed replicates — so
the binomial governs and is **anti-conservative**. That was disclosed in the
pre-reg header, not discovered here.

**Cost, which JOURNEY 11.5 requires reported with the verdict:** 81.7 ms →
267.3 ms per decision, **3.27×**; 12.24 → 3.74 decisions/sec. The exit
condition's own words: *"a gain that costs 5× is a different finding than the
same gain at 1.5×."* There is no gain at 3.3×.

### SECONDARY — the override-rate confound, and it is the finding

| comparison | delta | se | |
|---|---|---|---|
| depth-2 **matched** (δ 0.20) − depth-1 | **−0.0007** | 0.0128 | 0.05 se |
| depth-2 **naive** (δ 0.10) − depth-1 | **−0.0527** | 0.0158 | **3.34 se** |
| depth-2 matched − depth-2 **naive** | **+0.0520** | 0.0158 | **3.30 se** |

**Same depth. Same object. Same dose. Same evaluator. Same opponent. Only the
gate's δ moved — and the win rate moves 0.052 at 3.3 se.**

A deeper backup has a wider value spread, so a δ calibrated at one ply lets
2.4× as many overrides through, and every extra override is our critic vetoing
the policy in a position it was never trained to judge. The repo half-suspected
this at depth 3 vs SimpleHeuristics (−0.094 naive → −0.017 matched, n=600); it
is now confirmed at depth 2, on the unsaturated axis, at n=1500/3000.

**Consequence for the record: every depth number this project has published
before 2026-09-17 compared arms that differed in how often the search was
allowed to speak, not in how deep it looked.** The licensed reading of all of
them is "no evidence about depth", which is what `docs/landmines.md` already
says and now has a measurement behind it.

### SECONDARY — does search of ANY depth beat the greedy committee?

**No, and it does not lose either.** D1 − G0 = **−0.0060 (0.38 se)**; D2M − G0
= **−0.0067 (0.43 se)**. G0 is n=1500, so this cell cannot resolve anything
under ~0.032; both deltas are far inside that.

### SECONDARY — the session offset, and why G0 was worth its 40 minutes

G0 (greedy committee, **this** session) **0.5747** against the banked E3WF
**0.5987** (n=3000, 2026-09-15): **−0.0240 at 1.54 se**, for the *same frozen
checkpoints*. Yesterday's BC-clone leg measured the same shape on a different
instrument (+0.0140 between sessions on an unchanged object).

So the −0.030 gap between D1 and the banked greedy number, which looked like
"search costs three points", decomposes into **~0.024 of session and ~0.006 of
search**, neither significant. Without a same-session anchor this readout would
have reported a search penalty that does not exist.

## R0 gates

All pass, with two disclosures carried rather than waived:

- **G_FIRED**: every depth-2 arm fired the extra ply on **100%** of searched
  decisions, ~890 grandchildren each. 2026-09-11's VOID probe printed 0.8400
  having fired on *none* of 1572 decisions, which is why this gate exists and
  why the counter is now stamped on both the vs-SH and off-FP paths.
- **G_DOSE**: dose M on every arm, leaves 343 ± 20% — but `search_dose` itself
  was not stamped into off-FP reports until 2026-09-17, so for these arms the
  leaves band is the direct evidence and the dose is **UNVERIFIABLE from the
  artifact**. Disclosed, not waived.
- **G_SERIAL**: D1 and D2N report `max_concurrent_live_battles: 2`. A max
  cannot tell one transient at a battle seam from real parallel play, and three
  banked monster-read arms carry the same 2 — **E3WF among them, the number
  that picked the R5 ladder object**. The discriminator here is compute share:
  D1's own search time is **85.0%** of its wall clock and D2M's is **96.2%**,
  and genuinely overlapping play would exceed 100%. The seat now counts
  concurrent decisions so the next arm answers this directly.
- **G_OBJECT** and **G_BUDGET**: the three pinned committee members and 20 ms
  on every arm.

## The ruling this owes the maintainer

JOURNEY 11.5's exit condition says: *"Doesn't credit → the MCTS question closes
permanently; write up the substitution result and move on."*

**This readout declines to close it, and the reason was pre-registered.**
`docs/search_relook/DEPTH_IS_THE_UNTESTED_AXIS.md` §3 named the trap before any
of this ran: *"a null on EXHAUSTIVE depth-2 — a different algorithm, with a
different cost curve … — would retire MCTS having never tested it. That is the
PRE-D5 failure shape: a null from the wrong configuration closing a question
permanently."* It asked for a maintainer ruling to **decouple the stop rule**,
and that ruling has not been given.

What this file tested is the **matrix family's selective ply**.
`rl/search/tree.py` — decoupled UCT, our policy as the PUCT prior, our critic at
the leaves, mean simulation depth ~3 — is a different algorithm, and until
2026-09-17 it could not even be run off Foul Play because the seat dropped the
kwarg (fixed at 4441e30).

**And the confound finding raises the bar for closing anything.** The evidence
that made MCTS look unpromising was a set of negative depth numbers that this
readout has just shown to be override-rate artifacts. Closing MCTS on that
basis would be closing it on an artifact.

**The live hypothesis, and it is now testable.** Foul Play converts compute
into strength with a 202-line, 30-constant heuristic, consumed as
`sigmoid(0.0125 × (evaluate(leaf) − evaluate(root)))` — a *difference from the
root*, so any constant bias cancels, and the *same function everywhere*, so a
deeper tree asks it no harder a question. Our critic was fit by PPO only to
states our own policy reaches. That evaluator is now ported, verified against
hand-computed values from the Rust, and wired as a search vehicle (4ee66e0), so
"is it the evaluator?" is one pre-reg away from being answered instead of
argued.

## Barred on these numbers (the pre-reg's machine-readable list)

- "search does not pay for this project"
- "depth hurts" — **measured false at matched override rate**
- "monotone in depth"
- "MCTS is closed / retired / not worth building"
- "depth is a null at every budget" — one dose, one budget, one vehicle
- "this generalises to the ladder"
- any comparison of a phase-S win rate against anything

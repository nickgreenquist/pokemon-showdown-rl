# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## JOURNEY POSITION — steps 3–7 DONE; **step 7.5 is NEXT and is P0** (`JOURNEY.md`)
Steps 1–2 DONE (batch credited, RESULTS §17; LADDER R4: GXE 65.2 / Glicko-1 1618 ± 25 /
Elo 1354, n=200). **THE GEN-4 CHAPTER IS CLOSED (2026-09-09).** Step 3 milestone MET
(M-YES), step 4 ran (Wang's recipe on our frozen encoder), **step 5's exit MET
(S5-MATCHED: pooled 0.8788 vs SH ≥ the ruled floor 0.756, one-sided)**, step 6's ladder
is BANKED NOT RUN (ruled 2026-09-06), step 7 is this readout (RESULTS §19).
**Everything from here is gen 1, and 7.5 — the pkmn/engine collector port — comes first.**

## The gen-4 result (2026-09-09; full account RESULTS §19, provenance readouts/GEN4_WANG50M_READOUT.md)
- **PRIMARY vs SH, locked protocol, 3×3000, greedy: pooled 0.8788** (0.8873 / 0.8720 /
  0.8770). n_eff 3000×3; `win_rate` == `wins_from_returns` on every lane; ties 0.5–0.9%
  as non-wins; mask_desyncs 0. se binomial 0.00344, seed-clustered 0.00452 — **the band
  reads 0.00452**; +0.1228 over the floor = 27.2×. **ONE RUNG IS WORTH ±0.02.**
- **M-YES** (≥ 0.60) and **S5-MATCHED** (≥ 0.756), both off the header. **CREDITS NOTHING** —
  no lever, no credit line; "matched" is the only permitted strength word, and it carries
  D-DOSE (2/3), D-IMPL, D-NET, D-ACT, D-ENC, D-COLL, D-SH, D-TIE in the same sentence.
- **Anchors** (descriptive, never verdict inputs): MDT h2h 0.902 · FP@20 h2h 0.293 (budget
  named; weakly powered; flatters us) · FP@500 h2h 0.264 (pin: 20 ms) · clone(FP@20) h2h 0.985.
  Sanity: MDT-vs-SH 0.400, clone-vs-SH 0.464, FP@20-vs-SH 0.904, FP@500-vs-SH 0.912.
- **S-SHAPE** climbs through 25M (0.8277 → 0.8800, +0.0523); the six rungs from 25M span
  0.017, inside one rung's ±0.02 → not distinguishable from flat at this n and k.
  Sub-50M rungs sit on the 50M anneal and are not comparable to a finished run.
- **Gates: every one PASS ×3 lanes.** D-A EXACT to 1e-12 at 5M/25M/50M (u=2504, lr
  2.182058e-06). D-B medians 202/198/197 against an **expected 203 (never 212)**.
  D-C not actionable; D-D ≈ 0.5 by construction at pool_size 1. Stalls 0; resumes
  s216 ×3, s200 ×1, s208 ×1. Harvest ratio 0.901–1.059, version_lag_max 1.

## Next actions
1. **JOURNEY 7.5 — the pkmn/engine collector port. P0, starts now** (the box is idle and
   the readout is written, which was its precondition). Gates B-0/B-1/P-4/P-3/P-1/P-2
   already PASS on branch `pkmn-engine-port` (worktree `../pokemon-showdown-rl-engine`);
   **D-1, T-1 (+ a fleet-width T-1(d)) and A-1 remain and all need the idle box.**
   T-1 must report `collect_sec`/`update_sec`, not only steps/s.
2. **A-1 pre-reg is drafting in that worktree** and owes the maintainer a `rulings_wanted`
   list: at k=3, σ_seed ≈ 0.0617 gives se_diff ≈ 0.050, so a ±0.025 equivalence band is
   ~0.5 se — A-1 as specified is a GROSS-BREAKAGE SCREEN, not an equivalence test. The
   candidate escape is reusing historical 12M async finals as the baseline arm; four
   live in `../pokemon-showdown-rl-d25-backup-20260815/_runs_sacred/`
   (`showdown_sp_recipe12m_s62..65`, bare `checkpoint.pt` + embedded config, no meta.yaml).
3. **Gen-4 levers, if ever, are each their own pre-reg against this baseline** — NOT the
   pool (league stays on in gen 1; `pool_size: 1` was Wang fidelity only).
4. **IDEAS after 7.5:** §4 ranked 4.1 → 4.5 → 4.3 → 4.7 → 4.2 → 4.4; new rows 2.9
   (bit-identical update wins, 4.3–6.0% of update_sec) and §5's shared trunk (19.5% of
   the epoch loop) and cross features (rung 2 of an existing spec, never run). SB3
   migration is CLOSED (§3 + docs/CLEANUP.md); `docs/research_reports/PPO_VS_SB3_UPDATE_AUDIT.md`.

## Watch items
- **vs-SH is NEVER a ladder number**; the gen-4 ladder is banked and unrun. No projection.
- Resumes SPLIT wandb history — always `merge_history.py`, then `history_merged.csv`.
- **A pgrep guard must anchor on `bin/python`, not a bare module name:** the FLEET DONE
  auto-chain matched its OWN command line and would have refused the schedule forever.
- 0.786 is Wang's NETWORK-ALONE, WEAKER cell (Fig 4.1 ≈ 0.836/0.849); dose is named first.

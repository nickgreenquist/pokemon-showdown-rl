# review_2 — repo consistency and executability
Reviewer 2 of the frozen draft `results/design_gen4_wang50m/gen4_wang50m.draft.yaml`
(byte-identical to `configs/gen4_wang50m.yaml`, verified). Scope: does the header
describe the code that will run, and can every step it names be executed as
written. Everything below was checked against source or measured on the box.

**Verified clean, so the maintainer knows what was actually checked.** Both
configs load through `load_config` (`5.8884e-5` parses as float under YAML 1.1 —
signed exponent present); every `selfplay` key is in `make.py:103-104`'s known
set; every `agent` key exists on `PPOAgent.__init__` (`lr_schedule` /
`lr_power_a` / `lr_power_b` at ppo.py:320-322, `value_clip_eps` at :319,
`trunk_kwargs` layout/item_vocab/ability_vocab reaching `EntityDeepSetsNet` at
:503-506); `hidden_sizes` is required but unread by the entity trunk, as the
comment says. `make_agent` against `fake_spaces_gen4()` gives **actor 674,763 /
critic 543,553** — the stamped numbers are right. Anneal guard (train.py:414),
harvest seam (:448, :465-476) and `attach_harvest`'s privileged/aux refusal
(ppo.py:682-692) all behave as described; async refusal is not triggered
(`collector` absent → `mode: sync`). `8 | 50,000,000` and `8 | 500,000`, so
`_vector_loop` writes `ckpt_050000000.pt` on its last iteration and the wave
script's `done_rung` glob matches; 100 rungs, 200 evals, 2,504 updates, last at
49,999,872 with 128 trailing steps — all correct. Harvest path: `old_logp`
recorded from `AgentOpponent.move_logp` (pool.py:130-144), seat 2's own outcome
via `-outcome` (showdown.py:1100), per-episode GAE with terminal bootstrap 0
(episode.py:139-194), `version` = the member's push id so lag 0/1 is right at
`push_every_updates: 1`. `battle._replay_data` is appended unconditionally in
poke-env's `parse_message`, so seat 2's cursor-based `BattleTracker`
(tracker.py:105-111) sees the full log even though it is called only at seat-2
decisions — no seat asymmetry. Every post-fleet flag exists with the spelling
used, and the gen-4 cross-play assert (eval_checkpoint.py:183) permits the clone
leg. `bash -n` passes; the 24 offline tests in my brief pass. **I found no
correctness bug in the harvest path itself.**

---

## MUST-FIX

**M1. `scripts/gen4_wang50m_wave.sh:123` — the watcher dies on a bash fatal
arithmetic error the moment a lane's process disappears.**
`rss_mb=$(( $(ps -o rss= -p "$p" 2>/dev/null | tr -d ' ' || echo 0) / 1024 ))`.
The `|| echo 0` guards the *pipeline*, whose exit status is `tr`'s (always 0), so
it never fires; a dead pid yields an empty substitution and `$(( / 1024 ))` is a
**fatal** shell error, not a failed assignment. Reproduced on the box: the same
line inside a `for` loop prints `syntax error: operand expected` and the loop's
trailing `echo` never runs — the shell exits. The line sits *before* the
`[ -n "$t2" ]` guard and runs unconditionally, so any lane that exits inside the
15 s CPU-delta window (normal completion included, ≈ 15/345 of the cycle per
lane) takes the whole wave script down; three lanes then train for days with no
stall detection, no auto-resume and no RSS/disk sampling. Fix, same place:
```
rss_kb=$(ps -o rss= -p "$p" 2>/dev/null | tr -d ' ')
rss_mb=$(( ${rss_kb:-0} / 1024 ))
```
Apply the same shape to `node_age` (line 57): a `date -j -f` failure there is the
identical fatal error inside preflight rather than a clean `PREFLIGHT FAIL`.

**M2. R0-d claims a gate that does not exist.** "actor 674,763 / critic 543,553
params (asserted at construction by `tests/test_entity_trunk_gen4.py`)". That
file's only `numel` assertions (`:205`, `:215`) pin the **gen-1** counts —
`WANT` at `:195-198` is `(626059, 494849)` / `(626059, 642305)` at obs 828.
`grep -rn '674763\|543553' tests/` returns nothing. The numbers are correct (I
constructed the agent), but nothing pins them, so a trunk-width, vocab-table or
layout change passes R0-d silently. Fix: add a construction test to
`tests/test_gen4_prereg.py` — `load_config("configs/gen4_wang50m.yaml")` →
`make_agent(cfg, SimpleNamespace(observation_space=obs, action_space=act,
num_envs=cfg.num_envs))` over `fake_spaces_gen4()`, asserting both
`sum(p.numel() …)` against `SIDE["freeze"]["params"]` **and** the literals
674,763 / 543,553 — then re-point R0-d at that file.

**M3. R0-f's "the minibatch count is exactly 39 per epoch" contradicts the code.**
`_minibatch_slices` (ppo.py:266-268) builds `range(0, B, B // 39)`. With
`B = 39·mbs + r`, `r = B mod 39 < 39`, that is **40** slices whenever `r ≥ 1`,
and at `minibatch_tail: 'keep'` the floor is 2, so a 2–38-row tail **takes a full
Adam step** z-scored over itself at the 1,024-row lr — the exact F-04 pathology
that file documents. Measured: `B=39,936 → 39` slices (the nominal, and the only
divisible case), `39,900 → 40` (tail 3 rows), `39,600 → 40` (15), `40,200 → 40`
(30), `39,961 → 40` (25). Since the union size floats with the harvest, ~37/39 of
updates get the 40th slice, so grad steps are ≈ 2,504 × 7 × 40 ≈ **701,120**, not
the header's 683,592. Fix R0-f to
"39 full minibatches plus a 0–38-row tail slice that trains under `keep`
(≈ 1/40 of grad steps; F-04, ruled) → ≈ 701k grad steps", and say it in the
`batch_size` row of the recipe table so the "= his batch_size" claim is not read
as exact.

**M4. `tests/test_gen4_prereg.py:147-150` is a vacuous assertion.**
`assert head in ("flat","plateau") or head not in TXT.replace("BARRED","") or True`
— the trailing `or True` makes it unfailable. R0-a leans on this file as its
automated half; a test that cannot fail should not be in it. Fix: delete the loop
(line 151's `'"flat" and "plateau" are BARRED' in TXT` is the real check), or
implement it properly against the sidecar's barred phrases.

**M5. L3 is not resume-safe and will silently truncate on its own timeout.**
`scripts/gen4_fp_h2h.py` has no resume path: a death costs the whole leg, so a
1.85 h/lane agent-side job violates CLAUDE.md rule 4's clause (ii). Worse,
`--timeout` defaults to **7,200 s** (`:148`) against the header's own 250 × 26.6 s
= **6,650 s** estimate — 8% headroom; on breach `asyncio.wait_for` cancels,
`timed_out: true` is stamped and the leg reports fewer than 250 battles. Fix: run
L3 as five chunks of `--battles 50` per lane, each its own `--tag`, with
`--timeout 5400`; tally by SUMMING the chunk W-L-T records, never subtracting
(the FP-runner landmine's "G2 is two tallies agreeing"); state the chunk as the
resume unit in the header. A re-run gets a fresh username pair automatically
(`:86-88` derives them from `os.getpid() % 10000`) — say so, since the
poisoned-pair landmine otherwise applies.

**M6. The L2/L3 command lines overwrite each other's evidence.**
`scripts/gen4_fp_h2h.py` writes `<out>/<tag>.jsonl`, `<tag>.summary.json`,
`<tag>.foulplay.log` with defaults `--out data/gen4_fp --tag fp_h2h` (`:149-150`).
The header's L2/L3 invocations pass neither, so all six runs (3 lanes × 2 budgets)
write the same three files and only the last survives. Fix: name
`--tag gen4w50m_s<seed>_fp<ms>` and `--seed <lane seed>` in both L2 and L3 (and
in the chunked form of M5, `_c<k>`), and `--out results/gen4_wang50m/fp/`.

**M7. D-E's box-level STOP cannot fire as written.** "free+inactive < 2 GiB AND
non-zero swapouts, 3 consecutive 5-min polls". The script logs vm_stat's
**cumulative lifetime** `Swapouts` counter (line 140); on this box right now,
with nothing training, it reads **1,127,317**. A monotone counter makes the
second conjunct permanently true, so the only live term is free+inactive. Fix:
define D-E on the swapouts **delta between consecutive polls** and have the
script log the delta (keep the previous sample in a variable), or drop the term
and say the gate is free+inactive alone.

---

## SHOULD-FIX

**S1. R0-i will fail preflight on the box as it stands.** The gate is
`reclaimable ≥ 12 GB`; the script's own expression measures **9 GB** today with
only the Showdown server up (I ran it: `27k free + 529k inactive + 22k
speculative + 11k purgeable` pages × 16 KiB ≈ 9.7 GB). The hand-over launch will
stop at `PREFLIGHT FAIL: reclaimable memory 9GB < 12GB (R0-i)` with nothing in
the header telling the maintainer what to close. Also `Pages purgeable` is a
subset of active+inactive, so the sum slightly double-counts. Fix: record the
measured idle baseline in R0-i, and either lower the bar to 8 GB with that basis
or name the pre-launch action (close the browser / other apps).

**S2. Rung size is 14.7 MB, not ~19 MB.** Measured by writing both payloads at
this config: a ladder rung (`save_checkpoint` with no extras — weights 4.87 MB +
Adam moments 9.75 MB) = **14.7 MB**; `checkpoint.pt` with the pool member =
**19.6 MB**, which is what R0-e's 19.2 MB reading was. So R0-g is 100 × 14.7 MB
≈ **1.47 GB/lane**, fleet ≈ 4.5 GB, and R0-h's "need ≈ 6 GB" is conservative.
Fix the two numbers.

**S3. R0-4 is an unnamed cell.** Every other R0 row names its action
(INVESTIGATE / KILL LANE); R0-4 says only "eval/win_rate present, in (0, 1) at
the first eval". It also uses an open interval: a fresh gen-4 policy going 0/100
vs SH at 250k steps is entirely plausible and would "breach" a healthy lane. Fix:
`present, in [0, 1)` — breach → INVESTIGATE, never KILL (a 0.00 first reading is
a weak policy, not a broken lane). The five pre-reg rules require the cell.

**S4. R0-c's corpus hash gate can pass by skipping.**
`tests/test_gen4_encoder.py:609-612` is `skipif` on `data/gen4_tapes/` (gitignored,
and E2-style cleanups delete tape/rung data). The preflight runs
`pytest ... -q >/dev/null 2>&1`, so a skip is indistinguishable from green while
R0-c claims "the two hash gates green". Both pass today (I ran `-k hash`: 2
passed). Fix: `"$PY" -m pytest tests/test_gen4_encoder.py -q -k hash 2>&1 | grep -q '2 passed' || fail "hash gates not both GREEN (R0-c)"`.

**S5. Add `tests/test_entity_trunk_gen4.py` to the preflight** (24 offline tests,
2.0 s) so R0-d and the gen-1 bit-identity pin are machine-checked at launch, not
just at commit time.

**S6. The wave script's own docstring overstates its preflight.** Line 9 lists
"seeds' run dirs absent (R0-l)" as a fatal check; the code (62-64) only logs
"will RESUME", which is correct behaviour under the RESUME-SAFE contract. Fix the
comment. Separately, the header's opening paragraph maps R0-k to "clean tree"
while R0-k's own text bundles "clean tree, docs committed, suite green — bare
`pytest tests/`", which the script cannot check (live-server tests). Split it:
R0-k1 clean tree + docs committed (script), R0-k2 bare suite green (maintainer,
before launch).

**S7. Stall-path relaunch is missing the death path's guard.** Line 133 calls
`launch "$s" resume` unconditionally; lines 92 and 114 guard on
`[ -f "$d/checkpoint.pt" ]`. `checkpoint.pt` first appears at update 4
(`SAVE_LATEST_EVERY_UPDATES`, ≈ 80k steps, ≈ 5 min solo and longer 3-wide), so a
startup wedge inside that window burns a retry on a guaranteed
`FileNotFoundError`. Fix: reuse the same guard on line 133.

**S8. Say which side owns each gate.** R0-3, R0-5, H1, K6, T2, T3, D-A, D-B and
D-C are metric gates the script does not implement; the script owns the CPU-delta
stall check, auto-resume, RSS/box/disk sampling and the completion rung. One OPS
line splitting the two, and naming how the agent reads the metric side (the
offline wandb dir per lane; R0-5 from the watch log's `latest=` field), closes
the gap — with the header's own caveat that post-resume reads go through
`history_merged.csv`.

**S9. The smoke burned its whole anneal in 3 updates, so R0-1/T2 inherit
lower-lr readings.** `configs/gen4_wang50m_smoke.yaml:46` sets
`lr_anneal_steps: 59904 == total_steps`, so x ran 0 → 1/3 → 2/3, frac 1.000 →
0.142 → 0.063: updates 2 and 3 trained at ≈ lr0/7 and lr0/16, while the fleet's
first three updates all sit at ≈ lr0. The entropy band (R0-1) and the clip_frac
expectation (T2) are thus set in a different lr regime than the one they police.
No re-run needed — state it in R0-e and R0-1/T2. For the record,
`lr_anneal_steps: 50000000` is legal in a smoke (train.py:414 permits
`>= total_steps` and its comment names `showdown_sp_recipe12m_smoke.yaml` as the
schedule-prefix precedent) and would fix comparability *and* cut R0-a's diff set
from 7 keys to 6.

**S10. D-D should name all three self-play keys.** At `pool_size: 1`, `push()`
appends a fresh `[0.0, 0]` and evicts index 0 (pool.py:193, 196-200), so
`stats[0] is stats[-1]`: `selfplay/winrate_anchor`, `selfplay/anchor_games` and
`selfplay/winrate_latest` are the same per-rollout member, and the forgetting
detector **does not exist on this arm**. D-D names only `winrate_latest`.

**S11. Harvest keys are ABSENT, not zero, when no seat-2 episode finished.**
ppo.py:1078 gates the whole block on `len(self._harvest)`, so R0-3's and H1's
"on every update" has a third state. It should never happen after update 1 at
~300 finished battles/rollout; say absence is itself a KILL, so an automated
reader has a rule.

**S12. L1's gen-4 MDT-vs-SH placement has no named instrument.**
`scripts/anchor_h2h.py:24` hardcodes `FMT = "gen1randombattle"` with no format
flag — the gen-1 0.330 reference came from there, the gen-4 row cannot.
`scripts/gen4_smoke.py --player most_damage_typed --opponent heuristics --battles
300 --tag mdt_vs_sh` reports `a_record` W-L-T (`:170`) and is the one that can.
Name it, and drop "MEASURED FROM THE TAPES" — it reads as if t0–t6 already
contain the row, and they do not.

**S13. Name `--out` on the primary instrument.** `eval_checkpoint.py` prints but
files nothing without it. The JSON carries `win_rate`, the `wins_from_returns`
cross-check, `ties_from_returns` (where D-TIE's tie rate comes from) and
`mask_desyncs` — all four are owed at readout. Add
`--out results/gen4_wang50m/vs_sh_s<seed>.json`, and the same for L1/L4.

**S14. Two more test defects.** `tests/test_gen4_prereg.py:75` asserts
`33,333,333 ≤ 50,000,001` — vacuous; line 76 is the real dose check, delete 75.
And nothing pins the frozen draft copy to the config (byte-identical today,
`diff -q` verified) although HANDOFF §2's "re-freeze the draft copy" is manual;
add `assert (REPO / "results/design_gen4_wang50m/gen4_wang50m.draft.yaml").read_text() == TXT`.

**S15. Docs the ratifying commit must move.**
- `STATUS.md:35-47`: next actions 1–3 are DONE (3a5df5b, ec39268, 66746dc,
  8afa069, 1546472); reorder to HANDOFF's REMAINING list and flip the two
  step-3/step-5 lines. The file is at exactly 60 lines (the cap), so something
  must come out — the R4 block is the natural trim.
- `open_questions.md` §0.5: item 1 says "the three descriptive anchors" and item
  7 "the third descriptive anchor", but CLAUDE.md's ruled gen-4 list is five legs
  / four descriptive. Item 5 names `configs/showdown_sp_batch50m.yaml` as the
  FORM template while this header follows `showdown_sp_100m.yaml` +
  `configs/eval/ladder_r4.yaml` per HANDOFF §2.1 — and §0.5 **outranks** HANDOFF
  in that file's own precedence order, so record the supersession.
- `encoder_requirements.md` §13: the "Not built (next)" list still carries the
  pinned hash gate, the trunk layout argument and the `eval_checkpoint.py`
  threading — all landed; the section head still reads "Nothing here is frozen:
  the tuples become a commitment only in a gen-4 pre-registration header", which
  ratification turns into a pointer at `configs/gen4_wang50m.yaml`; the "17
  offline tests" count is stale.
- `docs/IDEAS_POST_100M.md` §4.1: still describes both-seat harvest as unbuilt,
  cites the stale `showdown.py:1208`, and proposes a *different* design (harvest
  latest-snapshot rows only at `latest_prob 0.8` / `push_every 5`, drop the 20%
  historical) than what shipped (`pool_size 1` / `latest_prob 1.0`, every row,
  `harvest/version_lag_max` as the metric). Mark BUILT with 66746dc and say
  whether it remains a gen-1 lever.

**S16. Landmines — clean, with one note.** Distinct seeds with disjoint windows
and a test that scans `runs/` ✓; `nohup … &` + `$!` avoids the subshell-pid
orphan ✓; `< /dev/null` present ✓; CPU-delta stall check present ✓ (subject to
M1); no encoder env vars exported, with a warning if they are set ✓; `/timer on`
is `Gen4ShowdownEnv`'s default and no `env_kwargs` overrides it ✓; FP child
reaping comes from `gen4_fp_smoke._stop_fp`, which carries the four runner fixes
✓; resume semantics match the lane-failure rule ✓. Note: no `set -e`, so a
`launch` whose python dies instantly is logged as "launched pid N" and caught
only by the next `kill -0` five minutes later — acceptable given the retry
counter, but worth one line so nobody reads the launch line as liveness (the
launcher-liveness landmine).

---

## Verdict on executability

Every config key, guard, metric name and instrument flag the header invokes
exists with the spelling it uses; the stamped param counts, the completion-rung
name, the update/rung/eval arithmetic and the whole harvest description match the
source, and there is no correctness bug in the harvest path. But the file is not
launchable as it stands. **M1** takes the watchdog down at any lane's exit, which
turns a 2–3-day hand-over run into an unsupervised one and defeats the only
instrument that catches the alive-at-zero-CPU stall. **S1** means preflight fails
on the box's current memory state with no named remedy. **M5/M6** would truncate
or overwrite five of the six Foul Play legs the frozen post-fleet schedule
depends on. **M2** and **M3** are the two places where the header asserts things
the code does not do — a gate asserted nowhere, and a minibatch count off by one
slice in ~95% of updates — exactly the claims a pre-registration exists to make
drift-proof. Nothing I found touches the design, the thresholds, the recipe or
the freeze: M1 and S7 are two-line shell fixes, M2/M4/S14 are test edits, and
M3/M5/M6/M7 plus the S-items are header text and command lines. With those
applied — M1 first, because it is the one that costs a whole fleet — the header
describes the run that will happen and the wave script can be handed over.

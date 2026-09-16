# What's next — written 2026-09-16, for the Sunday drive

Gen-1 step 11 is closed: LADDER R5 finished **listed on the top-500** (GXE 73.9,
Glicko-1 1697 ± 25, Elo 1457 against a 1354.2 cutoff, n=200), the anchor battery
is complete, and the mechanism co-primary is in. This is the state of play and a
ranked list of what to do with the box next. **Nothing here is ratified; three
rulings are owed and they are listed at the end.**

---

## The three facts that should drive every decision below

**1. The recipe is credited, and the mechanism says it is NOT a better value fit.**
The W recipe (L2-toward-init + a 1024-wide critic) at 200M beats the 100M baseline
by +0.033 vs SH (5.6 se) and +0.046 off FP@20 (4.8 se, seed-clustered). The wide
critic's capacity is genuinely *used* — first-layer srank99 **632 of 1024** where
the 384-wide critics hold **27** and **5** — but `explained_variance` is
**0.5881 vs 0.5919**, i.e. unchanged. 2.67× the width and 126× the first-layer
rank bought **zero** extra explained variance. (RESULTS §21.)

**2. At the COMMITTEE level the 200M gain nearly vanishes.** E3W vs the 100M
committee is **+0.0150 at 2.01 se — it misses the credit floor.** The recipe gain
and the committee gain **substitute for each other rather than adding**. Since the
thing we ladder is a committee, *another fleet of the same shape buys much less
than the singles comparison suggests*. This is the strongest argument in the file
and it points away from "more of the same".

**3. Two of the three offline axes are saturated.** vs SH sits in a 0.82–0.84 band
across every recent object; the BC clone sits at ~0.94 for both fleets (+0.009 at
1.1 se — the credited recipe is *invisible* there). **Off FP@20 is the only offline
axis with headroom left** (0.50 → 0.60), and the ladder is the only external one.

---

## The ranking

### 1. JOURNEY 11.5 — depth-1 vs depth-2, on the R5 committee. **Do this first.**

It is literally the next step in the arc, it needs **no training at all**, and it
is *unanswered*: every depth number this project has measures the **broken
pre-D5 selector**, and the repo has already ruled that such numbers may not be
used to argue depth does not pay. The D5 margin gate turned −0.035 into +0.042 on
the same critic. Depth was re-opened on 2026-09-11 and nobody has re-closed it.

Why now is the right time and not earlier, in the JOURNEY's own words: *"if search
substitutes for a deficient value head, the honest test is against our best
critic, after the special sauce and the massive train."* We now have that critic,
and — from fact 1 — we know something new about it that makes the test sharper:
**its explained variance is pinned at 0.59 no matter how much capacity we give
it.** If depth pays against a critic that cannot be improved by capacity, search
is the substitute for the value function's irreducible error, which is exactly the
finding step 14 and the gen-9 MCTS decision hang on.

- **Cost:** hours, not days. Engine-native depth-2 (384-byte clones, `-Dchance`
  builds) plus the existing D5 gate. No fleet, no ladder exposure.
- **Decides:** whether gen-9 gets MCTS (step 13) and whether step 14 is real.
- **Exit condition already written:** one comparison against the credit line,
  reporting decisions/sec for both arms — *"a gain that costs 5× is a different
  finding than the same gain at 1.5×"*. No depth-3; ambiguity is the answer.

### 2. The critic **LayerNorm** arm — the cheap test of the mechanism we just measured

`ctx_layernorm` was built 2026-09-12, is an exact no-op when off, and has never
run. The mechanism read hands it a much stronger prior than it had: the 384-wide
critics **collapse in their first layer** (the 100M baseline keeps *five*
significant directions out of 384) and LayerNorm is precisely the intervention the
plasticity literature names for that — BRO calls it the essential component,
Juliani & Ash's best on-policy combination carries it.

**The question is not "does LayerNorm raise the win rate" — it is "does LayerNorm
buy the wide critic's mechanism at 384 width".** That matters because width is not
free: the W lanes took **46.3 h against L2LAM's 38.7 h**, ~20% more wall clock for
3.7× the critic parameters. If a LayerNorm'd 384 critic holds first-layer rank the
way the 1024 one does, we get the credited recipe cheaper and the next fleet is
wider in *seeds* instead of in *parameters*.

**And this is the rule-6-legal way to run it small.** A 50M A/B cannot resolve the
win rate and its null would be worth nothing — but a 50M run absolutely *can*
resolve the **mechanism**: srank99 and dormancy at matched rungs are direct
measurements, not underpowered dose comparisons. Run it at 50M, read the
mechanism only, and let the win-rate question wait for a full fleet if the
mechanism says go. **Do not let anyone quote a 50M win rate from this arm.**

- **Cost:** ~12 h for a 2–3 lane 50M mechanism read.
- **Decides:** the *shape* of the next fleet — parameters or seeds.

### 3. More W-recipe members (a wider committee at 200M)

Known-positive and low-risk: the member curve vs SH runs 0.789 → 0.817 → 0.827 →
0.828 → 0.836 → 0.844, and off FP@20 adding *non*-W members **hurt** (E6MF 0.576
against E3WF 0.599), so any new members must be W-recipe. But fact 2 caps the
prize: the committee and the recipe substitute, so a 6-member W committee is
unlikely to be +0.06 over a 3-member one.

- **Cost:** ~46 h for three more lanes 3-wide.
- **Do it only if** item 2 says width is the wrong axis and you want a straight
  strength gain before the write-up.

### 4. 300M — **the weakest of the three fleet options on current evidence**

Three things argue against it, and none of them is a small-run null. The horizon
was already measured to be the *weaker* lever vs SH (ENS3 of the 50M finals
0.82233 against the 100M committee's 0.82356). W's explained variance **decays**
through the second 100M (0.675 at 100M → 0.647 → 0.596 at 200M) while its vs-SH
number only moves +0.033. And fact 2's substitution applies again at the committee
level. ~70 h/lane for the least-supported axis.

### 5. Cheap add, worth a day: **is EV 0.59 the irreducible ceiling?**

Fact 1 leaves an obvious question. Gen-1 random battles carry enormous outcome
variance — crits, para, freeze, sleep — so some fraction of return variance is
simply unlearnable. If ~0.4 of it is RNG, then **0.59 is not a plateau, it is the
ceiling**, the critic is *finished*, and every future lever belongs on the policy,
the search or the targets. Measure it directly: replay identical states many times
and decompose outcome variance. It is offline, it is cheap, and it would retire a
whole class of future critic work — or reopen it.

---

## The three rulings owed

**R-1 — LADDER R6's SPLIT SCHEDULE** (`docs/CLEANUP.md` item L1). R5's 200 battles
came from **102 distinct opponents; 63.5% were rematches and five accounts supplied
34.5% of the run**. Both adaptation tests came back null, so this is not a
contamination claim — it is that **Glicko counts 200 independent games and the
effective sample is smaller**. The proposal is to replace "ONE CONTINUOUS RUN"
with a pre-registered schedule across different hours and days. **It needs its own
stopping rule, because rd GROWS between sessions** and R5's rule (`rd ≤ 40 AND
n ≥ 200`) was written for one sitting. Not applied retroactively to R5.

**R-2 — the LR-ANNEAL FLOOR.** [RWL-4] says a ruling is owed either way and lays
out both sides: per-update `approx_kl` reaches ~1e-6 and `clip_frac` 0 in the
final rungs (the tail moves the policy almost nothing), against frozen rung evals
showing the 85M→100M segment as the **steepest** on the whole curve. One new
datum from the mechanism read, offered as evidence rather than an argument: **W's
explained variance falls through the annealed tail** (0.675 → 0.596). That is
consistent with a critic chasing a policy that is still moving, and equally
consistent with a critic going stale as its learning rate dies. It does not settle
the ruling; it says the tail is not inert.

**R-3 — the NEXT FLEET'S SHAPE.** Answer it *after* item 2, not before. The
mechanism read has changed the question from "how much width" to "is width the
cheap way to buy this at all".

---

## Where this leaves the JOURNEY

**11 is done.** Next is **11.5** (depth, item 1 above), which gates the gen-9 MCTS
decision. **11.6** (the attention/transformer trunk) is explicitly post-ladder and
explicitly does **not** block **12** (wrap the story). So the shortest honest path
to a finished story is **11.5 → 12**, with items 2–5 as optional strength work
that the story does not wait on.

One thing worth saying plainly for the write-up: the headline is not the Elo. It is
that **a pure self-play agent with no human data in training sat on the public
gen-1 ladder's top-500 list at the end of a 200-game run**, and that the project
can say exactly which parts of its recipe are credited, which are descriptive, and
which are measured *not* to work the way they look like they work.

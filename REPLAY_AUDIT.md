# Overnight replay audit — 2026-08-25

Answering "look through real game logs, find obvious issues, find patterns."
**Nothing was acted on.** No encoder change, no policy change, no config
change. The ladder ran untouched throughout.

Scope: 39 rated ladder battles / 56 replays, ~1,500 of our decisions and a
matching ~1,500 from the humans on the other side. Tooling in
`scripts/replay_audit/`, all read-only, all re-runnable.

---

## The headline, and it is not what I expected

**We pick the highest-damage move more reliably than our human opponents do.**

| damage efficiency (chosen ÷ best available) | us | humans |
|---|---|---|
| mean | **0.939** | 0.922 |
| picked the optimal move | **78.4%** | 77.3% |
| severe errors (<0.5 of best) | **1.8%** | 5.3% |

Restricted to fair comparisons only: same damage category (so the
attack/defence ratio cancels), no boosts up, and only moves the generator
*always* grants or that were revealed in that battle.

**And move choice is not what is costing us games.** Efficiency in battles we
won was 0.947; in battles we lost, 0.935. A gap of +0.012 does not decide
games. Whatever separates our wins from our losses, it is not this.

So the issues below are real, and they are worth fixing, but the framing
"the agent doesn't understand types" is not supported by the data.

---

## What actually separates wins from losses

| per battle | in wins | in losses |
|---|---|---|
| **opponent Elo** | **1227** | **1337** |
| our mons fainted | 3.18 | 6.00 |
| crits we took | 1.68 | 3.35 |
| crits we landed | 2.45 | 2.29 |

Opponent rating is the clean signal and behaves exactly as it should.

The crit gap survives normalisation, which I did not expect it to. Crits are
partly endogenous — losing means more turns spent being attacked — so I
recomputed as a **rate per attacking move**:

| crit rate | landed on us | landed on them |
|---|---|---|
| all 39 battles | 12.5% | 12.4% |
| in our wins | 10.2% | 12.8% |
| in our losses | **14.8%** | 11.9% |

Net-neutral across the run (12.5 vs 12.4 — we are not being cheated), but
sharply split by outcome. Caveat: gen-1 crit rate is a function of the
*attacker's* base Speed, so team composition confounds this, and 39 battles
is small. Still, it is one more concrete reason the raw W–L record is not a
strength measurement and GXE over many games is the right instrument.

---

## Issue 1 — zero-damage moves, and they have one signature

Nine 0× moves across 39 battles (1.50% of our damaging moves, vs 0.53% for
humans — we do this ~2.8× as often). **Eight of nine are Electric into a
Ground type.**

Classified by whether a better move was *certainly* available, by enumerating
the actual set generator:

**Indefensible — a better move was present with probability 1.0:**

| | used | had instead |
|---|---|---|
| Raichu vs Rhyhorn | Thunderbolt (~2) | **Surf (~242)** |
| Electabuzz vs Sandshrew | Thunderbolt (~2) | Psychic (~59) |
| Magnemite vs Nidoqueen | Thunderbolt (~2) | Double-Edge (~76) |
| Electrode vs Onix | Thunderbolt (~2) | Explosion (~57) |
| Weepinbell vs Gengar | Double-Edge (~2) | Razor Leaf (~29) |

Raichu is the worst single decision in the run: **Surf is in Raichu's
guaranteed kit, it is 4× on Rhyhorn, and it was passed over for a move that
does literally nothing.**

**Probabilistic (4) — Magneton ×3, Pidgeot ×1.** These are different in kind.
Magneton's *entire* guaranteed kit is Thunder / Thunderbolt / Thunder Wave —
all Electric, all 0× on a Ground type. Its fourth move is one of five, and
two of those five are Mimic/Rest. So roughly 59% of the time Magneton
genuinely has **no damaging move** against a Golem. Same for Pidgeot vs
Gengar (~78% chance it had nothing, since Double-Edge and Hyper Beam are both
Normal).

**Which relocates the bug.** In those cases the error is not the move — it is
**staying in at all.** Magneton attacked Golem with a 0× Thunderbolt on turn
10 and again on turn 14 of the same battle, with a bench available. The
question worth asking is not "why did it pick that move" but "why does it
never switch out of a matchup where it cannot deal damage."

---

## Issue 2 — repeating a move that just did nothing

Three cases (0.50% vs 0.18% for humans). The Magneton/Golem pair above is two
of them. There is no state feature saying "this move did nothing last turn",
and the policy is deterministic, so an unchanged position reproduces an
unchanged decision. Worth knowing this is structural rather than a lapse.

---

## Issue 3 — small stuff, all at or below the human rate

| | us | humans |
|---|---|---|
| dominated move (>2× better available) | 3.49% | **7.31%** |
| Hyper Beam into a healthy foe (wastes the recharge) | 2.33% | **4.10%** |
| Explosion / Self-Destruct | 1.16% | 1.60% |
| status onto an already-statused foe | 2 | 0 |
| type-immune status move (Thunder Wave into Ground) | 1 | 0 |
| heal at >85% HP | 1 | 1 |
| boost move below 25% HP | 1 | 0 |

Nothing here is a pattern. The two status-onto-statused and the one immune
Thunder Wave are single incidents.

---

## Switching looks healthy

| | us | humans |
|---|---|---|
| switch rate | 22.3% | 25.7% |
| switched into a ≥2× hit | 8.8% of switches | 9.7% |
| double-switch churn | 10 | 36 |

We switch slightly less than humans, walk into super-effective hits slightly
less often, and thrash far less. This is not a weak area — which makes the
never-switching-out-of-a-dead-matchup pattern in Issue 1 more specific than I
first read it: it is not that the agent won't switch, it is that a 0×
matchup in particular doesn't trigger it.

---

## Two things I got wrong, worth recording

**1. "Attacking into a resist 11 times" was correct play.** My first pass
flagged 54 decisions where the best known move was ≤0.5×. The largest cluster
— Slowpoke vs Poliwrath, 11 times — is a textbook **Amnesia sweep**: Thunder
Wave, Amnesia ×3, then Surf from 100% to 9%. Gen 1 Amnesia raises Special for
both attack *and* defence, so a resisted Surf from a boosted Slowpoke beats
an unboosted neutral move comfortably. The check ignored boosts.

The agent made 43 attacks with ≥2 boosts already up — Slowpoke 21, Poliwhirl
12, Psyduck 7, Golduck 2, Mewtwo 1. **It found a real Gen 1 strategy from
pure self-play**, and my audit called it an error. That cluster is the single
most encouraging thing in the replays.

**2. The accuracy-blindness from last night's synthetic probe is not real.**
The probe suggested the policy ignores accuracy entirely. Magneton and
Magnemite are guaranteed *both* Thunder (120 bp, 70% acc) and Thunderbolt
(95 bp, 100% acc); Thunderbolt is the better expected-damage move despite the
lower base power. **We chose Thunderbolt 7 times out of 7.** That is
accuracy being used correctly, against base power, in real positions. Third
finding in a row that the synthetic probe does not survive contact with a
real observation.

---

## Issue 0 — the one that matters most: we collapse in the endgame

This is the strongest result of the night and it is strategic, not
per-decision. Measuring the **terminal run** — how many of the loser's mons
faint consecutively at the very end:

| | our losses | our wins |
|---|---|---|
| terminal run, mean | **2.41** | 1.57 |
| runs of ≥3 | **9 / 17 (53%)** | 2 / 23 (9%) |

Fisher exact, one-sided: **p = 0.0029.**

**When we lose, we get swept at the end. When we win, we grind it out.**

Two controls, because this is exactly the kind of asymmetry that turns out to
be an artifact:

1. **Is it just that losses are more one-sided?** No. Games are equally close
   on faint count — we take 3.59 of their six in a loss, they take 3.33 of
   ours in a win.
2. **Do our wins end early because opponents forfeit?** Seven of them do, which
   would truncate their faint sequence and shorten the terminal run
   artificially. Restricting to **played-out wins only**: losses 9/17 vs wins
   **1/11**, Fisher **p = 0.0219**. The finding survives.

**What it is not.** I expected opposing setup sweepers, and the data says no.
Boosts per battle: they got 1.48 in our wins vs 2.24 in our losses — and *we*
got more too (0.87 vs 2.00), so that is just longer games, not a mechanism.
Battles where they got ≥4 boosts: 4/23 wins vs 5/17 losses. And the mon that
closed out each collapse was **different every time** — Pinsir, Meowth,
Mr. Mime, Staryu, Nidoqueen, Mewtwo, Slowbro, Abra, Mew, one each. There is no
single threat we fail to answer.

So: a real, significant, general endgame weakness with no identified
mechanism. That is the most valuable open question the replays produced.

---

## Status-move profile, for reference

| | us | humans |
|---|---|---|
| Thunder Wave | 40 | 37 |
| Sleep Powder | 26 | 18 |
| Amnesia | 25 | 24 |
| Recover | 22 | 10 |
| Softboiled | 11 | 24 |
| Hypnosis | 10 | 25 |
| **total status moves** | **147** | **189** |

We use fewer status moves overall and lean differently — more Sleep Powder and
Recover, much less Hypnosis and Softboiled. Nothing here is obviously wrong; it
is recorded because a style difference from the human field is worth knowing
before anyone reads style into a ladder number.

---

## What I would look at next, in order

1. **The endgame collapse (Issue 0).** Significant, survives its controls,
   no mechanism identified, and it is about *games* rather than *decisions* —
   which is where the evidence says our losses actually come from.
2. **Why a 0× matchup doesn't trigger a switch.** The one per-decision pattern
   with a clear signature and a concrete repro (Magneton vs any Ground type).
   It also subsumes several of the "wrong move" cases, since for Magneton
   there was no right move.
3. **Whether the critic is flat across those actions.** These are not states
   where the agent cannot see the type chart — the probe and the live
   diagnostic both say the feature is present and used. So the question is
   whether the value function distinguishes the outcomes at all, which is a
   different instrument than anything run so far.
4. **Nothing about accuracy, base power, or the encoder's type features.**
   Three independent measurements now say those are working.

## Caveats that bound all of the above

- **n = 39 battles.** Every rate here has wide intervals; the 2.8× on 0×
  moves is 9 events against 3.
- **PP is invisible in replays.** A flagged decision whose better move was
  exhausted is a false positive. Hydro Pump and Blizzard have 5 PP.
- **Movesets are a lower bound** except where the generator guarantees them,
  so dominated-move counts undercount.
- **The damage model ignores the attack/defence ratio.** Same-category
  comparisons are unaffected and are what the efficiency table uses.
- **Both sides run through the same parser with the same bugs**, which is the
  point — the comparison is more trustworthy than either absolute number.
- **Two of my own bugs were caught by plausibility-checking the output**, not
  by the code: an early endgame pass reported "we took 9.59 of their 6 mons",
  which traced to indexing the protocol field one position off. Any number
  here that looks impossible probably is — the scripts are new tonight and
  have not been through a review.

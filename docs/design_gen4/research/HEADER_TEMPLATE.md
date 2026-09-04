# <Title of the doc>

> **design_gen4 status header (mandatory, verbatim structure).**
> Written 2026-09-03 on branch `gen4-design`, DOCS ONLY — nothing under `rl/`
> changed. **Arc position:** the target is JOURNEY step 3 (gen4 encoder +
> model). This design work is **maintainer-ruled PREPARATION running AHEAD of
> step 2 (gen1 ladder #3)**, done while the maintainer-ordered, off-arc 100M
> fleet runs; it is not a pre-registration and it launches nothing.
> **Verification status per claim** — every claim below carries exactly one tag:
> - `[tree]` **tree-verified** — checked against a file in this repo
>   (`rl/`, `scripts/`, `configs/`, `tests/`, docs) or the vendored
>   `showdown/` data/sim: the game as we actually run it.
> - `[src]` **source-verified** — checked against an external primary source
>   on disk: installed poke-env 0.15.0, Wang's fork diffs / thesis PDF, the
>   H&L PDF / metagrok clone, ps-ppo, foul-play, the Metamon PDF.
> - `[lit]` **literature-only** — a secondary write-up, a web page, or the
>   prior-work index, not re-checked against a primary here.
> - `[live]` **needs-live-verification** — only a running server or a battle
>   can confirm it; BARRED until the 100M fleet AND its frozen post-fleet eval
>   schedule complete; the exact check is stated beside the tag.
> **Sources read for this doc:** <path list with line ranges / pages>.
> **Feeds / depends on:** <the other design_gen4 docs this one uses or serves>.
> **Reconcile at merge:** <anything designed against an interface the
> `audit-fixes` branch (F-08 EncoderSpec seam) has not landed yet>.

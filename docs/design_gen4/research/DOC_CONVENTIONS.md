# Writing conventions for docs/design_gen4/*.md (binding for every drafter, synthesizer and reviser)

1. Open with the status header from HEADER_TEMPLATE.md, filled in. Every claim carries exactly one
   of [tree] [src] [lit] [live]. A [live] tag names the post-fleet check. A number without a tag
   and a citation is a defect.
2. Cite precisely: `path:line` for files (repo paths relative to the repo root; external paths
   absolute), `p.N / Table X / Fig Y` for PDFs, the entry date + line for SESSION_LOGS. Never
   invent a citation; if a research note did not read it, say "not read".
3. When two research notes disagree, show BOTH positions with their citations and say which has the
   stronger verification status and what settles it. Do not silently pick one.
4. Repo rules that govern any number quoted here (CLAUDE.md): vs-SH numbers are NEVER ladder numbers
   and are never projected in either direction; the ~40% GXE conversion is RETIRED; every FP@20
   number travels with its two standing disclosures (weakly powered equivalence test; the point
   estimate flatters us) and names its budget; one vs-SH rung at n=3000 is worth ±0.02; anchors are
   descriptive, never verdict inputs; Wang's ladder numbers describe the SEARCHED agent — his
   network-alone comparable is the vs-SH offline number; every external row is a cross-format
   extrapolation. The credit line, if restated anywhere, is verbatim: a lever is credited iff pooled
   delta >= +0.025 AND >= 2*se_diff, with se_diff the larger of binomial and seed-clustered.
5. Nothing here is measured, launched, or evaluated. No checkpoint was touched. Say so where a reader
   might assume otherwise.
6. gen1's 828-dim encoding is bit-identical and untouchable (OBS_DIM landmine); the gen4 encoder is a
   NEW spec behind the per-gen seam. Anything designed against the audit branch's not-yet-coded
   F-08 EncoderSpec is a PROPOSAL "to reconcile at merge" and is labelled that way.
7. House style for a ruling request (open_questions.md and the encoder adjudications): the
   question; the recommendation in one sentence; the losing argument, stated at full strength, with
   what evidence would flip the ruling; what is carried to ratification; the refusal list (things
   the doc explicitly declines to decide). Imitate results/design_ch5_100m/synthesis_100m.md.
8. Prose: direct, no superlatives, no filler; short sections; tables for inventories; every table
   column with units. Headers are allowed (these are docs, not chat). No em-dashes required either
   way; keep ASCII-safe punctuation where possible.
9. Only write under docs/design_gen4/ in the worktree. Never commit (the session commits). Never
   touch STATUS.md, SESSION_LOGS.md, HANDOFF.md, README.md, RESULTS.md or anything outside
   docs/design_gen4/ (those edits would collide with the fleet session at merge; the merge
   checklist in open_questions.md carries the SESSION_LOGS entry text instead).
10. Cross-doc consistency: mechanics_delta is the authority on rules; pokeenv_gen4_survey on what the
    library exposes; encoder_requirements consumes both and must not restate a rule differently;
    anchors_and_eval consumes the SH analysis from the survey; open_questions collects every
    "maintainer ruling wanted" line from the other four verbatim (same wording, one place).

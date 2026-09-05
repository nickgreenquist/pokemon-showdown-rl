"""gen4randombattle support (JOURNEY step 3), built ADDITIVELY beside the gen-1
encoder: nothing under this package is imported by the gen-1 code paths, and
nothing here changes what gen 1 emits (the tape hash gate in
tests/test_encoder_spec.py stays the proof).

Layout:
  tape.py     - replayable protocol tapes (record on a local server, replay
                offline through poke-env's own parser) — the instrument every
                [live] claim in docs/design_gen4/ is checked with, and the
                seed of the gen-4 tape hash gate.
  vocab.py    - the frozen, forme-keyed vocabularies (species / moves /
                abilities / items) generated from the vendored gen4 pool by
                scripts/gen4_build_vocab.py (data/gen4_vocab.json).
  spec.py     - the GEN4 EncoderSpec values plus the gen-4-only layout tables.
  tracker.py  - per-battle state poke-env 0.15.0 does not track for gen 4.
  encoder.py  - embed_battle_gen4.
  env.py      - the gen-4 env classes.

Maintainer ruling 2026-09-04 (evening): gen4 groundwork starts now, ahead of
JOURNEY step 2's readout, on its own branch; training beyond smoke tests is
out of scope; gen-4 numbers stay out of the gen-1 chapter's accounting.
"""

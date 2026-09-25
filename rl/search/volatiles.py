"""The gen-1 volatile vocabulary shared by the poke_engine bridge, the shadow
battle and the harvest -- in a module with NO poke_engine import, so the
engine-side tools (gate R1-E's engine backend, the R7 write-side bridge) can
import the harvest/shadow path in an env that carries no poke_engine (rule 1:
the engine env is its own). Moved verbatim from `rl/search/bridge.py`
2026-09-23; `bridge` re-exports both names.
"""

from __future__ import annotations

GEN1_ENGINE_VOLATILES = frozenset({
    "reflect", "lightscreen", "mist", "focusenergy", "leechseed",
    "confusion", "substitute", "partiallytrapped", "mustrecharge", "bide",
    "flinch", "lockedmove", "disable",
})

# poke-env Effect name -> engine volatile name. Keys are Effect.name strings
# so the table needs no poke_env import at module load. Substitute health is
# handled separately (Side.substitute_health); the effect still maps so the
# volatile flag itself is set.
EFFECT_VOLATILE_MAP: dict[str, str] = {
    "REFLECT": "reflect",
    "MIST": "mist",
    "FOCUS_ENERGY": "focusenergy",
    "LEECH_SEED": "leechseed",
    "CONFUSION": "confusion",
    "SUBSTITUTE": "substitute",
    "BIDE": "bide",
    "DISABLE": "disable",
    "TRAPPED": "partiallytrapped",
    "PARTIALLY_TRAPPED": "partiallytrapped",
    "BINDING": "partiallytrapped",
    "FLINCH": "flinch",
}
assert set(EFFECT_VOLATILE_MAP.values()) <= GEN1_ENGINE_VOLATILES, (
    "EFFECT_VOLATILE_MAP emits a name outside the engine's gen1 enum"
)

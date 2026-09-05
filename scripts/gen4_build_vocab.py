"""Generate the frozen gen-4 vocabularies from the vendored randbats pool.

    python scripts/gen4_build_vocab.py [--showdown showdown] [--out rl/envs/gen4/data]

Reads showdown/data/random-battles/gen4/sets.json (the curated pool the
server's generator draws from, pinned at the Showdown commit stamped into
the output) plus poke-env's gen-4 pokedex, and writes:

  rl/envs/gen4/data/gen4_randbats_sets.json   byte copy of sets.json (the
                                              set prior's input; gen 1's
                                              precedent is
                                              rl/envs/data/gen1_randbats_sets.json)
  rl/envs/gen4/data/gen4_vocab.json           the four vocabularies, each a
                                              sorted list whose index+1 is the
                                              embedding row (row 0 = unknown),
                                              with the commit + sha256 stamp

Vocab rules (docs/design_gen4/encoder_requirements.md §3.4, adjudication A1):
  species   forme-id strings (`Pokemon.species`), pool-local: every pool key
            plus the cosmetic formes the generator emits by name (Gastrodon-
            East) and the battle-only formes of Forecast / Flower Gift
            (Castform x3, Cherrim-Sunshine) = 300 rows; the rule is explicit
            because poke-env's gen4 dex is not gen-filtered.
  moves     the union of every movepool, keyed on the TYPED Hidden Power id
            (`move.id` keeps `hiddenpowerfire`; `num` collapses all 17 to 237),
            plus `struggle`. `recharge` is a request placeholder, not a move.
  abilities the union of every set's `abilities`, as ids.
  items     poke-env has no item table. 17 species-forced (16 Arceus plates +
            Griseous Orb, from the dex's requiredItems / requiredItem) plus
            the 23 the generator's getPriorityItem / getItem can emit
            (showdown/data/random-battles/gen4/teams.ts, transcribed below
            with their line ranges) = 40. scripts/gen4_sample_generator.js
            is the empirical check that nothing else is ever emitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from datetime import date
from pathlib import Path

# --- the item rule table, transcribed from teams.ts @ 59da482e ---------------
# getPriorityItem (teams.ts:510-548): requiredItems | Soul Dew | Thick Club |
# Light Ball | Focus Sash | Custap Berry | Choice Scarf / Quick Powder / Sitrus
# Berry (Ditto) | Life Orb | Leftovers | Toxic Orb | Choice Band / Choice Specs
# (Trick sets) | Light Clay | Damp Rock / Chesto Berry (Rest) ; getItem
# (:550-626): Black Glasses | Choice Scarf/Specs/Band | Silk Scarf | Lustrous
# Orb | Stick | Lum Berry | Leftovers | Focus Sash | Life Orb | Expert Belt ;
# randomSet (:669-673): Leftovers -> Black Sludge on Poison types.
BATTLE_ONLY_FORMES = ("castformsunny", "castformrainy", "castformsnowy", "cherrimsunshine")

RULE_ITEMS = [
    "Soul Dew", "Thick Club", "Light Ball", "Focus Sash", "Custap Berry",
    "Choice Scarf", "Quick Powder", "Sitrus Berry", "Life Orb", "Leftovers",
    "Toxic Orb", "Choice Band", "Choice Specs", "Light Clay", "Damp Rock",
    "Chesto Berry", "Black Glasses", "Silk Scarf", "Lustrous Orb", "Stick",
    "Lum Berry", "Expert Belt", "Black Sludge",
]


def to_id(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--showdown", default="showdown")
    ap.add_argument("--out", default="rl/envs/gen4/data")
    args = ap.parse_args()
    sd = Path(args.showdown)
    sets_path = sd / "data" / "random-battles" / "gen4" / "sets.json"
    raw = sets_path.read_bytes()
    sets = json.loads(raw)
    commit = subprocess.run(
        ["git", "-C", str(sd), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()

    from poke_env.data import GenData

    dex = GenData.from_gen(4).pokedex

    # species: the 295 pool keys, plus the only two forme classes that can
    # appear mid-battle or at team generation without being pool keys:
    #   - cosmetic formes the generator emits by name (getForme samples
    #     `cosmeticFormes`; Gastrodon-East is the one pool case — measured
    #     296 distinct species ids over 120,000 generated sets,
    #     data/gen4_tapes/generator_sample_20k.json);
    #   - the battle-only formes of Forecast (Castform) and Flower Gift
    #     (Cherrim), which arrive as `detailschange` mid-battle. Every other
    #     gen-4 forme (Rotom, Deoxys, Wormadam, Giratina, Shaymin, Arceus) is
    #     fixed at generation and is its own pool key. poke-env's gen4 dex is
    #     NOT gen-filtered (megas, gmax, regional formes survive in it), so
    #     the rule is explicit rather than dex-derived.
    pool_species = sorted(sets)
    species = set(pool_species)
    for sp in pool_species:
        for cosmetic in dex[sp].get("cosmeticFormes") or []:
            species.add(to_id(cosmetic))
    species |= set(BATTLE_ONLY_FORMES)
    missing = [sp for sp in species if sp not in dex]
    assert not missing, f"forme ids absent from poke-env's gen4 dex: {missing}"
    species_list = sorted(species)

    moves = {"struggle"}
    abilities = set()
    levels = {}
    roles = set()
    n_sets = 0
    for sp, entry in sets.items():
        levels[sp] = entry["level"]
        for s in entry["sets"]:
            n_sets += 1
            roles.add(s["role"])
            moves.update(s["movepool"])
            abilities.update(to_id(a) for a in s["abilities"])
    moves_list = sorted(moves)
    abilities_list = sorted(abilities)

    forced = set()
    for sp in pool_species:
        entry = dex[sp]
        for it in entry.get("requiredItems") or []:
            forced.add(to_id(it))
        if entry.get("requiredItem"):
            forced.add(to_id(entry["requiredItem"]))
    items = sorted(forced | {to_id(i) for i in RULE_ITEMS})

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(sets_path, out / "gen4_randbats_sets.json")
    vocab = {
        "showdown_commit": commit,
        "sets_sha256": hashlib.sha256(raw).hexdigest(),
        "sets_bytes": len(raw),
        "generated": date.today().isoformat(),
        "generator": "scripts/gen4_build_vocab.py",
        "counts": {
            "pool_species": len(pool_species),
            "species_rows": len(species_list),
            "sets": n_sets,
            "moves": len(moves_list),
            "abilities": len(abilities_list),
            "items": len(items),
            "items_forced": len(forced),
            "roles": len(roles),
            "distinct_dex_nums": len({dex[sp]["num"] for sp in pool_species}),
        },
        "roles": sorted(roles),
        "species": species_list,
        "moves": moves_list,
        "abilities": abilities_list,
        "items": items,
        "levels": levels,
    }
    (out / "gen4_vocab.json").write_text(json.dumps(vocab, indent=1) + "\n")
    print(json.dumps({"commit": commit, "counts": vocab["counts"]}, indent=1))
    extra = sorted(set(species_list) - set(pool_species))
    print("non-pool forme rows:", extra)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

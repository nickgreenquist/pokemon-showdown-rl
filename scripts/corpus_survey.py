"""Price the human replay corpus before committing to the corpus chapter.

    python scripts/corpus_survey.py                 # download (once) + full survey
    python scripts/corpus_survey.py --sample 5000   # quick pass over N battles

DESIGN.md §4 Track 1 "parse-free half", checks (1)-(5). Everything here is a
measurement that can be taken WITHOUT a working replay parser, which is the
whole point of the split: the parser is days of work and §10's cost list is
long enough that we want the sizing numbers before paying for it.

Why each check exists — what decision it feeds:

(1) Upload-date distribution / recency cutoff. §10's headline "109,147
    gen1randombattle replays" is the whole 2015-2026 span. Set pools, the
    protocol, and the sim all moved across it, so the number that matters is
    the *post-cutoff* subset. §4's provisional bar is >= 50k recent-era
    replays; this check says which cutoffs clear it.

(2) `rating` nullity. §10 already flagged it as mostly null, which caps a
    behavioural clone at the mean uploader rather than the strong tail. The
    open question is whether the non-null slice is big enough to train on or
    to reweight with — and, separately, whether per-player Elo is recoverable
    from the log body when the column is null (it usually is; see the
    `|player|` and `|raw|` probes below). That changes the answer.

(3) Log length / decisions per battle. §10 asserts "plausibly 10-20M
    state-action pairs". That claim sets the storage design (§10's 25-50 GB
    embedded estimate, D7's sharded-memmap requirement) and the GPU spend, so
    it gets checked rather than assumed. Counted from spectator logs, so it is
    an upper bound on *labelled* pairs — the parser half (checks 7-8) subtracts
    the hidden-action rows.

(4) Winner extractability. The terminal reward, and the only label available
    for anything value-shaped. A log whose winner cannot be tied back to the
    `players` field is unusable for outcome-conditioned training.

(5) Set-pool coverage against the vendored `teams.ts` pool. §10's "one
    structural advantage" is that randbats sets come from a fixed public pool
    we already vendor, making hidden-team inference tractable. That advantage
    is only real for replays whose sets are still drawn from *today's* pool.
    Broken out by year because era drift is exactly what sets the cutoff in
    (1): a year whose species and moves no longer exist in the pool cannot be
    used to infer teams, however clean its protocol is.

Check (6) (Foul Play latency) is measured elsewhere; it needs a running bot,
not this parquet.

Provenance and handling: the dataset is `HolidayOugi/pokemon-showdown-replays`
on HuggingFace, pinned to REVISION below because §10 requires it — the dataset
is live and grows, and an unpinned re-download silently changes the training
set. It has **no stated license**: it lands in `data/` (gitignored), is never
committed, and does not leave the local box. Only the one `gen1randombattle`
parquet is fetched; the full dataset is 69.8 GB and we never want it.
"""

import argparse
import collections
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

REPO_ID = "HolidayOugi/pokemon-showdown-replays"
# Pinned per §10. lastModified 2026-06-20; 109,147 rows / 199,704,915 bytes.
REVISION = "bc76388c2119f8a5694adf643c640610b157ee1c"
FILENAME = "[Gen 1] RANDOMBATTLE.parquet"
EXPECTED_ROWS = 109_147
EXPECTED_BYTES = 199_704_915

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = REPO_ROOT / "data" / "corpus"
TEAMS_TS = REPO_ROOT / "showdown" / "data" / "random-battles" / "gen1" / "teams.ts"

CUTOFF_YEARS = [2018, 2020, 2022, 2023, 2024, 2025]
RATING_THRESHOLDS = [1300, 1500, 1700]
# Checks (1) and (5) answer the same question — where does the usable era
# start — and a YEAR is too coarse to answer it: the set table is retuned on
# no particular schedule, and a retune inside a year splits that year's
# replays across two different games. Months are resolved from here forward,
# which is where the level data says the interesting boundaries are.
MONTHLY_FROM = 2023

# Showdown's own toID(): lowercase, drop everything non-alphanumeric. Applied
# to BOTH sides of every species/move comparison so that display names
# ("Double-Edge", "Farfetch'd" with a curly apostrophe, "Hyper Beam") meet the
# pool's ids ("doubleedge", "farfetchd", "hyperbeam"). A normalization bug here
# would fake a coverage failure, so check (5) also prints the residual misses.
_NON_ID = re.compile(r"[^a-z0-9]+")


def to_id(text: str) -> str:
    return _NON_ID.sub("", text.lower())


def sha256_file(path: Path, chunk: int = 1 << 22) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def download() -> Path:
    """Fetch the single pinned parquet into data/corpus/ (no-op if present)."""
    from huggingface_hub import hf_hub_download

    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    path = Path(
        hf_hub_download(
            repo_id=REPO_ID,
            repo_type="dataset",
            revision=REVISION,
            filename=FILENAME,
            local_dir=str(CORPUS_DIR),
        )
    )
    size = path.stat().st_size
    if size != EXPECTED_BYTES:
        raise SystemExit(f"{path}: {size} bytes, expected {EXPECTED_BYTES}")
    return path


def load_set_pool() -> tuple[dict[str, set[str]], dict[str, int]]:
    """Today's gen1randombattle set pool: species -> legal move ids, and levels.

    `teams.ts` holds the *algorithm*; the pool itself is the `data.json` it
    `require`s. randomSet() draws from moves + exclusiveMoves + essentialMoves
    + comboMoves, so a species' legal move pool is the union of those four
    (verified against showdown/data/random-battles/gen1/teams.ts randomSet()).
    randomTeam() samples species from Object.keys(randomData), so the species
    pool is exactly this file's keys.
    """
    if not TEAMS_TS.exists():
        raise SystemExit(f"{TEAMS_TS}: missing — the showdown/ checkout is gitignored")
    src = TEAMS_TS.read_text()
    m = re.search(r"randomData[^=]*=\s*require\(['\"](.+?)['\"]\)", src)
    if not m:
        raise SystemExit(f"{TEAMS_TS}: could not find the randomData require()")
    data = json.loads((TEAMS_TS.parent / m.group(1)).read_text())
    pool, levels = {}, {}
    for species, entry in data.items():
        moves: set[str] = set()
        for field in ("moves", "exclusiveMoves", "essentialMoves", "comboMoves"):
            moves.update(entry.get(field) or [])
        pool[to_id(species)] = moves
        if entry.get("level"):
            levels[to_id(species)] = int(entry["level"])
    return pool, levels


class Survey:
    """Streaming accumulator — one pass over the parquet, everything at once."""

    def __init__(self, pool: dict[str, set[str]], levels: dict[str, int]):
        self.pool = pool
        self.levels = levels
        self.rows = 0
        self.ids: set[str] = set()
        self.dup_ids = 0
        self.formats: collections.Counter = collections.Counter()
        self.formatids: collections.Counter = collections.Counter()
        self.server_year: collections.Counter = collections.Counter()
        # Per-battle vectors (109k rows: cheap to hold, needed for percentiles).
        self.year: list[int] = []
        self.nbytes: list[int] = []
        self.turns: list[int] = []
        self.dec_p1: list[int] = []
        self.dec_p2: list[int] = []
        self.rating: list[float] = []
        # Per-year tallies.
        self.y_logelo: collections.Counter = collections.Counter()
        self.y_rawelo: collections.Counter = collections.Counter()
        self.y_win_ok: collections.Counter = collections.Counter()
        self.y_win_unmatched: collections.Counter = collections.Counter()
        self.y_tie: collections.Counter = collections.Counter()
        self.y_none: collections.Counter = collections.Counter()
        self.y_forfeit: collections.Counter = collections.Counter()
        self.y_inactive: collections.Counter = collections.Counter()
        self.y_choice: collections.Counter = collections.Counter()
        self.y_transform: collections.Counter = collections.Counter()
        # Check (5) tallies, all per-year.
        self.y_sp_obs: collections.Counter = collections.Counter()
        self.y_sp_ok: collections.Counter = collections.Counter()
        self.y_pair_obs: collections.Counter = collections.Counter()
        self.y_pair_ok: collections.Counter = collections.Counter()
        self.y_lvl_obs: collections.Counter = collections.Counter()
        self.y_lvl_ok: collections.Counter = collections.Counter()
        self.y_battle_sp_ok: collections.Counter = collections.Counter()
        self.y_battle_pair_ok: collections.Counter = collections.Counter()
        self.y_pair_skipped: collections.Counter = collections.Counter()
        self.bad_species: collections.Counter = collections.Counter()
        self.bad_pairs: collections.Counter = collections.Counter()
        # Same tallies at month resolution, MONTHLY_FROM onward (see above).
        self.m_n: collections.Counter = collections.Counter()
        self.m_lvl_obs: collections.Counter = collections.Counter()
        self.m_lvl_ok: collections.Counter = collections.Counter()
        self.m_pair_obs: collections.Counter = collections.Counter()
        self.m_pair_ok: collections.Counter = collections.Counter()
        # Pre-2019 protocol variant: |switch| omits the species field when it
        # equals the nickname. Not corruption — a parser must fall back to the
        # nickname, which randbats never sets, so it is always the species.
        self.species_from_nickname = 0
        self.has_log_elo: list[bool] = []
        # |choice| calibration for check (3): old logs carry the literal
        # submitted choice, so the move+switch heuristic can be scored.
        self.calib_battles = 0
        self.calib_choice = 0
        self.calib_heur = 0
        self.elo_values: list[float] = []

    def add_batch(self, batch) -> None:
        d = batch.to_pydict()
        for i in range(len(d["id"])):
            self.add(
                d["id"][i],
                d["format"][i],
                d["formatid"][i],
                d["players"][i],
                d["log"][i],
                d["uploadtime"][i],
                d["rating"][i],
            )

    def add(self, bid, fmt, fmtid, players, log, uploadtime, rating) -> None:
        self.rows += 1
        if bid in self.ids:
            self.dup_ids += 1
        else:
            self.ids.add(bid)
        self.formats[fmt] += 1
        self.formatids[fmtid] += 1
        when = datetime.fromtimestamp(uploadtime, timezone.utc)
        year = when.year
        month = f"{year}-{when.month:02d}"
        recent = year >= MONTHLY_FROM
        if recent:
            self.m_n[month] += 1
        # Battle ids are "<server->gen1randombattle-<n>"; "" means the main
        # ladder. Side servers and smogtours run their own (possibly stale)
        # sim, which is a distribution split worth seeing.
        self.server_year[(year, bid.split("gen1randombattle")[0] or "main-")] += 1
        self.year.append(year)
        self.nbytes.append(len(log))
        self.rating.append(float("nan") if rating is None else float(rating))

        turns = 0
        dec = [0, 0]
        choice_tokens = 0
        winner = None
        tie = forfeit = inactive = has_choice = False
        # Per-side state for check (5).
        active = [None, None]
        active_lvl = [None, None]
        tainted = [False, False]  # Transform/Mimic: moveset no longer the set's
        sp_ok = pair_ok = True
        sp_seen = pair_seen = False
        elos: list[float] = []
        raw_elo = False

        for line in log.split("\n"):
            if not line.startswith("|"):
                continue
            parts = line.split("|")
            if len(parts) < 2:
                continue
            tag = parts[1]

            if tag == "move":
                side = 0 if parts[2].startswith("p1") else 1
                dec[side] += 1
                if active[side] is None or tainted[side]:
                    self.y_pair_skipped[year] += 1
                    continue
                move = to_id(parts[3])
                if move in ("mimic", "transform"):
                    tainted[side] = True
                # [from] means the move was not chosen from the set (Metronome,
                # Mirror Move, Sky Attack's release turn) — not a set legality
                # observation. Struggle is forced, never in a pool.
                if move == "struggle" or any(
                    p.startswith("[from]") for p in parts[5:]
                ):
                    self.y_pair_skipped[year] += 1
                    continue
                self.y_pair_obs[year] += 1
                if recent:
                    self.m_pair_obs[month] += 1
                pair_seen = True
                if move in self.pool.get(active[side], ()):
                    self.y_pair_ok[year] += 1
                    if recent:
                        self.m_pair_ok[month] += 1
                else:
                    pair_ok = False
                    self.bad_pairs[(active[side], move)] += 1

            elif tag == "switch" or tag == "drag":
                side = 0 if parts[2].startswith("p1") else 1
                if tag == "switch":
                    dec[side] += 1
                details = parts[3] if len(parts) > 3 else ""
                name = details.split(",")[0].strip()
                if not name:
                    self.species_from_nickname += 1
                    name = parts[2].split(":", 1)[-1].strip()
                species = to_id(name)
                active[side] = species
                tainted[side] = False
                lvl = None
                for chunk in details.split(",")[1:]:
                    chunk = chunk.strip()
                    if chunk.startswith("L") and chunk[1:].isdigit():
                        lvl = int(chunk[1:])
                active_lvl[side] = lvl
                self.y_sp_obs[year] += 1
                sp_seen = True
                if species in self.pool:
                    self.y_sp_ok[year] += 1
                    if lvl is not None:
                        self.y_lvl_obs[year] += 1
                        if recent:
                            self.m_lvl_obs[month] += 1
                        if self.levels.get(species) == lvl:
                            self.y_lvl_ok[year] += 1
                            if recent:
                                self.m_lvl_ok[month] += 1
                else:
                    sp_ok = False
                    self.bad_species[species] += 1

            elif tag == "turn":
                turns += 1
            elif tag == "win":
                winner = parts[2] if len(parts) > 2 else ""
            elif tag == "tie":
                tie = True
            elif tag == "choice":
                has_choice = True
                choice_tokens += sum(1 for p in parts[2:] if p.strip())
            elif tag == "-transform":
                self.y_transform[year] += 1
                tainted[0 if parts[2].startswith("p1") else 1] = True
            elif tag == "player":
                if len(parts) > 5 and parts[5].strip().isdigit():
                    elos.append(float(parts[5]))
            elif tag == "raw":
                if "'s rating:" in line:
                    raw_elo = True
            elif tag == "-message":
                if "forfeited" in line:
                    forfeit = True
                elif "inactivity" in line:
                    inactive = True

        self.turns.append(turns)
        self.dec_p1.append(dec[0])
        self.dec_p2.append(dec[1])

        if tie:
            self.y_tie[year] += 1
        elif winner:
            names = {to_id(p) for p in (players or [])}
            if to_id(winner) in names:
                self.y_win_ok[year] += 1
            else:
                self.y_win_unmatched[year] += 1
        else:
            self.y_none[year] += 1
        if forfeit:
            self.y_forfeit[year] += 1
        if inactive:
            self.y_inactive[year] += 1
        self.has_log_elo.append(bool(elos))
        if elos:
            self.y_logelo[year] += 1
            self.elo_values.extend(elos)
        if raw_elo:
            self.y_rawelo[year] += 1
        if has_choice:
            self.y_choice[year] += 1
            self.calib_battles += 1
            self.calib_choice += choice_tokens
            self.calib_heur += dec[0] + dec[1]
        if sp_seen and sp_ok:
            self.y_battle_sp_ok[year] += 1
        if pair_seen and pair_ok:
            self.y_battle_pair_ok[year] += 1


def pct(num: int, den: int) -> str:
    return "n/a" if not den else f"{num / den:.4f}"


def stats(values: np.ndarray) -> dict:
    if not len(values):
        return {}
    return {
        "mean": float(values.mean()),
        "p10": float(np.percentile(values, 10)),
        "median": float(np.median(values)),
        "p90": float(np.percentile(values, 90)),
    }


def report(s: Survey, path: Path, digest: str, elapsed: float) -> dict:
    year = np.array(s.year)
    nbytes = np.array(s.nbytes)
    turns = np.array(s.turns)
    dec = np.array(s.dec_p1) + np.array(s.dec_p2)
    rating = np.array(s.rating)
    have_rating = ~np.isnan(rating)
    have_log_elo = np.array(s.has_log_elo)
    years = sorted(set(s.year))
    out: dict = {
        "source": {
            "repo_id": REPO_ID,
            "revision": REVISION,
            "filename": FILENAME,
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": digest,
        },
        "rows": s.rows,
        "duplicate_ids": s.dup_ids,
        "format_values": dict(s.formats),
        "formatid_values": dict(s.formatids),
        "survey_seconds": round(elapsed, 1),
    }

    print(f"\n{'=' * 72}\nCORPUS SURVEY — {REPO_ID} @ {REVISION[:12]}\n{'=' * 72}")
    print(f"file      {path}")
    print(f"bytes     {path.stat().st_size}   sha256 {digest}")
    print(f"rows      {s.rows}   duplicate ids {s.dup_ids}")
    print(f"format    {dict(s.formats)}")
    print(f"formatid  {dict(s.formatids)}")

    print("\n--- (1) upload year / recency cutoffs ---")
    per_year = {y: int((year == y).sum()) for y in years}
    out["per_year"] = per_year
    for y in years:
        print(f"  {y}  {per_year[y]:>7}")
    cutoffs = {}
    for c in CUTOFF_YEARS:
        keep = year >= c
        n = int(keep.sum())
        cutoffs[c] = {
            "battles": n,
            "with_rating": int((have_rating & keep).sum()),
            "with_log_elo": int((have_log_elo & keep).sum()),
            "decisions": int(dec[keep].sum()),
        }
        print(
            f"  >= {c}: {n:>7} battles  ({pct(n, s.rows)} of corpus)"
            f"  bar>=50k {'PASS' if n >= 50_000 else 'FAIL'}"
            f"   rating!=null {cutoffs[c]['with_rating']:>6}"
            f"   in-log Elo {cutoffs[c]['with_log_elo']:>6}"
        )
    out["cutoffs"] = cutoffs

    print("\n  battles by server prefix and year (side servers run their own sim):")
    for y in years:
        row = {p: c for (yy, p), c in s.server_year.items() if yy == y}
        top = sorted(row.items(), key=lambda kv: -kv[1])[:4]
        print(f"  {y}  " + "  ".join(f"{p}{c}" for p, c in top))
    out["server_year"] = {f"{y}|{p}": c for (y, p), c in s.server_year.items()}

    print("\n--- (2) rating nullity / recoverable skill signal ---")
    nn = rating[have_rating]
    print(f"  non-null `rating`: {len(nn)} / {s.rows}  ({pct(len(nn), s.rows)})")
    if len(nn):
        print(
            f"  min {nn.min():.0f}  p10 {np.percentile(nn, 10):.0f}  "
            f"median {np.median(nn):.0f}  p90 {np.percentile(nn, 90):.0f}  max {nn.max():.0f}"
        )
        for t in RATING_THRESHOLDS:
            print(f"  > {t}: {int((nn > t).sum())} ({pct(int((nn > t).sum()), len(nn))} of non-null)")
    out["rating"] = {
        "non_null": int(len(nn)),
        "stats": stats(nn),
        "above": {t: int((nn > t).sum()) for t in RATING_THRESHOLDS},
        "non_null_by_year": {y: int((have_rating & (year == y)).sum()) for y in years},
        "log_elo_battles_by_year": {y: s.y_logelo[y] for y in years},
        "raw_elo_battles_by_year": {y: s.y_rawelo[y] for y in years},
    }
    print("  year  battles  rating!=null  |player| Elo  |raw| Elo")
    for y in years:
        print(
            f"  {y}  {per_year[y]:>7}  {int((have_rating & (year == y)).sum()):>11}"
            f"  {s.y_logelo[y]:>12}  {s.y_rawelo[y]:>9}"
        )
    if s.elo_values:
        ev = np.array(s.elo_values)
        print(
            f"  in-log per-player Elo ({len(ev)} values): median {np.median(ev):.0f}, "
            f"p90 {np.percentile(ev, 90):.0f}, >1500 {pct(int((ev > 1500).sum()), len(ev))}"
        )
        out["rating"]["log_elo_stats"] = stats(ev)

    print("\n--- (3) log size / decisions per battle ---")
    print(f"  log bytes      {stats(nbytes)}   total {int(nbytes.sum())}")
    print(f"  turns          {stats(turns)}")
    print(f"  decisions/side {stats(np.concatenate([s.dec_p1, s.dec_p2]))}")
    print(f"  decisions/battle (both sides) {stats(dec)}   total {int(dec.sum())}")
    out["length"] = {
        "log_bytes": stats(nbytes),
        "log_bytes_total": int(nbytes.sum()),
        "turns": stats(turns),
        "decisions_per_side": stats(np.concatenate([s.dec_p1, s.dec_p2])),
        "decisions_per_battle": stats(dec),
        "decisions_total": int(dec.sum()),
    }
    # |move|+|switch| undercounts: a turn spent asleep/frozen/recharging still
    # took a submitted choice but logs |cant|, not |move|. Old logs carry the
    # literal |choice| line for both sides, so the heuristic can be scored
    # against ground truth and the totals scaled up. (Calibrated on the
    # 2015-2018 era only — that is the only era that logs |choice|.)
    ratio = s.calib_heur / s.calib_choice if s.calib_choice else 1.0
    if s.calib_battles:
        out["decision_calibration"] = {
            "battles": s.calib_battles,
            "choice_tokens": s.calib_choice,
            "heuristic_decisions": s.calib_heur,
            "heuristic_over_choice": ratio,
        }
        print(
            f"  calibration vs literal |choice| lines ({s.calib_battles} battles): "
            f"heuristic {s.calib_heur} vs choice {s.calib_choice} "
            f"(heuristic/choice {ratio:.4f})"
        )
    print("  cutoff   |move|+|switch| pairs   calibrated (/%.4f)" % ratio)
    for c in CUTOFF_YEARS:
        n = cutoffs[c]["decisions"]
        cutoffs[c]["decisions_calibrated"] = int(n / ratio)
        print(f"  >= {c}:  {n:>12}   {int(n / ratio):>12}")
    out["choice_line_battles_by_year"] = {y: s.y_choice[y] for y in years}
    print("  battles carrying literal |choice| lines, by year:")
    for y in years:
        print(f"    {y}  {s.y_choice[y]:>7} / {per_year[y]}")

    print("\n--- (4) winner extractability ---")
    print("  year  matched   unmatched   tie   none   forfeit   inactivity")
    win = {}
    for y in years:
        win[y] = {
            "matched": s.y_win_ok[y],
            "unmatched": s.y_win_unmatched[y],
            "tie": s.y_tie[y],
            "none": s.y_none[y],
            "forfeit": s.y_forfeit[y],
            "inactivity": s.y_inactive[y],
            "total": per_year[y],
        }
        print(
            f"  {y}  {s.y_win_ok[y]:>7}  {s.y_win_unmatched[y]:>9}  {s.y_tie[y]:>4}"
            f"  {s.y_none[y]:>5}  {s.y_forfeit[y]:>7}  {s.y_inactive[y]:>11}"
        )
    tot_ok = sum(s.y_win_ok.values())
    print(f"  overall matched: {tot_ok} / {s.rows} ({pct(tot_ok, s.rows)})")
    out["winner"] = win

    print("\n--- (5) set-pool coverage vs today's teams.ts pool ---")
    print(f"  pool: {len(s.pool)} species, {len(set().union(*s.pool.values()))} distinct moves")
    print("  year   species-obs in pool   (species,move) legal   level match   battles all-legal")
    cov = {}
    for y in years:
        cov[y] = {
            "species_obs": s.y_sp_obs[y],
            "species_in_pool": s.y_sp_ok[y],
            "pair_obs": s.y_pair_obs[y],
            "pair_legal": s.y_pair_ok[y],
            "pair_skipped": s.y_pair_skipped[y],
            "level_obs": s.y_lvl_obs[y],
            "level_match": s.y_lvl_ok[y],
            "battles_all_species_in_pool": s.y_battle_sp_ok[y],
            "battles_all_pairs_legal": s.y_battle_pair_ok[y],
            "battles_with_transform": s.y_transform[y],
        }
        print(
            f"  {y}   {pct(s.y_sp_ok[y], s.y_sp_obs[y])} ({s.y_sp_obs[y]:>7})"
            f"   {pct(s.y_pair_ok[y], s.y_pair_obs[y])} ({s.y_pair_obs[y]:>8})"
            f"   {pct(s.y_lvl_ok[y], s.y_lvl_obs[y])}"
            f"   {pct(s.y_battle_pair_ok[y], per_year[y])}"
        )
    out["coverage"] = cov
    out["top_missing_species"] = s.bad_species.most_common(25)
    out["top_illegal_pairs"] = [
        [f"{sp}|{mv}", n] for (sp, mv), n in s.bad_pairs.most_common(30)
    ]
    out["species_from_nickname_lines"] = s.species_from_nickname
    # The cutoff decision, at the resolution it actually happens. Species and
    # move pools are near-static across the recent era; what MOVES is the
    # level table, and it moves in steps, mid-year. Every step is a retune of
    # the generator we would be inferring hidden teams from, so the honest
    # "usable subset" is counted from the last step, not from a round year.
    months = sorted(s.m_n)
    monthly = {
        m: {
            "battles": s.m_n[m],
            "level_match": round(s.m_lvl_ok[m] / s.m_lvl_obs[m], 4) if s.m_lvl_obs[m] else None,
            "pair_legal": round(s.m_pair_ok[m] / s.m_pair_obs[m], 4) if s.m_pair_obs[m] else None,
            "battles_from_here": sum(s.m_n[k] for k in months if k >= m),
        }
        for m in months
    }
    out["monthly"] = monthly
    print(f"\n--- (1)+(5) era boundary, monthly from {MONTHLY_FROM} ---")
    print("  month     battles   level match   (species,move) legal   battles from here")
    for m in months:
        row = monthly[m]
        lvl = "n/a" if row["level_match"] is None else f"{row['level_match']:.4f}"
        pair = "n/a" if row["pair_legal"] is None else f"{row['pair_legal']:.4f}"
        print(
            f"  {m}  {row['battles']:>8}   {lvl:>11}   {pair:>20}"
            f"   {row['battles_from_here']:>17}"
        )

    print(f"  species observed but absent from pool: {s.bad_species.most_common(15)}")
    print(f"  top illegal (species, move): {s.bad_pairs.most_common(15)}")
    print(
        f"  |switch| lines with the species field omitted (old protocol, "
        f"species taken from the nickname): {s.species_from_nickname}"
    )
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sample", type=int, default=0, help="stop after N battles")
    ap.add_argument("--out", type=Path, default=CORPUS_DIR / "corpus_survey.json")
    args = ap.parse_args()

    path = download()
    digest = sha256_file(path)
    pool, levels = load_set_pool()

    pf = pq.ParquetFile(path)
    if pf.metadata.num_rows != EXPECTED_ROWS and not args.sample:
        print(f"WARNING: {pf.metadata.num_rows} rows, expected {EXPECTED_ROWS}")

    s = Survey(pool, levels)
    t0 = time.time()
    for batch in pf.iter_batches(batch_size=2048):
        s.add_batch(batch)
        if args.sample and s.rows >= args.sample:
            break
    out = report(s, path, digest, time.time() - t0)
    args.out.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()

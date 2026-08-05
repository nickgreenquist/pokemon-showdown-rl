"""Dump a run's W&B offline metric history to CSV for analysis.

    python scripts/extract_history.py runs/<run_name> [-o out.csv]

Accepts a run directory (finds the single wandb/offline-run-*/run-*.wandb
under it) or a direct path to a .wandb file — the latter covers runs from
before offline data colocated under the run dir. Reads the binary via
wandb's internal datastore, a private API pinned along with wandb itself.

A run killed mid-flight leaves a truncated final block; extraction keeps
every complete record and reports how far it got.
"""

import argparse
import csv
import json
import sys
from pathlib import Path


def find_wandb_file(path: Path) -> Path:
    if path.is_file():
        return path
    candidates = sorted(path.glob("wandb/offline-run-*/run-*.wandb"))
    if len(candidates) != 1:
        sys.exit(
            f"{path}: expected exactly one offline run, found {len(candidates)} "
            f"({[str(c) for c in candidates]}) — pass the .wandb file explicitly"
        )
    return candidates[0]


def read_history(wandb_file: Path) -> list[dict]:
    from wandb.proto import wandb_internal_pb2
    from wandb.sdk.internal.datastore import DataStore

    ds = DataStore()
    ds.open_for_scan(str(wandb_file))
    rows = []
    while True:
        try:
            data = ds.scan_data()
        except Exception as e:  # truncated tail of a killed run
            print(f"warning: stopped at corrupt record after {len(rows)} rows ({e})")
            break
        if data is None:
            break
        record = wandb_internal_pb2.Record()
        record.ParseFromString(data)
        if record.WhichOneof("record_type") != "history":
            continue
        row = {}
        for item in record.history.item:
            key = item.key or ".".join(item.nested_key)
            row[key] = json.loads(item.value_json)
        rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", help="run dir (runs/<name>) or a .wandb file")
    parser.add_argument("-o", "--out", help="output CSV (default: <run_dir>/history.csv)")
    args = parser.parse_args()

    path = Path(args.run)
    wandb_file = find_wandb_file(path)
    out = Path(args.out) if args.out else (path if path.is_dir() else wandb_file.parent) / "history.csv"

    rows = read_history(wandb_file)
    if not rows:
        sys.exit(f"{wandb_file}: no history records found")
    keys = sorted({k for r in rows for k in r})
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{out}: {len(rows)} rows, columns: {', '.join(keys)}")


if __name__ == "__main__":
    main()

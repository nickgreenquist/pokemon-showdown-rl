"""Mutation harness: apply a source mutation, run tests, restore, report.

The repo's standing rule is that a guard which has not been mutated is a
guard which has not been tested. This is the tool that does it. Both of the
subtleties below produced a confidently WRONG result before being fixed, and
neither is visible in the output — hence a script rather than a snippet
retyped each phase.

1. A RED baseline makes every mutation report "caught", including any
   deliberate equivalence control that is supposed to survive. A broken
   harness and a perfect score look identical, so the baseline is checked
   first and a red tree refuses to run.
2. Bytecode caching is invalidated by (mtime, size). A mutation that swaps
   two operands has the SAME SIZE as the original, and the restore usually
   lands within the same mtime second — so python serves a .pyc compiled
   from the MUTATED source long after the file is back to normal. That
   corrupts the verdicts and leaves the working tree behaving like mutated
   code, which surfaces as unrelated tests failing for no visible reason.

Always include at least one CONTROL: a provably-equivalent edit that MUST
survive. If it is reported caught, the harness is measuring noise.

Usage:

    python scripts/mutate.py <spec_module.py>

where the spec module defines:

    TESTS = ["tests/test_foo.py"]
    MUTATIONS = [(name, relative_path, old_source, new_source), ...]

`old_source` must appear exactly once in the file, or the mutation is
reported as BAD-PATTERN / AMBIGUOUS rather than silently skipped.
"""

import os
import runpy
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}


def _purge_pycache() -> None:
    for cache in REPO.rglob("__pycache__"):
        if ".git" not in cache.parts:
            shutil.rmtree(cache, ignore_errors=True)


def _pytest(tests: list[str]) -> subprocess.CompletedProcess:
    _purge_pycache()
    return subprocess.run(
        [sys.executable, "-m", "pytest", *tests, "-x", "-q", "--no-header",
         "-p", "no:cacheprovider"],
        cwd=REPO, capture_output=True, text=True, env=ENV,
    )


def run(mutations, tests) -> int:
    baseline = _pytest(tests)
    if baseline.returncode != 0:
        print("BASELINE IS RED — mutation results would be meaningless.\n")
        print(baseline.stdout[-2000:])
        raise SystemExit(2)

    results = []
    for name, target, old, new in mutations:
        path = REPO / target
        original = path.read_text()
        occurrences = original.count(old)
        if occurrences != 1:
            results.append((name, "BAD-PATTERN" if not occurrences else f"AMBIGUOUS({occurrences})"))
            continue
        try:
            path.write_text(original.replace(old, new))
            results.append((name, "caught" if _pytest(tests).returncode else "SURVIVED"))
        finally:
            path.write_text(original)
            _purge_pycache()
            assert path.read_text() == original, f"{name}: restore failed"

    width = max(len(name) for name, _ in results)
    survived = sum(verdict != "caught" for _, verdict in results)
    for name, verdict in results:
        print(f"{name:{width}s}  {verdict}{'' if verdict == 'caught' else '   <<<'}")
    print(f"\n{len(results) - survived}/{len(results)} caught, {survived} survived")
    return survived


if __name__ == "__main__":
    spec = runpy.run_path(sys.argv[1])
    run(spec["MUTATIONS"], spec["TESTS"])

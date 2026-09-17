#!/usr/bin/env python3
"""Verify a completed PhosphoFill ranked-pose run using only the standard library.

Example:
  python3 tests/verify_ranked_run.py /path/to/output_dir output_stem --n-poses 3
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("output_stem", help="Protein/output identifier before _PF<rank>")
    parser.add_argument("--suffix", default=".cif")
    parser.add_argument("--n-poses", type=int, default=3)
    parser.add_argument("--require-distinct", action="store_true")
    args = parser.parse_args()

    failures: list[str] = []
    hashes: list[str] = []
    checked_rows = 0

    for rank in range(1, args.n_poses + 1):
        structure = args.output_dir / f"{args.output_stem}_PF{rank}{args.suffix}"
        report = args.output_dir / f"{args.output_stem}_PF{rank}.report.tsv"
        if not structure.is_file():
            failures.append(f"missing structure: {structure}")
            continue
        if not report.is_file():
            failures.append(f"missing report: {report}")
            continue

        hashes.append(sha256(structure))
        with report.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        if not rows:
            failures.append(f"empty report: {report}")
            continue

        for row in rows:
            checked_rows += 1
            if int(row["pose_rank"]) != rank:
                failures.append(f"{report}: row reports pose_rank={row['pose_rank']}")
            if row.get("status") == "OK" and row.get("relax_backend") == "openmm_local":
                if row.get("relax_status") != "OK":
                    failures.append(
                        f"{report}: {row.get('chain_id')}:{row.get('resseq')} "
                        f"has relax_status={row.get('relax_status')}"
                    )

    if args.require_distinct and len(set(hashes)) != len(hashes):
        failures.append("ranked structure files are not all distinct")

    if failures:
        print("FAILED")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(
        f"PASS: {args.n_poses} ranked structures, {checked_rows} report rows, "
        f"{len(set(hashes))} distinct structure hashes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

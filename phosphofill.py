#!/usr/bin/env python3
"""Run the current PhosphoFill production -> report -> HTML pipeline.

Example:
  python phosphofill.py AF-P07949-F1.cif P07949.cif --sites A:905 A:932

By default, outputs are written to a directory named after the requested output
file. For the example above:

  P07949/
    AF-P07949-F1.cif
    P07949_PF1.cif
    P07949_PF1.report.tsv
    P07949_PF1_site_report.tsv
    P07949_viz_report.json
    P07949.selection.json
    P07949_viz.3dmol.html

Serve the output directory before opening the HTML:
  python -m http.server 8000 --directory P07949
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence


THIS_DIR = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Single-command PhosphoFill pipeline ending in the 3Dmol HTML report.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("input_structure", help="Input PDB or mmCIF file")
    parser.add_argument("output_structure", help="Output base structure name, for example phospho.cif")
    parser.add_argument("--sites", nargs="+", required=True, help="Sites to phosphorylate, for example A:905 A:928")

    parser.add_argument("--output-dir", default=None, help="Directory for all outputs. Default: <output_structure stem>/")
    parser.add_argument("--flat", action="store_true", help="Write outputs next to output_structure instead of creating a subdirectory")
    parser.add_argument("--n-poses", type=int, default=3, help="Number of ranked poses to generate, capped by production at 3")

    parser.add_argument("--relax-mode", choices=["none", "torsion_scan", "openmm_local"], default="openmm_local")
    parser.add_argument(
        "--cache-dir",
        default=str(THIS_DIR / "data" / "ccd"),
        help="CCD template cache directory (default: bundled SEP/TPO/PTR templates)",
    )
    parser.add_argument("--model-indices", default="0")
    parser.add_argument("--openmm-platform", default=None)
    parser.add_argument("--minimize-max-iterations", type=int, default=None)
    parser.add_argument("--minimize-tolerance", type=float, default=None)
    parser.add_argument(
        "--scan-context",
        choices=["sequential", "independent"],
        default="sequential",
        help="Scan sites on the accumulating grafted structure or independently on the original input.",
    )
    parser.add_argument(
        "--site-order",
        choices=["n_to_c", "c_to_n", "input"],
        default="n_to_c",
        help="Order used for grafting/prescan and sequential minimisation.",
    )
    parser.add_argument(
        "--minimization-coupling",
        choices=["sequential", "joint"],
        default="sequential",
        help="Minimise modified sites one at a time or together in one OpenMM call.",
    )
    parser.add_argument(
        "--existing-site-policy",
        choices=["skip", "error"],
        default="skip",
        help="Skip complete existing SEP/TPO/PTR sites or mark them as errors.",
    )

    parser.add_argument("--no-prescan-rotamer", action="store_true", help="Disable production prescan rotamer search")
    parser.add_argument("--prescan-step-deg", type=float, default=None)
    parser.add_argument("--prescan-contact-weight", type=float, default=None)
    parser.add_argument("--prescan-basic-weight", type=float, default=None)
    parser.add_argument("--prescan-hbond-weight", type=float, default=None)
    parser.add_argument("--prescan-polar-clash-scale", type=float, default=None)
    parser.add_argument("--prescan-pack-weight", type=float, default=None)
    parser.add_argument("--prescan-geom-prior-weight", type=float, default=None)
    parser.add_argument("--prescan-tpo-torsion-sigma", type=float, default=None)
    parser.add_argument("--prescan-keep-kabsch-if-good", action="store_true")

    parser.add_argument("--skip-report", action="store_true")
    parser.add_argument("--skip-viz", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Print commands and planned files without running them")
    parser.add_argument("--verbose", action="store_true", help="Stream subprocess output")

    parser.add_argument("--production-script", default=None)
    parser.add_argument("--report-script", default=None)
    parser.add_argument("--viz-script", default=None)
    return parser.parse_args()


def script_path(override: str | None, default_name: str) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    return THIS_DIR / default_name


def output_layout(output_structure: str, output_dir: str | None, flat: bool) -> tuple[Path, Path]:
    requested = Path(output_structure)
    suffix = requested.suffix or ".cif"
    requested = requested.with_suffix(suffix)

    if output_dir:
        out_dir = Path(output_dir)
        output_base = out_dir / requested.name
    elif flat:
        out_dir = requested.parent if str(requested.parent) else Path(".")
        output_base = requested
    else:
        out_dir = requested.parent / requested.stem
        output_base = out_dir / requested.name
    return out_dir.resolve(), output_base.resolve()


def pose_output_path(base_path: Path, rank: int, n_poses: int) -> Path:
    return base_path.parent / f"{base_path.stem}_PF{rank}{base_path.suffix}"


def pose_graft_report_path(base_path: Path, pose_path: Path, rank: int, n_poses: int) -> Path:
    return pose_path.with_suffix(".report.tsv")


def prescan_frames_path(base_path: Path) -> Path:
    return base_path.with_suffix(".prescan_frames.json")


def copy_input_structure(input_path: Path, out_dir: Path, dry_run: bool) -> Path:
    dest = out_dir / input_path.name
    if input_path.resolve() == dest.resolve():
        return dest
    if dry_run:
        return dest
    out_dir.mkdir(parents=True, exist_ok=True)
    # Copying the structure contents is required; preserving filesystem
    # metadata is optional.  Some removable filesystems (for example FAT32
    # mounted through WSL/DrvFS) accept the file copy but reject the chmod or
    # timestamp operations performed by shutil.copy2().
    shutil.copyfile(input_path, dest)
    try:
        shutil.copystat(input_path, dest)
    except OSError:
        # The destination does not support all source metadata.  The copied
        # structure is still complete and is safe to use downstream.
        pass
    return dest


def add_optional(cmd: List[str], flag: str, value: Any) -> None:
    if value is not None:
        cmd.extend([flag, str(value)])


def run_step(label: str, cmd: Sequence[str], dry_run: bool, verbose: bool) -> None:
    print(f"\n== {label} ==")
    print(subprocess.list2cmdline([str(part) for part in cmd]))
    if dry_run:
        return

    result = subprocess.run(
        list(cmd),
        text=True,
        stdout=None if verbose else subprocess.PIPE,
        stderr=None if verbose else subprocess.PIPE,
    )
    if result.returncode != 0:
        if not verbose:
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
        raise SystemExit(f"{label} failed with exit code {result.returncode}")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def site_key(row: Dict[str, Any]) -> str:
    label = row.get("site_label")
    if label:
        return str(label)
    chain = row.get("chain_id", "")
    resno = row.get("residue_number", row.get("resseq", ""))
    icode = str(row.get("insertion_code", row.get("icode", "")) or "").strip()
    return f"{chain}:{resno}{icode}"


def merge_pose_reports(report_jsons: Sequence[Path], pose_paths: Sequence[Path], out_path: Path) -> Path:
    per_pose_rows: List[List[Dict[str, Any]]] = []
    for report_json in report_jsons:
        data = load_json(report_json)
        if isinstance(data, dict) and "sites" in data:
            data = data["sites"]
        if not isinstance(data, list):
            raise SystemExit(f"Unsupported report JSON format: {report_json}")
        per_pose_rows.append(data)

    if not per_pose_rows or not per_pose_rows[0]:
        raise SystemExit("No rich report rows were produced")

    rows_by_pose: List[Dict[str, Dict[str, Any]]] = [
        {site_key(row): row for row in rows}
        for rows in per_pose_rows
    ]

    merged_rows: List[Dict[str, Any]] = []
    for base_row in per_pose_rows[0]:
        key = site_key(base_row)
        merged = dict(base_row)
        merged["selected_rank"] = 1
        for idx, pose_path in enumerate(pose_paths, start=1):
            pose_key = f"pf{idx}"
            row = rows_by_pose[idx - 1].get(key) if idx - 1 < len(rows_by_pose) else None
            if row:
                merged[f"{pose_key}_row"] = row
                merged[f"{pose_key}_confidence"] = row.get("phosphofill_confidence")
                merged[f"{pose_key}_tier"] = row.get("confidence_tier")
                merged[f"{pose_key}_quality"] = row.get("phospho_quality_label")
                merged[f"{pose_key}_overall_interpretation"] = row.get("overall_interpretation")
            merged[f"{pose_key}_path"] = pose_path.name
        merged_rows.append(merged)

    out_path.write_text(json.dumps({"sites": merged_rows}, indent=2), encoding="utf-8")
    return out_path


def write_selection_json(pose_paths: Sequence[Path], out_path: Path) -> Path:
    payload = {
        "selected_rank": 1,
        "selected_output_path": str(pose_paths[0]) if pose_paths else "",
        "candidate_poses": [
            {"output_rank": idx, "path": str(path)}
            for idx, path in enumerate(pose_paths, start=1)
        ],
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out_path


def require_files(paths: Sequence[Path], context: str) -> None:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise SystemExit(f"Missing expected {context} file(s):\n  " + "\n  ".join(missing))


def main() -> None:
    args = parse_args()

    if args.skip_report and not args.skip_viz:
        raise SystemExit("--skip-report cannot be combined with HTML generation; use --skip-viz too.")

    production_script = script_path(args.production_script, "phosphofill_production.py")
    report_script = script_path(args.report_script, "phosphofill_report_v4_modes_geom.py")
    viz_script = script_path(args.viz_script, "phosphofill_visualization_v5_richviz.py")

    input_path = Path(args.input_structure).expanduser().resolve()
    out_dir, output_base = output_layout(args.output_structure, args.output_dir, args.flat)
    actual_n_poses = max(1, min(args.n_poses, 3))
    stem = output_base.stem

    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
    html_input = copy_input_structure(input_path, out_dir, args.dry_run)

    pose_paths = [pose_output_path(output_base, rank, actual_n_poses) for rank in range(1, actual_n_poses + 1)]
    graft_reports = [
        pose_graft_report_path(output_base, pose_path, rank, actual_n_poses)
        for rank, pose_path in enumerate(pose_paths, start=1)
    ]
    frames_json = prescan_frames_path(output_base)

    print("PhosphoFill all-in-one pipeline")
    print(f"  Input:       {input_path}")
    print(f"  Output dir:  {out_dir}")
    print(f"  Sites:       {' '.join(args.sites)}")
    print(f"  Poses:       {actual_n_poses}")
    print(f"  Scan:        {args.scan_context} ({args.site_order})")
    print(f"  Minimise:    {args.minimization_coupling}")

    production_cmd = [
        sys.executable,
        str(production_script),
        str(input_path),
        str(output_base),
        "--sites",
        *args.sites,
        "--n-poses",
        str(actual_n_poses),
        "--relax-mode",
        args.relax_mode,
        "--model-indices",
        args.model_indices,
        "--scan-context",
        args.scan_context,
        "--site-order",
        args.site_order,
        "--minimization-coupling",
        args.minimization_coupling,
        "--existing-site-policy",
        args.existing_site_policy,
    ]
    add_optional(production_cmd, "--cache-dir", args.cache_dir)
    add_optional(production_cmd, "--openmm-platform", args.openmm_platform)
    add_optional(production_cmd, "--minimize-max-iterations", args.minimize_max_iterations)
    add_optional(production_cmd, "--minimize-tolerance", args.minimize_tolerance)
    add_optional(production_cmd, "--prescan-step-deg", args.prescan_step_deg)
    add_optional(production_cmd, "--prescan-contact-weight", args.prescan_contact_weight)
    add_optional(production_cmd, "--prescan-basic-weight", args.prescan_basic_weight)
    add_optional(production_cmd, "--prescan-hbond-weight", args.prescan_hbond_weight)
    add_optional(production_cmd, "--prescan-polar-clash-scale", args.prescan_polar_clash_scale)
    add_optional(production_cmd, "--prescan-pack-weight", args.prescan_pack_weight)
    add_optional(production_cmd, "--prescan-geom-prior-weight", args.prescan_geom_prior_weight)
    add_optional(production_cmd, "--prescan-tpo-torsion-sigma", args.prescan_tpo_torsion_sigma)
    if args.no_prescan_rotamer:
        production_cmd.append("--no-prescan-rotamer")
    if args.prescan_keep_kabsch_if_good:
        production_cmd.append("--prescan-keep-kabsch-if-good")

    run_step("1. Production grafting/minimization", production_cmd, args.dry_run, args.verbose)

    if not args.dry_run:
        require_files(pose_paths, "pose structure")
        require_files(graft_reports, "production report")

    rich_report_jsons: List[Path] = []
    if not args.skip_report:
        for rank, (pose_path, graft_report) in enumerate(zip(pose_paths, graft_reports), start=1):
            rich_prefix = out_dir / f"{stem}_PF{rank}_site_report"
            report_cmd = [
                sys.executable,
                str(report_script),
                str(html_input),
                str(pose_path),
                "--sites",
                *args.sites,
                "--output-prefix",
                str(rich_prefix),
                "--graft-report",
                str(graft_report),
                "--scan-context",
                args.scan_context,
                "--site-order",
                args.site_order,
                "--minimization-coupling",
                args.minimization_coupling,
            ]
            run_step(f"2.{rank}. Rich report for PF{rank}", report_cmd, args.dry_run, args.verbose)
            rich_report_jsons.append(Path(str(rich_prefix) + ".json"))

        if not args.dry_run:
            require_files(rich_report_jsons, "rich report JSON")

    if not args.skip_viz:
        selection_json = out_dir / f"{stem}.selection.json"
        viz_report_json = out_dir / f"{stem}_viz_report.json"
        if not args.dry_run:
            write_selection_json(pose_paths, selection_json)
            merge_pose_reports(rich_report_jsons, pose_paths, viz_report_json)

        viz_prefix = out_dir / f"{stem}_viz"
        viz_cmd = [
            sys.executable,
            str(viz_script),
            str(html_input),
            str(viz_report_json),
            "--selection-json",
            str(selection_json),
            "--output-prefix",
            str(viz_prefix),
        ]
        if frames_json.exists() or args.dry_run:
            viz_cmd.extend(["--prescan-frames", str(frames_json)])
        run_step("3. HTML visualization", viz_cmd, args.dry_run, args.verbose)

    html_path = out_dir / f"{stem}_viz.3dmol.html"
    print("\nDone.")
    print(f"  Output directory: {out_dir}")
    if not args.skip_viz and (html_path.exists() or args.dry_run):
        print(f"  HTML report:      {html_path}")
        serve_cmd = [sys.executable, "-m", "http.server", "8000", "--directory", str(out_dir)]
        print(f"  Serve with:       {subprocess.list2cmdline(serve_cmd)}")
        print(f"  Then open:        http://localhost:8000/{html_path.name}")


if __name__ == "__main__":
    main()

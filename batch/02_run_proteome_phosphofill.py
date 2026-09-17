#!/usr/bin/env python3
"""
02_run_proteome_phosphofill.py
==============================
Runs phosphofill.py on every protein in proteome_input.tsv using --skip-viz.
The structural poses, production reports, and rich per-site reports are kept;
only the HTML visualization is omitted.

Parses the production report TSV from each run and collects results
into a single proteome_results.tsv.

Also extracts pLDDT at each site from the AF2 B-factor column.

Usage
-----
    python3 02_run_proteome_phosphofill.py \
        --input      proteome_run/proteome_input.tsv \
        --af2-dir    af2_models \
        --workdir    proteome_run/pf_runs \
        --results    proteome_run/proteome_results.tsv \
        --phosphofill phosphofill.py \
        --workers    8 \
        [--prescan-contact-weight 0.0] \
        [--prescan-pack-weight 0.2] \
        [--resume]      # skip proteins already in results

Outputs
-------
    proteome_run/
        proteome_results.tsv      one row per site per pose rank
        failed_proteins.tsv       proteins that failed with error
"""

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd


# ── Production report TSV columns we care about ──────────────────────────
# From phosphofill_production.py output
# Production report columns (always available)
REPORT_KEEP_PRODUCTION = [
    "chain_id", "resseq", "original_resname", "new_resname",
    "status", "preflight_status", "plddt_mean", "plddt_min", "plddt_category",
    "scan_context", "site_order", "minimization_coupling",
    "prescan_score_before", "prescan_score_after",
    "prescan_n_zero_clash", "prescan_score_min", "prescan_score_max",
    "clashes_after_relax", "relax_status",
    "relax_energy_before", "relax_energy_after",
    "site_repulsion_energy_delta", "n_flex_neighbors",
]

# Rich report columns (from phosphofill_report_v4_modes_geom.py — available
# because the proteome runner skips only visualization, not reporting).
REPORT_KEEP_RICH = [
    "torsion_CA_CB_OG_P", "torsion_CG2_CB_OG1_P", "torsion_CE1_CZ_OH_P",
    "nearby_basic_count_after", "nearby_acidic_count_after",
    "salt_bridge_count_after", "salt_bridge_details_after",
    "polar_contact_count_after", "hydrogen_bond_count_after",
    "electrostatic_score_weighted_after",
    "phosphofill_confidence", "confidence_tier", "phospho_quality_label",
    "intrinsic_site_fit", "contextual_site_fit",
    "plddt_site", "plddt_window_mean", "plddt_class",
    "sasa_unmodified", "sasa_modified", "sasa_delta",
    "exposure_class_unmodified", "exposure_class_modified", "local_ca_rmsd",
    "d_anchor_p_modified", "angle_base_anchor_p_modified",
    "overall_interpretation", "interpretation_flags",
]

REPORT_KEEP = REPORT_KEEP_PRODUCTION + REPORT_KEEP_RICH


def extract_plddt(pdb_path: str, chain: str, position: int) -> float | None:
    """
    Extract mean pLDDT (B-factor) for a site ± 5 residues from an AF2 PDB.
    AF2 stores pLDDT in the B-factor column.
    """
    try:
        values = []
        with open(pdb_path) as f:
            for line in f:
                if not line.startswith(("ATOM", "HETATM")):
                    continue
                rec_chain = line[21].strip()
                if rec_chain != chain:
                    continue
                try:
                    resnum = int(line[22:26].strip())
                except ValueError:
                    continue
                if abs(resnum - position) <= 5:
                    try:
                        bfac = float(line[60:66].strip())
                        values.append(bfac)
                    except ValueError:
                        continue
        return sum(values) / len(values) if values else None
    except Exception:
        return None


def parse_production_report(prod_tsv: Path, rich_tsv: Path = None) -> list[dict]:
    """Parse production + optional rich report TSV into list of dicts."""
    if not prod_tsv.exists():
        return []
    try:
        prod_df = pd.read_csv(prod_tsv, sep="\t")

        # Load rich report if available
        rich_df = None
        if rich_tsv and rich_tsv.exists():
            try:
                rich_df = pd.read_csv(rich_tsv, sep="\t")
            except Exception:
                pass

        rich_lookup = {}
        if rich_df is not None:
            for _, rich_row in rich_df.iterrows():
                key = (
                    str(rich_row.get("chain_id", "")),
                    int(rich_row.get("residue_number", 0)),
                    str(rich_row.get("insertion_code", "") or "").strip(),
                )
                rich_lookup[key] = rich_row

        rows = []
        for _, row in prod_df.iterrows():
            r = {}
            # Production columns
            for col in REPORT_KEEP_PRODUCTION:
                r[col] = row.get(col, None)
            # Rich columns — merge by structural site identity, not row order.
            key = (
                str(row.get("chain_id", "")),
                int(row.get("resseq", 0)),
                str(row.get("icode", "") or "").strip(),
            )
            rich_row = rich_lookup.get(key)
            if rich_row is not None:
                for col in REPORT_KEEP_RICH:
                    r[col] = rich_row.get(col, None)
            else:
                for col in REPORT_KEEP_RICH:
                    r[col] = None
            mod_type = str(r.get("new_resname", ""))
            torsion_column = {
                "SEP": "torsion_CA_CB_OG_P",
                "TPO": "torsion_CG2_CB_OG1_P",
                "PTR": "torsion_CE1_CZ_OH_P",
            }.get(mod_type)
            r["torsion_key"] = r.get(torsion_column) if torsion_column else None
            rows.append(r)
        return rows
    except Exception as e:
        return []


def run_one_protein(args_tuple) -> dict:
    """
    Worker function — runs phosphofill.py for one protein.
    Returns a result dict with status and parsed rows.
    """
    (acc_id, entry_name, af2_pdb, site_specs, positions, mod_types,
     n_sites, af2_dir, workdir, phosphofill_py,
     contact_weight, pack_weight, n_poses, scan_context, site_order,
     minimization_coupling, existing_site_policy) = args_tuple

    pdb_path = Path(af2_dir) / af2_pdb
    if not pdb_path.exists():
        return {"acc_id": acc_id, "status": "missing_af2", "rows": []}

    protein_id = str(acc_id)
    out_dir = Path(workdir) / protein_id
    out_cif = Path(f"{protein_id}.cif")

    # Build command. Keep rich reports for confidence/contact analysis and
    # omit only the per-protein HTML visualization.
    cmd = [
        sys.executable, phosphofill_py,
        str(pdb_path),
        str(out_cif),
        "--output-dir", str(out_dir),
        "--sites", *site_specs.split(),
        "--n-poses", str(n_poses),
        "--skip-viz",  # keep rich report for salt bridge/contact metrics
        "--scan-context", scan_context,
        "--site-order", site_order,
        "--minimization-coupling", minimization_coupling,
        "--existing-site-policy", existing_site_policy,
    ]
    if contact_weight is not None:
        cmd += ["--prescan-contact-weight", str(contact_weight)]
    if pack_weight is not None:
        cmd += ["--prescan-pack-weight", str(pack_weight)]

    t0 = time.time()
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600
        )
        elapsed = time.time() - t0

        if result.returncode != 0:
            return {
                "acc_id": acc_id, "status": "failed", "rows": [],
                "error": result.stderr[-500:] if result.stderr else "",
                "elapsed": elapsed,
            }

        # Parse all pose report TSVs
        all_rows = []
        for rank in range(1, n_poses + 1):
            # Production report (always present)
            prod_report = out_dir / f"{protein_id}_PF{rank}.report.tsv"
            # Rich report (present when --skip-report not used)
            rich_report = out_dir / f"{protein_id}_PF{rank}_site_report.tsv"
            parsed = parse_production_report(prod_report, rich_report)
            for row in parsed:
                # Add metadata
                row["acc_id"]     = acc_id
                row["entry_name"] = entry_name
                row["pose_rank"]  = rank
                row["mod_types"]  = mod_types
                # Extract pLDDT per site
                try:
                    pos = int(row.get("resseq", row.get("residue_number", 0)))
                    chain = str(row.get("chain_id") or site_specs.split(":")[0])
                    row["plddt_local"] = extract_plddt(str(pdb_path), chain, pos)
                except Exception:
                    row["plddt_local"] = None
                all_rows.append(row)

        return {
            "acc_id": acc_id, "status": "ok",
            "rows": all_rows, "elapsed": elapsed,
            "n_sites": n_sites,
        }

    except subprocess.TimeoutExpired:
        return {"acc_id": acc_id, "status": "timeout", "rows": [], "elapsed": 600}
    except Exception as e:
        return {"acc_id": acc_id, "status": "error", "rows": [], "error": str(e)}


def main(input_tsv: str, af2_dir: str, workdir: str, results_path: str,
         phosphofill_py: str, workers: int, contact_weight: float,
         pack_weight: float, n_poses: int, scan_context: str,
         site_order: str, minimization_coupling: str,
         existing_site_policy: str, resume: bool) -> None:

    Path(workdir).mkdir(parents=True, exist_ok=True)

    # Load input
    df = pd.read_csv(input_tsv, sep="\t")
    print(f"Loaded {len(df):,} proteins from {input_tsv}")

    # Resume: skip already completed
    completed = set()
    if resume and Path(results_path).exists():
        done = pd.read_csv(results_path, sep="\t")
        completed = set(done["acc_id"].unique())
        print(f"Resuming: {len(completed):,} proteins already done, "
              f"{len(df) - len(df[df.acc_id.isin(completed)]):,} remaining")
        df = df[~df["acc_id"].isin(completed)]

    # Build task tuples
    tasks = []
    for _, row in df.iterrows():
        tasks.append((
            row["acc_id"], row["entry_name"], row["af2_pdb"],
            row["site_specs"], row["positions"], row["mod_types"],
            row["n_sites"],
            af2_dir, workdir, phosphofill_py,
            contact_weight, pack_weight, n_poses, scan_context, site_order,
            minimization_coupling, existing_site_policy,
        ))

    print(f"Running {len(tasks):,} proteins with {workers} workers...")
    print(f"  PhosphoFill: {phosphofill_py}")
    print(f"  prescan-contact-weight: {contact_weight}")
    print(f"  prescan-pack-weight: {pack_weight}")
    print(f"  n-poses: {n_poses}")
    print(f"  scan-context: {scan_context}")
    print(f"  site-order: {site_order}")
    print(f"  minimization-coupling: {minimization_coupling}")

    all_rows   = []
    failed     = []
    n_done     = 0
    n_ok       = 0
    t_start    = time.time()

    # Open results file for streaming writes
    results_path = str(Path(results_path).resolve())
    Path(results_path).parent.mkdir(parents=True, exist_ok=True)
    failed_path = str(Path(results_path).parent / "failed_proteins.tsv")
    results_file = open(results_path, "a" if resume else "w", newline="")
    failed_file  = open(failed_path, "a" if resume else "w", newline="")

    writer         = None
    failed_writer  = csv.DictWriter(
        failed_file, fieldnames=["acc_id", "status", "error", "elapsed"],
        delimiter="\t"
    )
    if not resume:
        failed_writer.writeheader()

    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(run_one_protein, t): t[0] for t in tasks}

        for future in as_completed(futures):
            acc_id = futures[future]
            try:
                res = future.result()
            except Exception as e:
                res = {"acc_id": acc_id, "status": "exception",
                       "rows": [], "error": str(e)}

            n_done += 1
            elapsed_total = time.time() - t_start
            rate = n_done / elapsed_total if elapsed_total > 0 else 0
            eta  = (len(tasks) - n_done) / rate if rate > 0 else 0

            if res["status"] == "ok" and res["rows"]:
                n_ok += 1
                rows = res["rows"]

                # Write header on first batch
                if writer is None:
                    fieldnames = list(rows[0].keys())
                    writer = csv.DictWriter(results_file, fieldnames=fieldnames,
                                           delimiter="\t", extrasaction="ignore")
                    if not resume:
                        writer.writeheader()

                for row in rows:
                    writer.writerow(row)
                results_file.flush()

            else:
                failed_writer.writerow({
                    "acc_id":  res["acc_id"],
                    "status":  res["status"],
                    "error":   res.get("error", "")[:200],
                    "elapsed": res.get("elapsed", ""),
                })
                failed_file.flush()

            if n_done % 100 == 0 or n_done == len(tasks):
                print(f"  {n_done:,}/{len(tasks):,} done "
                      f"({n_ok:,} ok) | "
                      f"{rate:.1f}/min | ETA {eta/60:.0f} min")

    results_file.close()
    failed_file.close()

    print(f"\nDone. {n_ok:,}/{len(tasks):,} proteins succeeded.")
    print(f"Results: {results_path}")
    print(f"Next: python3 03_analyse_proteome.py --results {results_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input",     required=True)
    ap.add_argument("--af2-dir",   default="af2_models")
    ap.add_argument("--workdir",   default="proteome_run/pf_runs")
    ap.add_argument("--results",   default="proteome_run/proteome_results.tsv")
    ap.add_argument("--phosphofill", default="phosphofill.py")
    ap.add_argument("--workers",   type=int, default=4)
    ap.add_argument("--prescan-contact-weight", type=float, default=0.0,
                    dest="contact_weight")
    ap.add_argument("--prescan-pack-weight",    type=float, default=0.2,
                    dest="pack_weight")
    ap.add_argument("--n-poses",   type=int, default=3)
    ap.add_argument("--scan-context", choices=["sequential", "independent"], default="sequential")
    ap.add_argument("--site-order", choices=["n_to_c", "c_to_n", "input"], default="n_to_c")
    ap.add_argument("--minimization-coupling", choices=["sequential", "joint"], default="sequential")
    ap.add_argument("--existing-site-policy", choices=["skip", "error"], default="skip")
    ap.add_argument("--resume",    action="store_true",
                    help="Skip proteins already in results file")
    args = ap.parse_args()
    main(args.input, args.af2_dir, args.workdir, args.results,
         args.phosphofill, args.workers, args.contact_weight,
         args.pack_weight, args.n_poses, args.scan_context,
         args.site_order, args.minimization_coupling,
         args.existing_site_policy, args.resume)

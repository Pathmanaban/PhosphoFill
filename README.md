# PhosphoFill

PhosphoFill grafts phosphate groups onto existing SER, THR, and TYR residues,
ranks local phosphate orientations against the structural environment, and
returns up to three independently minimised structural models with per-site
reports and an optional interactive HTML view.

## Installation

Python 3.10 or newer is recommended.

```bash
git clone <repository-url>
cd PhosphoFill
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

The release workflow was tested with Python 3.12.3, Biopython 1.87, NumPy
1.26.4, and OpenMM 8.5.0.

## Quick start

Single phosphosite (TYR 68 to PTR):

```bash
python3 phosphofill.py \
  examples/single_site/input/AF-A0A024RBG1-F1.cif \
  A0A024RBG1.cif \
  --sites A:68 \
  --n-poses 3
```

Two adjacent phosphosites (SER 686 and TYR 687):

```bash
python3 phosphofill.py \
  examples/multi_site/input/AF-P07949-F1.cif \
  P07949.cif \
  --sites A:686 A:687 \
  --n-poses 3
```

By default, a directory named after the output stem is created. The second
command writes `P07949/P07949_PF1.cif`, `P07949_PF2.cif`, and
`P07949_PF3.cif`, together with pose-specific reports and the HTML
visualisation. Site numbers are stored in the reports rather than embedded in
filenames.

## What each rank means

PhosphoFill scans 12 trial orientations at 30-degree intervals, scores the
orientations, and returns the three highest-ranked alternatives. Each rank is
reconstructed from its own saved prescan coordinates and minimised
independently. Rank 2 and rank 3 are not cumulative rotations of rank 1.

## Multi-site behaviour

The production defaults are:

```text
--scan-context sequential
--site-order n_to_c
--minimization-coupling sequential
```

For sequential scanning, each later site sees phosphates already grafted at
earlier sites. The three controls can be selected independently:

- `--scan-context sequential|independent`
- `--site-order n_to_c|c_to_n|input`
- `--minimization-coupling sequential|joint`

For example, reverse-order scanning followed by one joint OpenMM minimisation
per rank is:

```bash
python3 phosphofill.py input.cif phosphofilled.cif \
  --sites A:185 A:187 \
  --scan-context sequential \
  --site-order c_to_n \
  --minimization-coupling joint
```

## Existing phosphoresidues and preflight checks

Every requested site is checked before grafting. Complete existing SEP, TPO,
or PTR residues are left unchanged by default and reported as `SKIPPED` with
preflight status `ALREADY_PHOSPHORYLATED`. Use
`--existing-site-policy error` to reject them instead.

Missing sites, unsupported parent residues, duplicate requests, and incomplete
phosphoresidues are fatal preflight errors. A `.preflight.tsv` diagnostic is
written before the run stops.

## Empirical placement geometry

| Residue | Anchor--P | Base--anchor--P | Torsion treatment |
|---|---:|---:|---|
| TPO | 1.613 Å | 118.8 degrees | CG2--CB--OG1--P seed at -58.9 degrees |
| SEP | 1.614 Å | 115.4 degrees | +66.3-degree sharp seed; broad -60 to +50-degree scoring basin |
| PTR | 1.609 Å | 125.1 degrees | neutral seed; no torsion-prior penalty |

SEP starting angles are 66.3, 12.6, and -45.0 degrees. These are starting
orientations for environmental scanning rather than fixed final orientations.

## Outputs

For each retained rank, PhosphoFill can write:

- a PDB or mmCIF structural model;
- the production `.report.tsv`;
- a per-site JSON/TSV report;
- an interactive 3Dmol HTML report.

To open the HTML locally, serve the output directory:

```bash
python3 -m http.server 8000 --directory P07949
```

Then visit `http://localhost:8000/` in a browser.

## Batch processing

`batch/02_run_proteome_phosphofill.py` applies the same production workflow to
a TSV of structures and requested sites. See [batch/README.md](batch/README.md)
for the input schema and a resumable command. The batch runner is provided for
general datasets; manuscript-scale AlphaFold outputs are not bundled here.

## Useful options

- `--openmm-platform CPU` explicitly chooses the CPU platform.
- `--skip-viz` omits HTML generation but retains reports.
- `--skip-report --skip-viz` runs grafting/minimisation only.
- `--relax-mode none` is for diagnostics, not production results.
- `--flat` writes next to the requested output instead of creating a directory.
- `--dry-run` prints planned commands and paths without running them.

List every option with:

```bash
python3 phosphofill.py --help
```

## Release verification

After a three-pose run:

```bash
python3 tests/verify_ranked_run.py P07949 P07949 \
  --n-poses 3 --require-distinct
```

The helper checks that all structures and reports exist, rank labels agree,
OpenMM minimisation succeeded, and ranked structure files are distinct.

## License

PhosphoFill source code is available under the Apache License 2.0. See
[LICENSE](LICENSE) and [NOTICE](NOTICE). Bundled example structures remain
subject to their original source terms and are not relicensed.

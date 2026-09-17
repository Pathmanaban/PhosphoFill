# Batch runner

The batch runner groups requested sites by protein/structure and invokes the
root `phosphofill.py` workflow. Its input is a tab-separated table containing at
least:

```text
acc_id  af2_pdb  site_specs
P07949  AF-P07949-F1.cif  A:686 A:687
```

An example resumable command, run from the repository root, is:

```bash
python3 -u batch/02_run_proteome_phosphofill.py \
  --input /path/to/input.tsv \
  --af2-dir /path/to/structures \
  --workdir /path/to/run/pf_runs \
  --results /path/to/run/results.tsv \
  --phosphofill phosphofill.py \
  --workers 4 \
  --n-poses 3 \
  --scan-context sequential \
  --site-order n_to_c \
  --minimization-coupling sequential \
  --existing-site-policy skip \
  --resume
```

`--resume` recognises completed proteins from the result table and validated
per-protein outputs. Store `--workdir` and `--results` on a filesystem that
supports the required files and free space; the runner accepts both ordinary
Linux/WSL paths and mounted external drives.


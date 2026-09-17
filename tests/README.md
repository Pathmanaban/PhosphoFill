# Release checks

After a three-pose run, verify that every structure/report exists and every
OpenMM-grafted site was independently minimized:

```bash
python3 tests/verify_ranked_run.py /path/to/output_dir output_stem \
  --n-poses 3 --require-distinct
```

For example, a P07949 run is verified with `output_stem` set to `P07949`; the
helper expects `P07949_PF1.cif`, `P07949_PF2.cif` and `P07949_PF3.cif`.

The release was checked on real archived structures:

- CDK2/4EOJ Thr160: three distinct ranked outputs; all three minimizations OK.
- 2ZM3 Tyr1161/Tyr1165/Tyr1166: reverse-order scan with joint minimization;
  three distinct ranked outputs and all three sites minimized successfully in
  every rank.
- The same 2ZM3 sites with independent scanning and sequential minimization.
- Phosphorylated CDK2/4EOJ TPO160: detected as already phosphorylated, left
  unchanged and reported as `SKIPPED`.
- Duplicate CDK2/4EOJ Thr160 request: rejected during preflight; diagnostic TSV
  written and no grafted structure created.

The prior multi-site benchmark verification also passed 4,149/4,149 archived
checks across N-to-C, C-to-N, independent-site and joint-minimization modes.

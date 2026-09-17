# Examples

## Single site

`single_site/input/AF-A0A024RBG1-F1.cif` contains TYR at chain A, residue 68.
Run PhosphoFill with `--sites A:68` to create PTR. A rank-1 reference output and
production report are retained in `single_site/expected/` for inspection.

## Adjacent multi-site example

`multi_site/input/AF-P07949-F1.cif` contains SER A:686 and TYR A:687. Run with
`--sites A:686 A:687` to exercise sequential multi-site scanning and three
independently minimised outputs.

The input structures are examples only; their inclusion does not imply that
these particular predicted phosphosites are experimentally validated in the
provided conformations.


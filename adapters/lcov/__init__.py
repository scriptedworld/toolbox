"""Not a package in use: the adapters are standalone scripts, invoked by path.

This file exists so coverage.py can SEE them. Its discovery of files that no
test executed descends only into subdirectories it can reach as packages, so
without this marker an adapter with no test is absent from the report rather
than present at 0% — which is exactly the file a per-file coverage gate exists
to catch. Measured 2026-09-04; `../../pyproject.toml` carries the numbers.

Naming the leaf directories in `[tool.coverage.run] source` also works and was
rejected: it makes each Cobertura filename relative to its own leaf, so the
three `coverage.py` adapters all report as "coverage.py" and merge into one
entry.

THE DIRECTORY IS NAMED FOR THE FORMAT, NOT FOR A LANGUAGE. It held only
`adapters/rust/coverage.py` until 2026-09-09, which read a format rather than a
language: lcov is what cargo-llvm-cov and gcovr both emit, so the C++ jig needs
the same file. Copying it would have been the fifth thing in this repository to
exist twice with nothing detecting that the copies agreed.
"""

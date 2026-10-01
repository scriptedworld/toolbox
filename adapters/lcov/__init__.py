"""Not a package in use: the adapters are standalone scripts, invoked by path.

This file exists so coverage.py can see them. Its discovery of files that no
test executed descends only into subdirectories it can reach as packages, so
without this marker an adapter with no test is absent from the report rather
than present at 0%, which is exactly the file a per-file coverage gate exists
to catch. `../../pyproject.toml` carries the numbers.

Naming the leaf directories in `[tool.coverage.run] source` instead would make
each Cobertura filename relative to its own leaf, so the three `coverage.py`
adapters would all report as "coverage.py" and merge into one entry.

The directory is named for the format. lcov is what cargo-llvm-cov, node and
deno all emit, so the Rust, Node and Deno jigs read one adapter and no copy per
language can drift from it.
"""

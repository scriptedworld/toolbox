"""Not a package in use: the adapters are standalone scripts, invoked by path.

This file exists so coverage.py can see them. Its discovery of files that no
test executed descends only into subdirectories it can reach as packages, so
without this marker an adapter with no test is absent from the report rather
than present at 0%, which is exactly the file a per-file coverage gate exists
to catch. `../../pyproject.toml` carries the numbers.

Naming the leaf directories in `[tool.coverage.run] source` also works and was
rejected: it makes each Cobertura filename relative to its own leaf, so the
three `coverage.py` adapters all report as "coverage.py" and merge into one
entry.

The directory is named for the format, not for a language. lcov is what
cargo-llvm-cov, node and deno all emit, so the Rust, Node and Deno jigs read the
same file, and a copy per language would be one more thing in this repository
to exist twice with nothing detecting whether the copies agree.
"""

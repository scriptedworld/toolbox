## What changed

## Why

Where the reasoning is not obvious from the diff. Anything that would survive
being moved into the file it describes belongs in that file instead.

## How it was checked

Say what you ran and what came back, not that it passed.

```sh
python3 -m pytest
bolt --definitions toolbox common-quality .
bolt --definitions toolbox python-std-quality .
bolt secrets .
```

`--definitions toolbox` is not optional here and no other adopter passes it.
`CONTRIBUTING.md` says why.

## What this does to adopters

A change to a jig, a checker or an adapter reaches every project that has
adopted it, with no version pin in between. State which of these applies:

- No effect on adopters.
- Adopters see a new finding they did not see before. Say which task, and what
  an adopter's honest response is.
- Adopters need to relink, because the set gained or lost a file in
  `jigs.yaml`.

## Requirements

A change to behaviour names the requirement it serves. A new test carries a
`COVERS:` mark, and the kinds are `positive`, `negative`, `edge`, `property` and
`regression`.

If this retires a requirement, its `COVERS:` marks are repointed or removed in
this same change, and the ID is not reused.

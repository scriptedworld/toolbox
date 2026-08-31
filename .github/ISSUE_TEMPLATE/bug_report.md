---
name: Bug report
about: A jig, checker or adapter behaved differently from what is documented
labels: bug
---

## What you ran

The jig and the command, including any flags:

```sh
bolt common-quality .
```

## What happened

Paste the relevant part of `result.yaml` rather than the exit status. bolt exits
0 whenever the run completed, so the status does not carry the verdict.

If one task is at fault, its output under the run's `work/<task>/` directory is
the useful part.

## What you expected

## Which version

There are no releases yet, so name the commit you have:

```sh
git rev-parse --short HEAD
```

## Your project

Whether it adopted by symlink or holds real files, and which sets:

```sh
python3 bin/link-toolbox.py --check /path/to/your-project common
```

The language and the tool version, where the finding is about a specific tool.

## A false pass, if that is what this is

Say so explicitly. A check that reports nothing after looking in the wrong place
is the failure that matters most here, and it is indistinguishable from a clean
run unless you tell us what it should have found.

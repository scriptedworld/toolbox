# Security

## Reporting a vulnerability

Use GitHub's private vulnerability reporting on this repository, through the
Security tab. That keeps the report private until there is something to say
about it.

Please do not open a public issue for a vulnerability.

There are no releases and no version tags. The supported version is the current
state of the default branch, so a fix lands there and adopters pick it up the
next time they pull.

## What this repository is, in security terms

A jig is a list of command lines. bolt runs them, this repository holds them,
and adopting a jig is agreeing to run its command lines in your project.

That is the whole trust boundary, and three things follow from it.

**Running a quality jig executes the code being checked.** This is not incidental
to how the jigs work. The Python jig runs the project's own test suite under
`pytest`, and the Go jig runs `go test` and then invokes the binary it just
built. Point a jig at a repository you do not trust and you have run that
repository's code with your own privileges.

The jigs are a quality gate, not a sandbox. They are built to tell you whether
your code meets a standard, and they assume the code is yours.

**Adoption is symlinks, not copies, so a change here takes effect immediately in
every project that has adopted.** `bin/link-toolbox.py` links this repository's
checkers and adapters into an adopting project, and those links resolve back
here. There is no version pin between the two. An adopter tracking this
repository gets a fix the moment it lands, and would get a defect the same way.
`--check` reports what an adoption currently points at.

**The tools a jig names are installed by something else.** `requires:` declares
executables by name, not by version or by checksum, and anvil builds the images
carrying them. Nothing here verifies what got installed under those names, so
the integrity of `gofmt`, `ruff`, `gitleaks` and the rest belongs to whatever
provisioned them.

## Secret scanning, and what it does not tell you

`bolt.secrets.yaml` runs two scanners because their false negatives differ.
`gitleaks` is rule based and reads git history as well as the working tree, so
it sees a credential that was committed and later deleted. `detect-secrets` adds
entropy detection and keeps a reviewed baseline.

Two limits worth stating plainly.

**Rotation is not a check.** Neither scanner can tell you whether a credential it
found has been revoked. A scan that goes green after a secret is deleted from
the working tree has reported on the tree, not on the secret. The key is valid
until somebody rotates it, and that step belongs to a person.

**A baseline is a list of accepted findings, and it belongs to the adopting
project.** `--baseline` stays relative to the project rather than travelling with
the jig, so no adopter is judged against another project's accepted findings. A
baseline that is never re-reviewed will absorb real findings, which is the cost
of having one.

## Suppressions

There is no `SUPPRESSIONS` file here, because nothing in this repository is
silenced. The `suppressions` task fails in both directions: an unregistered
pragma is a suppression nobody justified, and a registered row with nothing
behind it is a justification for something that has already gone, which reads as
cover for whatever replaces it.

# A finding phrased as a conclusion has no seam to check at

Six wrong claims travelled between sessions on 2026-08-28, in both directions,
and every one was caught by somebody else's arithmetic rather than by care. The
pattern underneath them is the useful part, and it is not "verify what you are
told", which nobody can do at scale.

## What went wrong, and it went wrong both ways

**Into this repository.** infobot reported two shell shims "gated by nothing",
and toolbox repeated it into two committed task files without opening
`cmd/statusline/`. Their behaviour is tested: five cases, each marked, running
the real file. **Unread is not untested**, and the two are one word apart.

**Out of this repository.** A task here carried "dotfiles has 8 bash scripts and
10 zsh fragments" with no command and no date. It was correct when taken, at
dotfiles `2979efd` on 2026-08-19, and the window was three days: `config/zsh`
held ten fragments only until `f4d7837`. **A right measurement became
unreconstructable within a week and nothing about it looked stale.** infobot
relayed it into their own task and designed a paragraph around it before
discovering it could not be checked.

**Inside one paragraph.** Checking that figure caught its neighbour:
`install.sh` recorded at 4,380 bytes against an actual 4,376. Four bytes,
nothing turning on it, and it would never have been found, because nobody
re-measures a byte count that is not adjacent to one under suspicion.

## The rule, which is infobot's

> **Relayed findings should carry the command, not the conclusion, and a finding
> that cannot carry its command is a lead by construction.**

Both failures happened because the claim arrived **already phrased as a
conclusion**, so there was nothing to check at.

    no seam    gated by nothing
    no seam    8 bash scripts and 10 zsh fragments
    no seam    install.sh is 4,380 bytes

    three      wc -c install.sh -> 4376, 2026-08-28
    seams      the command, the number, and the date, any of which
               failing is visible

Carrying the command is what makes checking cheap enough to actually happen.
That is the whole difference between a rule that survives a busy session and one
that does not.

## The corollary that changed how a task got planned

A relayed instance is **a lead to ask its owner about, never an instance to
design against.**

silo offered eight instances of a fault and shrank the list to the two they held
first-hand, declining to pass on six from another session's log. skid declined
the same way an hour earlier. Both were right, and the reason is stronger than
courtesy:

> The consequence was not available to anyone who did not know what
> `bin/infobot` is for, so it could not have been relayed at all. Only
> re-derived at the far end.

**A relay does not summarise badly. A relay cannot carry what depends on knowing
why a file exists.** The owner is not the preferred source; it is the only
source that holds the consequence. Measured across the eight: seven were found
by the session that owned the defective thing.

## What it cost, and what it bought

Nothing shipped wrong, because each error was caught within hours by a session
re-measuring rather than re-reading. What it cost was two committed task files
carrying an overstatement, a paragraph designed against a figure that did not
check out, and several hours of two sessions arguing from different numbers for
the same tree.

What it bought is that every figure in this repository's task tree now carries
the command that produced it and the date it was taken.

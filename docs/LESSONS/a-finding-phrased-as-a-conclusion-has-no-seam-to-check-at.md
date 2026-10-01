# A finding phrased as a conclusion has no seam to check at

A claim relayed between projects as a conclusion cannot be checked by whoever
receives it. A claim relayed with the command that produced it can. Asking
everyone to verify what they are told does not scale; asking for the command
does.

## Three instances

**A conclusion relayed in.** infobot reported two shell shims "gated by
nothing", and two toolbox task files repeated it without opening
`cmd/statusline/`. Their behaviour is tested: five cases, each marked, running
the real file. Unread is not the same as untested.

**A measurement relayed out with no command.** A task here carried "dotfiles has
8 bash scripts and 10 zsh fragments" with no command and no date. It was correct
at dotfiles `2979efd` on 2026-08-19, and `config/zsh` held ten fragments only
until `f4d7837`, three days later. Nothing about the figure looked stale, and
infobot designed a paragraph around it before finding it could not be checked.

Re-measuring that figure also caught the one next to it: `install.sh` recorded at 4,380 bytes against an actual 4,376. Nobody
re-measures a byte count unless it sits next to one under suspicion.

## The rule, which is infobot's

> **Relayed findings should carry the command, not the conclusion, and a finding
> that cannot carry its command is a lead by construction.**

    no seam    gated by nothing
    no seam    8 bash scripts and 10 zsh fragments
    no seam    install.sh is 4,380 bytes

    three      wc -c install.sh -> 4376, 2026-08-28
    seams      the command, the number, and the date, any of which
               failing is visible

Carrying the command makes checking cheap enough to be done.

## The corollary for planning

A relayed instance is a lead to ask its owner about, never an instance to design
against.

> The consequence was not available to anyone who did not know what
> `bin/infobot` is for, so it could not have been relayed at all. Only
> re-derived at the far end.

A relay cannot carry what depends on knowing why a file exists. The project that
owns the file is the only source that holds the consequence: of eight instances
of one fault offered across projects, seven were found in the project that owned
the defective thing.

## What it costs

Two committed task files carrying an overstatement, a paragraph designed against
a figure that did not check out, and two projects arguing from different numbers
for the same tree. Every figure in this repository's task tree now carries the
command that produced it and the date it was taken.

# Stay safe

[![Checks on main](https://github.com/chalkbadger/stay-safe/actions/workflows/checks.yml/badge.svg?branch=main&event=push)](https://github.com/chalkbadger/stay-safe/actions/workflows/checks.yml?query=branch%3Amain+event%3Apush)

Check your Codex settings and saved approvals with three questions in mind.

- **What have I allowed Codex to do?**
- **Which actions do my settings let Codex take on its own, and which need my approval?**
- **What should I change if that’s more access than I want?**

stay-safe is a pre-1.0 tool for Unix. Version 0.2.4 checks Codex settings and saved approvals. Starting in 0.3.0, it also reads Claude Code user settings. The report names defaults and incomplete checks. It can’t confirm live connections or what the agent will allow. See the [full scope](docs/report.md#full-scope).

Each finding names its rule and setting and links to evidence. You can [challenge a finding](https://github.com/chalkbadger/stay-safe/issues/new?template=challenge.yml). Coding agents help write and review changes using [Wirth](https://github.com/chalkbadger/wirth). The maintainer decides what to merge.

Here’s an excerpt from a finding on a [test configuration](tests/runs_without_a_coding_agent/sample.toml).

> **With these settings, Codex runs commands without asking you.** It won't ask before any command it's allowed to run, so injected or mistaken instructions could make it run code you didn't want.
>
> *How it has gone wrong:* Agents running commands without approval have run a delete command aimed at a home directory and wiped a drive. Another user reported an automatic driver update while getting help with GPU performance. [I2](https://github.com/chalkbadger/stay-safe/blob/v0.2.4/incidents.md#i2-home-directory-added-to-a-delete-command), [I3](https://github.com/chalkbadger/stay-safe/blob/v0.2.4/incidents.md#i3-windows-drive-wiped), [I24](https://github.com/chalkbadger/stay-safe/blob/v0.2.4/incidents.md#i24-driver-update-followed-by-boot-and-network-failures) (reported, not verified).

[Read the full finding and what to change.](docs/report.md#example-finding) [See a sample report.](https://github.com/chalkbadger/stay-safe/issues/208#issuecomment-7147713051)

Use Python 3.11 or newer. If your Python is older or missing,
follow [Python setup](docs/usage.md#python-setup), then use that interpreter in
the commands below. No agent is needed:

```sh
git clone --branch v0.3.0 https://github.com/chalkbadger/stay-safe.git
cd stay-safe
python3 -m stay_safe
```

Without Git, [download the v0.3.0 ZIP](https://github.com/chalkbadger/stay-safe/archive/refs/tags/v0.3.0.zip) and extract it. Open a terminal in the folder containing the extracted `stay-safe-0.3.0` folder, then run:

```sh
cd stay-safe-0.3.0
python3 -m stay_safe
```

By default it reads `~/.codex/config.toml` (`$CODEX_HOME/config.toml` when `CODEX_HOME` is set). [Usage](docs/usage.md) covers the inspected files, options, `--save` and exit status.

## Run with uv

If you already use [uv](https://docs.astral.sh/uv/), run the
[published 0.3.0 package](https://pypi.org/project/stay-safe/0.3.0/):

```sh
uvx --python 3.11 stay-safe@0.3.0
```

The command asks uv for Python 3.11, downloading it if needed; your system Python
stays unchanged. Add `--save` to save the HTML report in your current directory.
The clone and ZIP routes above do not require uv.

## Ask Codex

Paste this into Codex in the ChatGPT app or the CLI:

```text
Download stay-safe at tag v0.3.0 from https://github.com/chalkbadger/stay-safe into
a new temporary folder and run `python3 -m stay_safe` there. First identify where
your execution tools run and which environment you will inspect. If my intended
configuration is unavailable there, stop and explain. If Python is too old or missing,
point me to https://github.com/chalkbadger/stay-safe/blob/main/docs/usage.md#python-setup
and let me install it myself. Show the report exactly
as printed, with its exit status, then your notes under "Agent's own report". Don't
open auth files or change files outside that folder. If the download fails, stop and
tell me.
```

In "Ask for approval" mode, approve the one internet request; never choose "don't ask
again". If Codex can't download, see [Usage](docs/usage.md#if-codex-cant-download).

## What it checks and what it can't see

A saved approval may cover more than the action you remember. For example, an
approval for every use of a program you used to download a file can cover uploads
too. Check what the rule covers and whether that program has network access.

- It reads the files listed in [Usage](docs/usage.md) and changes nothing in your setup.
- Each warning names its rule and the setting behind it, and links to [incident reports](incidents.md). [Reading the report](docs/report.md) explains each part.
- The [Codex meanings table](harnesses/codex.md) lists the settings it checks and the sources it uses. The report says when it used a default or could not complete a check.
- The [full scope](docs/report.md#full-scope) explains what it does not inspect.
- It shows server, app and tool names as written. Check those names before sharing the report. If a name is private, reproduce the finding with made-up names and share that report.

## Could someone use Codex to take private data?

Suppose you ask Codex to investigate a bug someone reported in a public issue.

1. **How could an attacker get in?** The person who filed the issue asks for a
   diagnostic log. Could Codex mistake their request for an instruction from you?
2. **What could they get to that’s worth taking?** Could Codex read a private log
   containing customer details while it investigates?
3. **How could they get it out?** Could Codex attach that log to a public reply
   the attacker can read? Would it ask you before posting?

For someone to take data this way, all three have to line up. The report can
show which settings matter. You know who can file issues and what your logs
contain. If one step is unclear, check that step. If Codex only needs to read
issues, giving its issue tool read-only access closes this way out.

## Challenge a finding

Two challenges help improve the report. Show us a risk it missed, or a warning
it gave even though the settings already block the action it describes.

Use the [challenge form](https://github.com/chalkbadger/stay-safe/issues/new?template=challenge.yml) to submit the finding, revision, disputed claim and evidence.
Read [past challenges and their outcomes](https://github.com/chalkbadger/stay-safe/issues/211#issuecomment-7147613949).

## Why stay-safe exists

stay-safe is part of [chalkbadger](https://github.com/chalkbadger), which works on AI safety through adversarial peer review.

Explore the [claims and their evidence](docs/report.md#where-the-claims-come-from):
[Understanding configuration findings](docs/report.md#understanding-configuration-findings)
or [Using and trusting the tool](docs/report.md#using-and-trusting-the-tool).

## Develop

Git is required for the development tests. Run `python3 check_tests.py` in a
development virtual environment. Before the first run, install the build tools
with `python3 -m pip install build "setuptools>=77" wheel fastjsonschema==2.21.2`.
This checks test-folder package markers before running unittest discovery.

## Contribute

Share feedback, challenge a finding or propose a change through [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Licensed under the [Apache License, Version 2.0](LICENSE).

References to an *archived* issue or PR point to the private repository that holds this project's earlier working history.

# Using stay-safe

The [README](../README.md) has the three commands that download a release and run it, and
the prompt that asks Codex to run it for you. This page covers the rest.

## Python setup

Stay Safe needs Python 3.11 or newer. In a terminal, check the Python you will use:

```sh
python3 --version
```

If it reports 3.11 or newer, continue with the README's run command. If the command
is missing or the version is older, use a supported Python already installed, or
install one yourself:

- **macOS:** follow [Python's official macOS installation guide](https://docs.python.org/3/using/mac.html).
  Choose a currently supported release from [python.org](https://www.python.org/downloads/macos/).
- **Linux:** follow [Python's official Unix guidance](https://docs.python.org/3/using/unix.html#getting-and-installing-the-latest-version-of-python)
  and your distribution's instructions for installing a supported Python alongside
  its system Python.

Keep the operating system's Python. After installation, open a new terminal and
verify the command for the version you installed. For example, if you installed
Python 3.15:

```sh
python3.15 --version
python3.15 -m stay_safe
```

Run the second command from the extracted Stay Safe folder (the folder containing
`stay_safe`). Replace `python3.15` with your installed version's command, or its
quoted absolute executable path. Use that same interpreter wherever these
instructions say `python3`. Installing a newer version does not necessarily change
what `python3` launches. No pip install or uv is needed for the clone/ZIP flow.

The older-Python error may suggest an existing 3.11–3.13 command. If another
supported version is installed, verify and use its command as above. Releases
before this guidance may say to install Python and run `python3.11`; use the version
you actually installed instead.

## Options

There are no third-party dependencies. From this checkout:

```sh
python3 -m stay_safe
python3 -m stay_safe --config /path/to/config.toml
python3 -m stay_safe --config /path/to/user.toml --config /path/to/project.toml
python3 -m stay_safe --config /path/to/config.toml --format json
python3 -m stay_safe --rules /path/to/default.rules
python3 -m stay_safe --config /path/to/config.toml --rules /path/to/default.rules
python3 -m stay_safe --save
```

Explicit `--config` and `--rules` options inspect only the selected files as
independent snapshots. Select at most one rules file. The report goes to standard
output and nothing is written. Redirect it to a new file to share it; never redirect onto an input file.

To check whether a Codex settings file explicitly grants sandboxed commands write access to a
project’s `.codex` directory, name the project you use with Codex:

```sh
python3 -m stay_safe --workspace /path/to/project --config /path/to/config.toml
```

You can also use `--workspace DIR` with the usual Codex settings discovery. The option supplies a
directory for comparison. It does not select any additional configuration files. Use a direct
path to the project. stay-safe compares each file's absolute and home-relative roots after applying
Codex's path normalization. A home-relative root needs an absolute `HOME`. If it is missing or
relative, the report names those unchecked entries and still reports any independent direct grant.
Other relative roots, unresolved aliases and the wider effects of the
folders remain under “Not checked.”
See the [Codex meanings](../harnesses/codex.md) for the configured boundary.

## How files are found

For a Codex report with no file arguments, the reader opens `config.toml` and `rules/default.rules`
under `$CODEX_HOME`, falling back to `~/.codex` when it is unset or empty, as
Codex does. Other `.rules` files in that `rules/` directory are not read; their
presence, or a `rules/` directory that cannot be listed, is an inspection gap.
So are a `hooks.json` file, plugins in `plugins/cache`, skills in `skills` and an
`environments.toml` file, which are not read, an `environments.toml` that is not a
file, and a failure to check the last three. The default scan looks for visible user
skills under the Codex skills folder. It skips hidden folders, including the bundled
`.system` folder. A
`CODEX_HOME` that is missing or not a directory, or a home directory that cannot
be determined, is an inspection gap and no defaults are assessed.

When automatic discovery finds no default configuration file, the report identifies
its absence and assesses documented defaults (shell environment, the ChatGPT Apps connection). Approval and sandbox
settings remain unknown, so this assessment still exits `2`. See the
[inspection contract](../contracts/claims.md#see_every_connection_and_setting-i-see-supported-settings-and-saved-approvals-from-my-files-with-defaults-identified) for the behavior and checks.

## Claude Code: `--agent`

With no file or agent selected, stay-safe checks each agent whose settings folder it
finds. A Claude-only home gets a Claude Code report. If neither folder exists, you
get the usual Codex default assessment. A nonempty `CODEX_HOME` or `CLAUDE_CONFIG_DIR`
selects that folder even when it cannot be inspected. That report names the gap and
the command exits 2, alongside any findings for the other agent.

With `--format json`, a single report is an object with a `harness` field. For two
agents the outer object contains a `reports` array, with Codex first and Claude Code
second.

```sh
python3 -m stay_safe --agent claude
python3 -m stay_safe --agent codex
python3 -m stay_safe --agent claude --config /path/to/settings.json
```

Claude Code discovery reads `settings.json` under `$CLAUDE_CONFIG_DIR` or
`~/.claude`, and the project's `.claude/settings.json` in the current folder. Run
stay-safe from the folder where you start Claude Code to include that project file.
Command hooks are reported as programs Claude Code starts and HTTP hooks as network
access, with commands and addresses withheld. A project file is read even without
`~/.claude`.
To inspect another settings file, pass `--agent claude --config FILE`.
Each selected file is a separate snapshot. Account data, managed settings and
extension folders are outside discovery. The [Claude Code meanings table](../harnesses/claude-code.md)
lists the supported settings and their sources.

Without `--agent`, `--config` and `--rules` select Codex. Select one agent when
passing `--config`. Only Codex accepts `--rules`. Both options skip files named
`.claude.json` or `.credentials.json` and report an inspection gap.

## Export findings as SARIF

```sh
python3 -m stay_safe --format sarif > stay-safe.sarif
```

Open the file in a SARIF 2.1.0 viewer. Each agent has a run containing findings
as results and inspection gaps as warnings in its invocation. A logical location
identifies the setting. Review visible configuration names before sharing.
A complete inspection with no findings produces no results or warnings and exits 0.
An incomplete inspection still writes the document and exits 2. For example, if
your selected rules file is missing, its run contains a warning about the file.

## Save the report as a page: `--save`

`--save` also writes the report as a self-contained page, `stay-safe-report.html`, in
the current directory for an installed package, or the stay-safe folder for a clone
or ZIP, replacing the one from the previous run. It prints the same report,
then one last line with a command that opens the page: `open '<path>'` on macOS,
`xdg-open '<path>'` elsewhere, with the path quoted for the shell. Paste that command to
read the formatted report in your browser; stay-safe doesn't run it. Attach the file to
share it; the last line names the saved location, so leave it out when you share the
printed report. The page has the same content as the Markdown
report, and no scripts or network requests: it uses only document structure, text and link
elements ([HTML element index](https://html.spec.whatwg.org/multipage/indices.html#elements-3)), and its headings
carry the [anchors GitHub gives them](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#section-links), so the report's own links work on the page. It is the only file stay-safe's code writes,
and only with `--save`; Python itself may cache compiled code in `stay_safe/__pycache__`. If the page can't be written, for example in a read-only sandbox,
stay-safe says so in one line and prints the report. `--save` can't be combined
with `--format json` or `--format sarif`.

## Symlinks

A symlinked configuration or rules file is refused and reported as an inspection gap. stay-safe opens each file
with `O_NOFOLLOW`, which [fails when the last part of the path is a link](https://pubs.opengroup.org/onlinepubs/9799919799/functions/open.html).

## Platforms

stay-safe runs only on Unix. CI runs the test suite on Linux and macOS with
Python 3.11 and the latest 3.x; Windows is untested.

## Exit status

Exit status `0` means the supported fields in the selected files were inspected;
it is not a safety score. Status `2` means the report names inspection gaps (listed under Not checked), or the arguments were invalid and no report was produced.
See [the inspection-limits contract](../contracts/claims.md#understand_inspection_limits-i-can-tell-what-the-report-establishes-and-what-needs-further-checking)
for what accompanies a report with gaps.

## If Codex can't download

Some sandboxes block Codex's download. Download the
[v0.3.0 ZIP](https://github.com/chalkbadger/stay-safe/archive/refs/tags/v0.3.0.zip)
yourself on the computer the agent can access. Copy the archive's full path:
in macOS Finder, select it and press Option-Command-C; on Linux, use your file
manager's copy-location action. Replace `ARCHIVE_PATH` below with that actual
absolute path, keeping the quotes, then paste the prompt into Codex:

```text
Extract the Stay Safe ZIP at "ARCHIVE_PATH" into a new temporary folder. Enter
its stay-safe-0.3.0 folder and run `python3 -m stay_safe` with an available
Python 3.11+ interpreter. First identify where your execution tools run and which
environment you will inspect. If my intended configuration or the archive is
unavailable there, stop and explain. If Python is too old or missing, point me to
https://github.com/chalkbadger/stay-safe/blob/main/docs/usage.md#python-setup
and let me install it myself. Show the report exactly as printed, with its exit
status, then your notes under "Agent's own report". Don't open auth files or change
files outside the new temporary folder.
```

The report then marks its commit "(release archive)"; see
[the commit and release archives](report.md#the-commit-and-release-archives).

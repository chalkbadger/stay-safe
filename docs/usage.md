# Using stay-safe

The [README](../README.md) has the three commands that download a release and run it, and
the prompt that asks Codex to run it for you. This page covers the rest.

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

## How files are found

With no file arguments, the reader opens `config.toml` and `rules/default.rules`
under `$CODEX_HOME`, falling back to `~/.codex` when it is unset or empty, as
Codex does. Other `.rules` files in that `rules/` directory are not read; their
presence, or a `rules/` directory that cannot be listed, is an inspection gap. A
`CODEX_HOME` that is missing or not a directory, or a home directory that cannot
be determined, is an inspection gap and no defaults are assessed.

When automatic discovery finds no default configuration file, the report identifies
its absence and assesses documented defaults (shell environment, the ChatGPT Apps connection). Approval and sandbox
settings remain unknown, so this assessment still exits `2`. See the
[no-config-file contract](../contracts/claims.md#works_without_a_config_file-with-no-config-file-the-report-looks-where-codex-looks-and-tells-me-which-codex-defaults-apply) for the behavior and checks.

## Save the report as a page: `--save`

`--save` also writes the report as a self-contained page, `stay-safe-report.html`, in
this checkout, replacing the one from the previous run. It prints the same Markdown report,
then one last line with a command that opens the page: `open '<path>'` on macOS,
`xdg-open '<path>'` elsewhere, with the path quoted for the shell. Paste that command to
read the formatted report in your browser; stay-safe doesn't run it. Attach the file to
share it; the last line names your checkout's folder, so leave it out when you share the
printed report. The page has the same content as the Markdown
report, and no scripts or network requests. It is the only file stay-safe's code writes,
and only with `--save`; Python itself may cache compiled code in `stay_safe/__pycache__`. If the page can't be written, for example in a read-only sandbox,
stay-safe says so in one line and prints the Markdown report. `--save` can't be combined
with `--format json`.

## Symlinks

A symlinked configuration or rules file is refused and reported as an inspection gap.

## Platforms

stay-safe runs only on Unix. CI runs the test suite on Linux and macOS with
Python 3.11 and the latest 3.x; Windows is untested.

## Exit status

Exit status `0` means the supported fields in the selected files were inspected;
it is not a safety score. Status `2` means the report names inspection gaps (listed under Not checked), or the arguments were invalid and no report was produced.
See [the incomplete-inspection explanation contract](../contracts/claims.md#explains_incomplete_inspection-when-my-report-has-gaps-i-see-why-the-run-exits-2)
for what accompanies a report with gaps.

## If Codex can't download

Some sandboxes block Codex's download. Remove any `stay-safe-0.2.0*` file (any case)
from the project Codex is working in, then download
https://github.com/chalkbadger/stay-safe/archive/refs/tags/v0.2.0.zip into it, so it is
the only such file. Then paste this into Codex:

```text
Unzip stay-safe-0.2.0.zip from this project into a new temporary folder and run
`python3 -m stay_safe` from the `stay-safe-0.2.0` folder inside. Show the report exactly
as printed, with its exit status, then your notes under "Agent's own report". Don't
open auth files or change files outside the new temporary folder.
```

The report then marks its commit "(release archive)"; see
[the commit and release archives](report.md#the-commit-and-release-archives).

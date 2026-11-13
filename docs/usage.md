# Using stay-safe

The [README](../README.md#start-here) gives users one prompt to start with.
The steps below tell the agent how to choose the setup route.

## First run

Use Stay Safe **0.2.3**, source commit
`bf8de56a6ea20dadae0fd847e7b3773236aa0c64`, for every route below.
These are setup instructions for an agent with shell and download tools, not a
script. Stop if this guide or a required tool is unavailable; do not invent a
replacement installer or fall back to an unpinned release.

### Identify the environment

Before downloading anything, identify the OS and architecture and whether your
commands run on the user's computer or in a remote/cloud environment. Say which
environment you intend to inspect. Do not infer local access from the user's OS
or from a browser running on their computer. If the execution location is unclear,
ask before proceeding.

On macOS and Linux, continue with configuration available to that session.
Keep `HOME` and `CODEX_HOME` unchanged: they determine where the diagnostic looks.
If the user wants their laptop checked but you run in the cloud without access
to that configuration, stop and explain. Do not copy private configuration to the
cloud or present the cloud's report as the laptop's. If the diagnostic finds no
configuration, show its report of that absence; do not claim that it inspected a
file. An unreadable file remains an inspection gap.

Native Windows is not supported. WSL is a Linux environment, but this onboarding
flow has not yet been verified there. Do not install WSL or switch into it silently.
A WSL report must identify whether it inspected WSL configuration or files the user
explicitly selected; it does not establish Windows-host permissions.

### Choose the route

Create a new temporary folder with `mktemp -d` and keep its absolute path as
`run_dir`. Do not use a user's existing project as the download destination.
Resolve available commands to absolute paths and check their versions. Check for
`uvx`/`uv` first; otherwise check available Python commands for version 3.11 or newer.
Use only successful version checks; a command name alone does not establish its
version. Do not change `PATH`, `HOME` or `CODEX_HOME` to select the route.

For any uv invocation, set these variables for that command only:

| Variable | Value |
| --- | --- |
| `UV_CACHE_DIR` | `$run_dir/cache` |
| `UV_PYTHON_INSTALL_DIR` | `$run_dir/python` |
| `UV_TOOL_DIR` | `$run_dir/tools` |
| `UV_PYTHON_INSTALL_BIN` | `0` |

1. **uv is available:** use its absolute `uvx` path (or `uv tool run`) with
   `--python 3.11 stay-safe@0.2.3`. If Python 3.11 is missing, explain and ask before
   letting uv download it. A rejected or failed download stops the run.
2. **Python 3.11+ is available without uv:** download the
   [0.2.3 source distribution](https://files.pythonhosted.org/packages/6e/5a/d70be8a8696180404d91ac1dfd43123634cf2d25a5ee0a72ea84e58b1170/stay_safe-0.2.3.tar.gz)
   into the temporary folder. Its SHA-256 is
   `ba0f42384ad410d766fde1c1e731349d744b79e57d8f56dcd5d2009f7b2eab64`.
   Verify the download against that digest, then extract it there and use the
   absolute Python path to run `-B -m stay_safe` from `stay_safe-0.2.3`.
   No pip installation or Git checkout is needed.
3. **Neither is available:** ask: “May I download uv and Python into a temporary
   folder to run Stay Safe? I won't replace your Python or change your shell or
   Codex settings.” If accepted, download
   `https://astral.sh/uv/0.13.8/install.sh` into that folder. Check that the download
   succeeded before running the saved script with `sh` and
   `UV_UNMANAGED_INSTALL="$run_dir/bin"`. Then use the installed absolute `uvx`
   path and the command-local variables above to run route 1. Do not ask again
   for the Python download already accepted here.

The pinned uv [installer documentation](https://github.com/astral-sh/uv/blob/0.13.8/docs/reference/installer.md#unmanaged-installations)
explains unmanaged installation. Only the installed uv binary goes in `bin`;
its Python, tool and cache locations must also be set as above. Do not use sudo,
edit shell profiles, replace system Python, upgrade existing tools or change
Codex settings. Normal host approval controls still apply; do not bypass them.

### Run and show the result

Run from the temporary folder (or extracted source folder for route 2). Pass
`--format markdown` so the captured report is consistent. Let Stay Safe discover
its default files unless the user explicitly selected `--config` or `--rules`.
Do not inspect authentication files, print raw configuration, start configured
programs or probe services as part of setup or diagnosis.

Capture the exit status immediately. Show the diagnostic's stdout unchanged,
including findings and gaps, with stderr and the exit status separately. Put
explanations under “Agent's own report.” A report with exit 2 is an incomplete
inspection, not an installation failure; do not discard it or retry with broader
permissions. If no report was produced, say which setup step failed. A declined
request stops setup without claiming the diagnostic ran.

Tell the user where the temporary folder is and leave it in place. If they ask
for a saved page, rerun with `--save` and show the path it prints. Review names
before sharing the report; nothing is uploaded automatically.

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
the current directory for an installed package, or the stay-safe folder for a clone
or ZIP, replacing the one from the previous run. It prints the same report,
then one last line with a command that opens the page: `open '<path>'` on macOS,
`xdg-open '<path>'` elsewhere, with the path quoted for the shell. Paste that command to
read the formatted report in your browser; stay-safe doesn't run it. Attach the file to
share it; the last line names the saved location, so leave it out when you share the
printed report. The page has the same content as the Markdown
report, and no scripts or network requests. It is the only file stay-safe's code writes,
and only with `--save`; Python itself may cache compiled code in `stay_safe/__pycache__`. If the page can't be written, for example in a read-only sandbox,
stay-safe says so in one line and prints the report. `--save` can't be combined
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

## If the agent cannot download

Stop and explain which download failed. The user can use the
[manual instructions](../README.md#run-it-yourself) on the machine they want to
inspect. Do not change network or approval settings to get past the failure.

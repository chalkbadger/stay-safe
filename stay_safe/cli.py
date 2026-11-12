"""The command line: read the selected Codex files and print the report."""
import argparse
import os
from pathlib import Path
import sys

from .report import inspect, render
from .save import NAME, save

NOT_SAVED = f"Could not save {NAME} in the stay-safe folder; the full report follows.\n"


def open_command(path, platform=None):
    """The line `--save` ends with: a command the user can paste to open the page (archived issue #106).

    stay-safe doesn't run it. The plain path is put in single quotes, where the shell expands nothing, and each `'`
    in it is written as '"'"'; so spaces, double quotes, `$`, backticks and `!` reach the command unchanged.
    """
    opener = "open" if (platform or sys.platform) == "darwin" else "xdg-open"
    quoted = "'" + str(path).replace("'", "'\"'\"'") + "'"
    return f"Saved the formatted report. Open it with: {opener} {quoted}\n"

SYSTEM = Path("/etc/codex")
# The command --help names: the same for `python3 -m stay_safe` and `python3 stay_safe` (issue #48), in the form
# Python 3.14's argparse gives `-m` itself.
PROG = (sys.executable.rsplit("/", 1)[-1] or "python3") + " -m stay_safe"


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "Invalid arguments. Use --help.\n")


def codex_home():
    """Select the directory Codex's find_codex_home selects, or return the gap that stops Codex."""
    value = os.environ.get("CODEX_HOME", "")
    if value:
        try:
            if Path(value).is_dir():
                return Path(value), None
        except OSError:
            pass
        return None, ("Codex home: CODEX_HOME is set but is missing, not a directory or cannot be checked; "
                      "Codex would not start, so no default files were inspected.")
    if os.environ.get("HOME") != "":
        try:
            return Path.home() / ".codex", None
        except RuntimeError:
            pass
    return None, ("Codex home: CODEX_HOME is unset and the home directory cannot be determined; "
                  "no default files were inspected.")


def hooks_json(home):
    """Codex loads hooks.json beside config.toml when Rust's Path::is_file is true; errors count as false."""
    try:
        return (home / "hooks.json").is_file()
    except OSError:
        return False


def plugins_cache(home):
    """Return the observed or unreadable cache gap, or no gap when no version folder is found."""
    def folders(path):
        return [path / name for name in os.listdir(path) if (path / name).is_dir()]
    try:
        if any(folders(plugin) for market in folders(home / "plugins" / "cache") for plugin in folders(market)):
            return "Codex home: plugins/cache holds Codex plugins that were not inspected."
    except FileNotFoundError:
        pass
    except OSError:
        return ("Codex home: Could not check the plugin cache. "
                "Check that you can open plugins/cache in your Codex folder.")
    return None


def system_config():
    """Whether Codex's system config folder holds a file Codex loads, or a rules/ folder it cannot list."""
    try:
        if not SYSTEM.is_dir():
            return False
        names = ("config.toml", "managed_config.toml", "requirements.toml")
        if hooks_json(SYSTEM) or any((SYSTEM / name).is_file() for name in names):
            return True
        return any(name.endswith(".rules") for name in os.listdir(SYSTEM / "rules"))
    except FileNotFoundError:
        return False
    except OSError:
        return True


def main(argv=None):
    parser = Parser(prog=PROG, description="Read Codex configuration files and print a shareable report.")
    parser.add_argument("--config", action="append", metavar="FILE", help="Inspect this file independently; repeat for more files.")
    parser.add_argument("--rules", action="append", metavar="FILE", help="Inspect one saved-rules file independently.")
    parser.add_argument("--format", choices=("markdown", "json"))
    parser.add_argument("--save", action="store_true",
                        help=f"Also save the report as a formatted page, {NAME}, in this checkout, and end with a command "
                             "that opens it. Not with --format json.")
    args, extra = parser.parse_known_args(argv)
    if args.save and len(extra) == 1 and not extra[0].startswith("-"):
        parser.exit(2, f"--save takes no path. It saves {NAME} in the stay-safe folder.\n")
    if extra:
        parser.error("Unexpected arguments.")
    if args.rules and len(args.rules) != 1:
        parser.error("Only one rules file may be selected.")
    if args.save and args.format == "json":
        # A fixed message: it names the options, never a value the user typed.
        parser.exit(2, "--save can't be combined with --format json. Use --help.\n")
    paths = [Path(p) for p in args.config or []]
    rules = Path(args.rules[0]) if args.rules else None
    defaults = not args.config and not args.rules
    gaps, files = [], {}
    if defaults:
        home, gap = codex_home()
        if home is None:
            paths, rules, gaps = [], None, [gap]
        else:
            paths = [home / "config.toml"]
            rules = home / "rules" / "default.rules"
            # The report names these files by where Codex keeps them, never by the expanded folder.
            base = "$CODEX_HOME" if os.environ.get("CODEX_HOME", "") else "~/.codex"
            files = {"config-1": f"{base}/config.toml", "rules-1": f"{base}/rules/default.rules"}
            if hooks_json(home):
                gaps.append("Codex home: hooks.json exists and was not inspected.")
            cache_gap = plugins_cache(home)
            if cache_gap:
                gaps.append(cache_gap)
            if system_config():
                gaps.append("System config folder: /etc/codex holds Codex configuration that was not inspected.")
    result = inspect(paths, rules_path=rules, discovered=defaults, gaps=gaps)
    status = 2 if result["inspection_gaps"] else 0
    path = save(render(result, "html", files)) if args.save else None
    if args.save and path is None:
        sys.stderr.write(NOT_SAVED)
        sys.stderr.flush()
    terminal = args.format is None and sys.stdout.isatty()
    sys.stdout.write(render(result, args.format or ("plain" if terminal else "markdown"), files))
    if path is not None:
        sys.stdout.write(open_command(path))
    if terminal and not args.save:
        sys.stdout.flush()
        sys.stderr.write("Use --save to save a formatted HTML report.\n")
    if status == 2:
        sys.stdout.flush()
        sys.stderr.write("Inspection incomplete (exit 2). See the report for what wasn't checked.\n")
    return status


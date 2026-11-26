import argparse
import os
from pathlib import Path
import stat
import sys

from . import claude_report
from .report import inspect, render_all
from .save import NAME, save
from .provenance import INSTALLED

FEEDBACK = "Report a problem or suggest an idea: https://github.com/chalkbadger/stay-safe/issues/new/choose\n"
SAVE_FOLDER = "the current directory" if INSTALLED else "the stay-safe folder"
NOT_SAVED = f"Could not save {NAME} in {SAVE_FOLDER}; the full report follows.\n"


def open_command(path, platform=None):
    opener = "open" if (platform or sys.platform) == "darwin" else "xdg-open"
    quoted = "'" + str(path).replace("'", "'\"'\"'") + "'"
    return f"Saved the formatted report. Open it with: {opener} {quoted}\n"

SYSTEM = Path("/etc/codex")
AGENTS = ("codex", "claude")
PROG = (sys.executable.rsplit("/", 1)[-1] or "python3") + " -m stay_safe"


class Parser(argparse.ArgumentParser):
    def exit(self, status=0, message=None):
        if status:
            message = (message or "") + FEEDBACK
        super().exit(status, message)

    def error(self, message):
        self.exit(2, "Invalid arguments. Use --help.\n")


def codex_home():
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
    try:
        return (home / "hooks.json").is_file()
    except OSError:
        return False


def plugins_cache(home):
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


def skills(home):
    root = home / "skills"
    failed = False

    def mode(path, follow=True):
        try:
            return stat.S_IFMT(path.stat(follow_symlinks=follow).st_mode)
        except (FileNotFoundError, NotADirectoryError):
            return None

    try:
        if mode(root) != stat.S_IFDIR:
            return None
        seen = {root.resolve()}
        queue = [(root, 0)]
        for folder, depth in queue:
            try:
                names = sorted(os.listdir(folder))
            except OSError:
                failed = True
                continue
            for name in names:
                path = folder / name
                try:
                    kind = mode(path)
                    if mode(path, follow=False) == stat.S_IFLNK and kind != stat.S_IFDIR:
                        continue
                    if name == "SKILL.md" and kind == stat.S_IFREG:
                        return "Codex home: skills holds Codex skills that were not inspected."
                    if kind == stat.S_IFDIR and depth < 6 and not name.startswith(".") and path.resolve() not in seen:
                        seen.add(path.resolve())
                        queue.append((path, depth + 1))
                except OSError:
                    failed = True
    except OSError:
        failed = True
    if failed:
        return ("Codex home: Could not check the skills folder. "
                "Check that you can open skills in your Codex folder.")
    return None


def environments_toml(home):
    try:
        if not stat.S_ISREG((home / "environments.toml").stat().st_mode):
            return "Codex home: environments.toml is not a file; Codex fails to read it."
    except (FileNotFoundError, NotADirectoryError):
        return None
    except OSError:
        return ("Codex home: Could not check environments.toml. "
                "Check that you can open environments.toml in your Codex folder.")
    return "Codex home: environments.toml exists and was not inspected."


def system_config():
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


def directory_status(path):
    try:
        return "directory" if stat.S_ISDIR(path.stat().st_mode) else "not a directory"
    except FileNotFoundError:
        return "missing"
    except OSError:
        return "unreadable"


def claude_home(chosen):
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    label = "$CLAUDE_CONFIG_DIR" if override else "~/.claude"
    home = None
    if override:
        home = Path(override)
    elif os.environ.get("HOME") or (chosen and "HOME" not in os.environ):
        try:
            home = Path.home() / ".claude"
        except RuntimeError:
            pass
    status = directory_status(home) if home is not None else "missing"
    return home, label, status


def claude_project(home):
    folder = Path(".claude")
    unchecked = "The project's .claude folder could not be checked; its settings were not inspected."
    try:
        names = os.listdir(folder)
    except (FileNotFoundError, NotADirectoryError):
        return None, None
    except OSError:
        return None, unchecked
    if "settings.json" not in names:
        return None, None
    if home is not None:
        try:
            here, user = folder.stat(), home.stat()
        except (FileNotFoundError, NotADirectoryError):
            return folder / "settings.json", None
        except OSError:
            return None, unchecked
        if (here.st_dev, here.st_ino) == (user.st_dev, user.st_ino):
            return None, None
    return folder / "settings.json", None


def claude_run(home, label, status, project, required):
    paths, scopes, files, gaps = [], [], {}, []
    path, project_gap = project
    if status == "directory":
        paths, scopes, files = [home / "settings.json"], ["user"], {"settings-1": f"{label}/settings.json"}
    elif required:
        reason = {"missing": "was not found", "not a directory": "is not a directory",
                  "unreadable": "could not be checked"}[status]
        inspected = ("only the project's .claude/settings.json was inspected" if path
                     else "no Claude Code files were inspected")
        gaps.append(f"Claude Code home: {label} {reason}; {inspected}.")
    if path is not None:
        paths.append(path)
        scopes.append("project")
        files[f"settings-{len(paths)}"] = ".claude/settings.json"
    if project_gap:
        gaps.append(project_gap)
    return claude_report.inspect(paths, discovered=True, scopes=scopes, gaps=gaps), files


def discover_runs(args, agents):
    if agents == ["codex"]:
        return [codex_run(args)]
    home, label, status = claude_home(chosen=bool(agents))
    project = claude_project(home if status == "directory" else None)
    configured = bool(os.environ.get("CLAUDE_CONFIG_DIR"))
    if agents:
        include_claude, include_codex = "claude" in agents, "codex" in agents
    else:
        include_claude = status != "missing" or configured or project != (None, None)
        include_codex = True
        if (status == "directory" or project[0] is not None) and not os.environ.get("CODEX_HOME"):
            codex, _ = codex_home()
            include_codex = codex is not None and directory_status(codex) != "missing"
    runs = [codex_run(args)] if include_codex else []
    if include_claude:
        required = bool(agents) or configured or status != "missing"
        runs.append(claude_run(home, label, status, project, required))
    return runs


def main(argv=None):
    parser = Parser(prog=PROG, description="Read Codex and Claude Code settings and print a shareable report.")
    parser.add_argument("--config", action="append", metavar="FILE", help="Inspect this file independently; repeat for more files.")
    parser.add_argument("--workspace", action="append", metavar="DIR",
                        help="Compare Codex extra writable folders with this project's .codex directory.")
    parser.add_argument("--rules", action="append", metavar="FILE", help="Inspect one saved-rules file independently.")
    parser.add_argument("--agent", action="append", choices=AGENTS,
                        help="Check this coding agent; repeat for both. With no files selected, inspect the agent folders found.")
    parser.add_argument("--format", choices=("markdown", "json", "sarif"),
                        help="Choose the report format.")
    parser.add_argument("--save", action="store_true",
                        help=f"Also save the report as a formatted page, {NAME}, in {SAVE_FOLDER}, and end with a command "
                             "that opens it. Use --save with Markdown output only.")
    args, extra = parser.parse_known_args(argv)
    if args.save and len(extra) == 1 and not extra[0].startswith("-"):
        parser.exit(2, f"--save takes no path. It saves {NAME} in {SAVE_FOLDER}.\n")
    if extra:
        parser.error("Unexpected arguments.")
    if args.workspace and len(args.workspace) > 1:
        parser.exit(2, "Select only one directory with --workspace.\n")
    args.workspace = args.workspace[0] if args.workspace else None
    if args.workspace == "":
        parser.exit(2, "--workspace needs a directory. Use --help.\n")
    if args.rules and len(args.rules) != 1:
        parser.error("Only one rules file may be selected.")
    if args.save and args.format in ("json", "sarif"):
        parser.exit(2, f"--save can't be combined with --format {args.format}. Use --help.\n")
    agents = list(dict.fromkeys(args.agent or []))
    if args.config and len(agents) > 1:
        parser.exit(2, "--config needs one --agent: choose codex or claude.\n")
    if args.workspace is not None and agents == ["claude"]:
        parser.exit(2, "--workspace checks Codex settings only.\n")
    if args.rules and "claude" in agents:
        parser.exit(2, "--rules reads Codex files only.\n")
    if args.config or args.rules:
        if "claude" in agents:
            runs = [(claude_report.inspect([Path(p) for p in args.config]), {})]
        else:
            runs = [codex_run(args)]
    else:
        runs = discover_runs(args, agents)
    status = 2 if any(result["inspection_gaps"] for result, _ in runs) else 0
    path = save(render_all(runs, "html")) if args.save else None
    if args.save and path is None:
        sys.stderr.write(NOT_SAVED)
        sys.stderr.flush()
    terminal = args.format is None and sys.stdout.isatty()
    sys.stdout.write(render_all(runs, args.format or ("plain" if terminal else "markdown")))
    if path is not None:
        sys.stdout.write(open_command(path))
    if terminal and not args.save:
        sys.stdout.flush()
        sys.stderr.write("Use --save to save a formatted HTML report.\n")
    if status == 2:
        sys.stdout.flush()
        sys.stderr.write("Inspection incomplete (exit 2). See the report for what wasn't checked.\n")
    return status


def codex_run(args):
    paths = [Path(p) for p in args.config or []]
    rules = Path(args.rules[0]) if args.rules else None
    defaults = not args.config and not args.rules
    gaps, files = [], {}
    if args.rules:
        files["rules-1"] = None
    if defaults:
        home, gap = codex_home()
        if home is None:
            paths, rules, gaps = [], None, [gap]
        else:
            paths = [home / "config.toml"]
            rules = home / "rules" / "default.rules"
            base = "$CODEX_HOME" if os.environ.get("CODEX_HOME", "") else "~/.codex"
            files = {"config-1": f"{base}/config.toml", "rules-1": f"{base}/rules/default.rules"}
            if hooks_json(home):
                gaps.append("Codex home: hooks.json exists and was not inspected.")
            cache_gap = plugins_cache(home)
            if cache_gap:
                gaps.append(cache_gap)
            gaps.extend(gap for gap in (skills(home), environments_toml(home)) if gap)
            if system_config():
                gaps.append("System config folder: /etc/codex holds Codex configuration that was not inspected.")
    return inspect(paths, rules_path=rules, discovered=defaults, gaps=gaps, workspace=args.workspace), files

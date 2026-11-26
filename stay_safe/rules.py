from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    id: str
    explanation: str
    incidents: tuple[str, ...]


SANDBOX_OFF_EXPLANATION = (
    "A mistaken command could damage files outside your project. "
    "A command could also change Codex’s own settings, saved approvals, or instructions if your account can edit "
    "those files. A later Codex run could then follow different instructions or run a command it would otherwise "
    "ask you to approve."
)


RULES = (
    Rule("saved_approval",
         "A saved rule declares matching commands allowed outside the sandbox without prompting.",
         ("I26", "I30")),
    Rule("commands_without_prompts",
         "Permitted commands run without asking; injected or mistaken instructions could execute code. The configured sandbox still applies.",
         ("I2", "I3", "I24")),
    Rule("unrestricted_filesystem", SANDBOX_OFF_EXPLANATION, ("I1", "I3", "I32", "I20", "I33")),
    Rule("writable_project_settings",
         "This file explicitly grants sandboxed commands write access to the selected workspace's .codex directory. "
         "A command could change project settings that a later trusted Codex run uses.",
         ("I20", "I33")),
    Rule("configured_program",
         "The configuration can launch a program; a compromised command or configuration could execute unwanted code.",
         ("I13", "I14", "I19", "I33")),
    Rule("automatic_tools",
         "Tool approval mode is approve; untrusted tool content could lead to unwanted operations.",
         ("I15", "I20")),
    Rule("destructive_tools",
         "Destructive connector operations are enabled; a mistaken operation could change or delete connected data.",
         ("I7", "I8")),
    Rule("network_access",
         "The configuration permits network access; injected instructions could send private data to an outside service.",
         ("I15", "I21")),
    Rule("self_described_tools",
         "Documented in source, not yet observed: auto and writes use server-declared hints for tool approval.",
         ("I15", "I21")),
    Rule("environment_inheritance",
         "The selected configuration starts shell command environments from the parent process environment, "
         "apart from a few Codex launch variables. "
         "Inherited credentials could be misused, even with automatic name filtering enabled.",
         ("I23",)),
)


def evaluate(entries):
    return [
        {"rule": rule.id, "entry": entry["id"], "explanation": rule.explanation,
         "incidents": list(rule.incidents)}
        for entry in entries for rule in RULES
        if entry["facts"].get(rule.id) is True
    ]

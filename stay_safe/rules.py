"""Risk rules consume observations, not a harness's configuration syntax."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    id: str
    explanation: str
    incidents: tuple[str, ...]


RULES = (
    Rule("saved_approval",
         "A saved rule declares matching commands allowed outside the sandbox without prompting.",
         ("I26",)),
    Rule("commands_without_prompts",
         "Permitted commands run without asking; injected or mistaken instructions could execute code. The configured sandbox still applies.",
         ("I2", "I3", "I24")),
    Rule("unrestricted_filesystem",
         "The configuration removes the filesystem sandbox; a mistaken command could damage files outside the project.",
         ("I1", "I3")),
    Rule("configured_program",
         "The configuration can launch a program; a compromised command or configuration could execute unwanted code.",
         ("I13", "I14", "I19")),
    Rule("automatic_tools",
         "With strict automatic review off, configured approve mode makes tool calls allowed without asking. This is approval, not successful execution; untrusted tool content could lead to unwanted operations. Strict automatic review is runtime state requiring automated review unless a permission hook decides first. Tool hints, remembered approvals, effective permission profiles and reviewer state are not inspected.",
         ("I15", "I20")),
    Rule("destructive_tools",
         "Destructive connector operations are enabled; a mistaken operation could change or delete connected data.",
         ("I7", "I8")),
    Rule("network_access",
         "The configuration permits network access; injected instructions could send private data to an outside service.",
         ("I15", "I21")),
    Rule("self_described_tools",
         "Documented in source, not yet observed: approval depends on server-declared hints. With strict automatic review off, hints can make calls allowed without asking, even under never; other exemptions can also apply. This is approval, not successful execution. Strict automatic review is runtime state requiring automated review unless a permission hook decides first. Tool hints, remembered approvals, effective permission profiles and reviewer state are not inspected.",
         ("I15", "I21")),
    Rule("environment_inheritance",
         "The selected configuration starts shell command environments from the parent process environment, "
         "apart from a few Codex launch variables. "
         "Inherited credentials could be misused, even with automatic name filtering enabled.",
         ("I23",)),
)


def evaluate(entries):
    """Return stable rule results for supported explicit or defaulted conditions."""
    return [
        {"rule": rule.id, "entry": entry["id"], "explanation": rule.explanation,
         "incidents": list(rule.incidents)}
        for entry in entries for rule in RULES
        if entry["facts"].get(rule.id) is True
    ]

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts import codex_drift


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "codex-rs/core/config.schema.json"
SOURCE = "codex-rs/example.rs"


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.repo = self.folder / "codex"
        self.repo.mkdir()
        self.env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull,
                    "GIT_CONFIG_NOSYSTEM": "1", "GIT_NO_LAZY_FETCH": "1",
                    "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
                    "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.invalid"}
        self.git("init", "-q")
        self.lines = ["before", "cited one", "cited two", "after"]
        self.schema = {"type": "object", "properties": {"kept": {"type": "string"},
                       "removed": {"type": "boolean"}, "model_providers": {
                           "type": "object", "additionalProperties": {"$ref": "#/definitions/Provider"}}},
                       "definitions": {"Provider": {"type": "object", "properties": {}}}}
        self.commit("rust-v0.9.0")
        anchor = self.git("rev-parse", "HEAD").strip()
        self.meanings = self.folder / "meanings.md"
        self.meanings.write_text(
            f"[approval]: https://github.com/openai/codex/blob/{anchor}/{SOURCE}#L2-L3\n")
        self.lines[0:0] = ["inserted outside the citation", "second inserted line", "third inserted line"]
        self.commit("rust-v0.10.0")
        self.lines[4] = "cited one changed"
        self.schema["properties"]["kept"] = {"type": "integer"}
        del self.schema["properties"]["removed"]
        self.schema["properties"]["added"] = {"type": "boolean"}
        self.schema["definitions"]["Provider"]["properties"]["gateway_oauth"] = {
            "type": "object", "properties": {"credential_export": {"type": "string"}}}
        self.commit("rust-v0.10.1")
        self.git("tag", "rust-v0.10.5-rc1")
        self.lines[-1] = "unrelated change"
        self.commit("rust-v0.11.0")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], env=self.env,
                              text=True, capture_output=True, timeout=10, check=True).stdout

    def commit(self, tag):
        for path, contents in ((SOURCE, "\n".join(self.lines) + "\n"),
                               (SCHEMA, json.dumps(self.schema, indent=2) + "\n")):
            target = self.repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(contents)
        self.git("add", ".")
        self.git("commit", "-qm", tag)
        self.git("tag", tag)

    def scan(self, start="rust-v0.9.0", end=None):
        return codex_drift.scan(self.repo, self.meanings, start, end)

    def test_each_stable_release_reports_only_changed_citations_and_schema_differences(self):
        report = self.scan()
        releases = report["releases"]
        self.assertEqual([r["tag"] for r in releases],
                         ["rust-v0.10.0", "rust-v0.10.1", "rust-v0.11.0"])
        self.assertEqual(releases[0]["sources"], [])
        self.assertEqual(releases[2]["sources"], [])
        changed = releases[1]["sources"]
        self.assertEqual([(s["path"], s["labels"]) for s in changed], [(SOURCE, ["approval"])])
        self.assertIn("-cited one\n+cited one changed\n", changed[0]["diff"])
        self.assertEqual(releases[1]["schema"], [
            {"change": "added", "path": "added", "after": [{"type": "boolean"}]},
            {"change": "changed", "path": "kept", "before": [{"type": "string"}], "after": [{"type": "integer"}]},
            {"change": "added", "path": "model_providers.*.gateway_oauth", "after": [{"type": "object"}]},
            {"change": "added", "path": "model_providers.*.gateway_oauth.credential_export", "after": [{"type": "string"}]},
            {"change": "removed", "path": "removed", "before": [{"type": "boolean"}]},
        ])
        self.assertEqual([r["tag"] for r in self.scan("rust-v0.10.0", "rust-v0.10.1")["releases"]],
                         ["rust-v0.10.1"])
        self.assertEqual(self.scan("rust-v0.11.0")["releases"], [])

    def test_whole_file_and_deleted_citations_remain_visible(self):
        anchor = self.git("rev-parse", "rust-v0.9.0").strip()
        self.meanings.write_text(self.meanings.read_text() +
                                 f"[whole]: https://github.com/openai/codex/blob/{anchor}/{SOURCE}\n")
        releases = self.scan()["releases"]
        self.assertEqual(len(releases), 3)
        self.assertEqual(releases[-1]["sources"][0]["labels"], ["whole"])
        self.lines = ["inserted outside the citation", "before", "unrelated change"]
        self.commit("rust-v0.12.0")
        change = self.scan("rust-v0.11.0")["releases"][0]["sources"][0]
        self.assertEqual(change["labels"], ["approval", "whole"])
        self.assertIn("-cited two", change["diff"])
        introduced = self.repo / "codex-rs/introduced.rs"
        introduced.write_text("new cited function\n")
        self.commit("rust-v0.13.0")
        newer = self.git("rev-parse", "HEAD").strip()
        self.meanings.write_text(self.meanings.read_text() +
                                 f"[newer]: https://github.com/openai/codex/blob/{newer}/codex-rs/introduced.rs#L1\n")
        addition = self.scan()["releases"][-1]["sources"][0]
        self.assertEqual(addition["labels"], ["newer"])
        self.assertIn("+new cited function", addition["diff"])
        introduced.unlink()
        self.commit("rust-v0.14.0")
        deletion = self.scan("rust-v0.13.0")["releases"][0]["sources"][0]
        self.assertEqual(deletion["labels"], ["newer"])
        self.assertIn("-new cited function", deletion["diff"])

    def test_schema_branch_and_array_structure_changes_are_reported(self):
        self.schema = {"type": "object", "properties": {
            "choices": {"allOf": [{"type": "integer"}, {"minimum": 1}]},
            "sequence": {"type": "array", "items": {"type": "integer"}},
            "single": {"oneOf": [{"type": "integer"}]}}}
        self.commit("rust-v0.12.0")
        fields = self.schema["properties"]
        fields["choices"]["anyOf"] = fields["choices"].pop("allOf")
        fields["sequence"]["items"] = [fields["sequence"]["items"]]
        fields["single"]["oneOf"].append({"type": "integer"})
        self.commit("rust-v0.13.0")
        report = self.scan("rust-v0.12.0", "rust-v0.13.0")
        self.assertEqual([(item["change"], item["path"]) for item in report["releases"][0]["schema"]],
                         [("changed", "choices"), ("changed", "sequence"), ("changed", "single")])
        for path in ("choices", "sequence", "single"):
            self.assertIn(f"Changed: `{path}`", codex_drift.render(report))

    def test_missing_refs_files_and_invalid_inputs_fail_instead_of_returning_clean_results(self):
        for start, end in (("rust-v0.8.0", None), ("rust-v0.11.0", "rust-v0.9.0"),
                           ("rust-v0.9.0", "rust-v0.12.0"), ("main", None)):
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                self.scan(start, end)
        original = self.meanings.read_text()
        for contents in ("no source links", original.replace("#L2-L3", "#L99-L100"),
                         original.replace(SOURCE, "missing.rs"),
                         original.replace("#L2-L3", "#L3-L2")):
            self.meanings.write_text(contents)
            with self.subTest(contents=contents), self.assertRaises(ValueError):
                self.scan()
        self.meanings.write_text(original)
        self.schema = []
        self.commit("rust-v0.12.0")
        with self.assertRaisesRegex(ValueError, "schema"):
            self.scan()
        self.schema = {"type": "object", "properties": {}}
        self.commit("rust-v0.13.0")
        (self.repo / SCHEMA).unlink()
        self.git("add", "-u")
        self.git("commit", "-qm", "missing schema")
        self.git("tag", "rust-v0.14.0")
        with self.assertRaisesRegex(ValueError, "missing source file: rust-v0.14.0:codex-rs/core/config.schema.json"):
            self.scan("rust-v0.13.0")
        for index, (kind, branches) in enumerate((kind, branches)
                for kind in ("allOf", "anyOf", "oneOf") for branches in ({}, [])):
            self.schema = {"type": "object", "properties": {"setting": {kind: branches}}}
            tag = f"rust-v0.15.{index}"
            self.commit(tag)
            with self.subTest(kind=kind, branches=branches), self.assertRaisesRegex(ValueError, "schema"):
                self.scan(tag, tag)

    def test_cli_reports_complete_scan_or_explicit_failure_without_advancing_state(self):
        state = self.folder / "state.json"
        state.write_text(json.dumps({"last_scanned_tag": "rust-v0.9.0"}))
        initial = state.read_bytes()
        command = [sys.executable, str(ROOT / "scripts/codex_drift.py"),
                   "--codex-repo", str(self.repo), "--meanings", str(self.meanings),
                   "--state", str(state)]
        success = subprocess.run(command, text=True, capture_output=True, timeout=20, env=self.env)
        self.assertEqual((success.returncode, success.stderr), (0, ""))
        self.assertIn("Scanned 3 stable releases", success.stdout)
        self.assertIn("rust-v0.10.1", success.stdout)
        self.assertIn("cited one changed", success.stdout)
        self.assertEqual(state.read_bytes(), initial)
        state.write_text("{")
        failure = subprocess.run(command, text=True, capture_output=True, timeout=20, env=self.env)
        self.assertEqual(failure.returncode, 2)
        self.assertEqual(failure.stdout, "")
        self.assertIn("state", failure.stderr)
        self.assertEqual(state.read_text(), "{")

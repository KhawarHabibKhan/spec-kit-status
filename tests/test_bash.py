import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/bash/status.sh"

class StatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        subprocess.run(["git", "-c", "init.defaultBranch=main", "init", "-q", str(self.root)], check=True)
        (self.root / ".specify").mkdir()
        self.feature = self.root / "specs/001-example"
        self.feature.mkdir(parents=True)
        skill = self.root / ".agents/skills/speckit-specify/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("# Specify")
        self.env = {k:v for k,v in os.environ.items() if not k.startswith("SPECIFY_")}

    def run_status(self):
        return subprocess.run(["bash", str(SCRIPT)], cwd=self.root, env=self.env, capture_output=True, text=True)

    def test_pointer_on_main_and_fenced_task_examples(self):
        pointer = self.root / ".specify/feature.json"
        pointer.write_text(json.dumps({"feature_directory": "specs/001-example"}))
        before = pointer.read_bytes()
        (self.feature / "tasks.md").write_text("```md\n- [x] T001 example\n```\n~~~\n- [x] example\n~~~\n- [ ] T001 real\n- [X] T002 checked")
        result = self.run_status()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["feature_name"], "001-example")
        self.assertEqual(data["tasks"], {"completed": 1, "total": 2})
        self.assertTrue(next(a for a in data["agents"] if a["key"] == "codex")["has_commands"])
        self.assertFalse(any(a["key"] == "amp" for a in data["agents"]))
        self.assertEqual(pointer.read_bytes(), before)

    def test_no_latest_guess_and_invalid_explicit_directory_fails(self):
        result = self.run_status()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["phase"], "no_feature")
        self.env["SPECIFY_FEATURE_DIRECTORY"] = "specs/999-missing"
        self.assertNotEqual(self.run_status().returncode, 0)

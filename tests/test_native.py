"""Regression contract for Spec Kit 1.2.2 native project state."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODE = 'status'

class NativeState(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name) / 'project space'
        for name in ('.specify/scripts/bash', '.specify/templates', '.specify/memory', '.specify/extensions', '.agents/skills/speckit-specify', 'specs/001-alpha', 'specs/002-beta'):
            (self.project / name).mkdir(parents=True, exist_ok=True)
        for name in ('common', 'check-prerequisites', 'create-new-feature', 'setup-plan'):
            path = self.project / ('.specify/scripts/bash/' + name + '.sh')
            path.write_text('#!/bin/sh\n')
            path.chmod(0o755)
        for name in ('.specify/memory/constitution.md', '.agents/skills/speckit-specify/SKILL.md', 'specs/001-alpha/spec.md', 'specs/002-beta/spec.md'):
            (self.project / name).write_text('# fixture\n')
        self.write('.specify/extensions/.registry', {'extensions': {}})
        self.write('.specify/integration.json', {'integration': 'skills', 'agent': 'codex'})
        self.write('.specify/feature.json', {'feature_directory': 'specs/001-alpha'})

    def write(self, name, value):
        (self.project / name).write_text(json.dumps(value))

    def run_script(self, env=None, cwd=None):
        clean = {k: v for k, v in os.environ.items() if not k.startswith('SPECIFY_')}
        clean.update(env or {})
        command = ['bash', str(ROOT / ('scripts/bash/' + MODE + '.sh')), '--json']
        result = subprocess.run(command, cwd=cwd or self.project, env=clean, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.stderr, '', result.stderr)
        return result, json.loads(result.stdout)

    def active(self, value):
        return value['active_feature'] if MODE == 'doctor' else value['feature_name']

    def test_native_pointer_and_directory_override(self):
        result, value = self.run_script()
        self.assertEqual(result.returncode, 0, value)
        self.assertEqual(self.active(value), '001-alpha')
        for selector in ('specs/002-beta', str(self.project / 'specs/002-beta')):
            result, value = self.run_script({'SPECIFY_FEATURE_DIRECTORY': selector, 'SPECIFY_FEATURE': '001-alpha'})
            self.assertEqual(result.returncode, 0, value)
            self.assertEqual(self.active(value), '002-beta')

    def test_init_override_and_nested_root(self):
        for cwd, env in ((self.project / 'specs/001-alpha', {}), (Path(self.tmp.name), {'SPECIFY_INIT_DIR': str(self.project)})):
            result, value = self.run_script(env, cwd)
            self.assertEqual(result.returncode, 0, value)
            self.assertEqual(self.active(value), '001-alpha')
        result, value = self.run_script({'SPECIFY_INIT_DIR': str(self.project / 'missing')})
        self.assertNotEqual(result.returncode, 0)

    def test_invalid_state_returns_json_failure(self):
        for name, bad in (('.specify/extensions/.registry', []), ('.specify/integration.json', []), ('.specify/feature.json', []), ('.specify/feature.json', {'feature_directory': []})):
            with self.subTest(name=name, bad=bad):
                path = self.project / name
                before = path.read_text()
                self.write(name, bad)
                try:
                    result, value = self.run_script()
                    self.assertNotEqual(result.returncode, 0, value)
                finally:
                    path.write_text(before)

    def test_no_writes_and_shared_contracts_are_not_features(self):
        (self.project / 'specs/contracts').mkdir()
        (self.project / 'specs/contracts/api.md').write_text('# shared\n')
        def snapshot():
            return {str(p.relative_to(self.project)): (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest()) for p in self.project.rglob('*') if p.is_file()}
        before = snapshot()
        result, value = self.run_script()
        self.assertEqual(result.returncode, 0, value)
        self.assertEqual(snapshot(), before)
        if MODE == 'status': self.assertEqual(value['feature_count'], 2)

    def test_unsafe_pointer_and_symlink_rejected(self):
        for selector in ('../outside', '/tmp', 'specs/999-missing'):
            result, value = self.run_script({'SPECIFY_FEATURE_DIRECTORY': selector})
            self.assertNotEqual(result.returncode, 0, value)
        (self.project / 'specs/003-link').symlink_to(self.project / 'specs/001-alpha', target_is_directory=True)
        result, value = self.run_script({'SPECIFY_FEATURE_DIRECTORY': 'specs/003-link'})
        self.assertNotEqual(result.returncode, 0, value)

    def test_environment_override_does_not_read_stale_pointer(self):
        (self.project / '.specify/feature.json').write_text('not JSON')
        result, value = self.run_script({'SPECIFY_FEATURE_DIRECTORY': 'specs/002-beta'})
        self.assertEqual(result.returncode, 0, value)
        self.assertEqual(self.active(value), '002-beta')

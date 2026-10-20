"""Portable fixture contract; run: python3 -m unittest discover -s tests -v.

PowerShell executes the same assertions when pwsh is available; otherwise its
runtime coverage is explicitly skipped. No network or project mutations.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class StatusContract:
    powershell = False

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name) / 'fixture project'
        (self.project / '.specify/scripts/bash').mkdir(parents=True)
        (self.project / '.specify/scripts/powershell').mkdir(parents=True)
        self.feature('001-alpha', '- [X] T001 done\n- [ ] T002 pending\n')
        self.feature('002-beta', '- [x] T001 done\n')
        subprocess.run(['git', 'init', '-q', '-b', 'main', str(self.project)], check=True)

    def feature(self, name, tasks=None):
        directory = self.project / 'specs' / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'spec.md').write_text('# Specification\n')
        if tasks is not None:
            (directory / 'tasks.md').write_text(tasks)
        return directory

    def run_status(self, selector=None, env_feature=None, success=True, cwd=None):
        env = os.environ.copy()
        for key in ('SPECIFY_FEATURE', 'SPECIFY_FEATURE_DIRECTORY', 'SPECIFY_INIT_DIR', 'GIT_DIR', 'GIT_WORK_TREE'):
            env.pop(key, None)
        if env_feature is not None:
            env['SPECIFY_FEATURE'] = env_feature
        if self.powershell:
            command = ['pwsh', '-NoProfile', '-File', str(ROOT / 'scripts/powershell/status.ps1')]
            if selector is not None:
                command += ['-Feature', selector]
        else:
            command = ['bash', str(ROOT / 'scripts/bash/status.sh')]
            if selector is not None:
                command += ['--feature', selector]
        result = subprocess.run(command, cwd=cwd or self.project, env=env, text=True, capture_output=True)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        payload = json.loads(result.stdout)  # Entire stdout must be one JSON document.
        self.assertEqual(result.stderr, '')
        return payload

    def branch(self, name):
        subprocess.run(['git', '-C', str(self.project), 'symbolic-ref', 'HEAD', 'refs/heads/' + name], check=True)

    def test_main_all_feature_summary_without_latest(self):
        data = self.run_status()
        self.assertEqual(data['feature_name'], '')
        self.assertEqual(data['phase'], 'no_feature')
        self.assertEqual(data['feature_count'], 2)
        self.assertEqual(data['summary']['tasks'], {'completed': 2, 'total': 3})
        self.assertEqual(data['live_status'], 'NOT_QUERIED')

    def test_selector_precedence_and_unique_branch_prefix(self):
        self.branch('001-renamed-branch')
        self.assertEqual(self.run_status()['feature_name'], '001-alpha')
        self.assertEqual(self.run_status(env_feature='002')['feature_name'], '002-beta')
        self.assertEqual(self.run_status('001', env_feature='002')['feature_name'], '001-alpha')

    def test_ambiguity_and_exact_directory(self):
        self.feature('001-other')
        self.assertIn('Ambiguous', self.run_status('001', success=False)['error'])
        self.assertEqual(self.run_status('001-alpha')['feature_name'], '001-alpha')
        self.branch('001-renamed')
        self.assertIn('Ambiguous', self.run_status(success=False)['error'])

    def test_missing_and_invalid_selectors_fail(self):
        for value in ('999', '../001-alpha', 'alpha'):
            with self.subTest(value=value):
                self.assertIn('error', self.run_status(value, success=False))

    def test_detached_and_non_git_never_infer_latest(self):
        (self.project / '.git/HEAD').write_text('0' * 40 + '\n')
        self.assertEqual(self.run_status()['feature_name'], '')
        shutil.rmtree(self.project / '.git')
        self.assertEqual(self.run_status()['feature_name'], '')
        self.assertEqual(self.run_status('001')['feature_name'], '001-alpha')

    def test_current_layout_codex_skills_not_amp(self):
        skills = self.project / '.agents/skills/speckit-status'
        skills.mkdir(parents=True)
        (skills / 'SKILL.md').write_text('# Status\n')
        data = self.run_status()
        self.assertEqual(data['script_type'], 'sh + ps')
        agents = {agent['key']: agent for agent in data['agents']}
        self.assertTrue(agents['codex']['has_commands'])
        self.assertEqual(agents['codex']['folder'], '.agents/skills/')
        self.assertNotIn('amp', agents)
        (self.project / '.agents/commands').mkdir()
        self.assertIn('amp', {a['key'] for a in self.run_status()['agents']})

    def test_legacy_codex_prompts_supported(self):
        prompts = self.project / '.codex/prompts'
        prompts.mkdir(parents=True)
        (prompts / 'speckit.status.md').write_text('# Status\n')
        agents = {a['key']: a for a in self.run_status()['agents']}
        self.assertTrue(agents['codex']['has_commands'])

    def test_fenced_examples_and_checkbox_boundaries(self):
        tasks = '''- [X] T001 real
```md
- [ ] fake
```
~~~~ example
- [x] fake
~~~
- [ ] still inside longer fence
~~~~
````md
- [ ] fake
```
- [x] still inside longer fence
````
- [ ] T002 real
- [x]not-a-checkbox
'''
        directory = self.feature('003-fences', tasks)
        (directory / 'checklists').mkdir()
        (directory / 'checklists/review.md').write_text('- [X] real\n```md\n- [ ] example\n```\n')
        data = self.run_status('003')
        self.assertEqual(data['tasks'], {'completed': 1, 'total': 2})
        self.assertTrue(data['artifacts']['checklists_all_pass'])

    def test_checked_tasks_do_not_mean_acceptance(self):
        data = self.run_status('002')
        self.assertEqual(data['phase'], 'tasks_checked')
        self.assertEqual(data['acceptance'], 'NOT_ASSESSED')
        self.assertEqual(data['summary']['acceptance'], 'NOT_ASSESSED')

    def test_empty_tasks_and_missing_tasks_are_distinct(self):
        self.feature('003-empty', '# Roadmap only\n')
        self.assertEqual(self.run_status('003')['phase'], 'no_tasks')
        directory = self.feature('004-plan')
        (directory / 'plan.md').write_text('# Plan\n')
        self.assertEqual(self.run_status('004')['phase'], 'tasks')

    def test_nested_working_directory(self):
        self.assertEqual(self.run_status('001', cwd=self.project / 'specs/001-alpha')['feature_name'], '001-alpha')

    def test_project_name_json_escaping(self):
        renamed = self.project.with_name('fixture "project"\n\x01')
        self.project.rename(renamed)
        self.project = renamed
        self.assertEqual(self.run_status()['project_name'], renamed.name)

    def test_registry_count_and_invalid_json(self):
        registry = self.project / '.specify/extensions/.registry'
        registry.parent.mkdir()
        registry.write_text('{"extensions": {}}')
        self.assertEqual(self.run_status()['installed_extensions'], 0)
        registry.write_text('{"extensions": {"status": {}}}')
        self.assertEqual(self.run_status()['installed_extensions'], 1)
        registry.write_text('{not json')
        self.assertIn('error', self.run_status(success=False))

    def test_missing_project_is_json_error(self):
        shutil.rmtree(self.project / '.specify')
        self.assertIn('error', self.run_status(success=False))


class BashStatus(StatusContract, unittest.TestCase):
    pass


@unittest.skipUnless(shutil.which('pwsh'), 'PowerShell runtime unavailable; parity unverified')
class PowerShellStatus(StatusContract, unittest.TestCase):
    powershell = True

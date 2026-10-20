#!/usr/bin/env python3
"""Read-only task bookkeeping; engineering acceptance is never inferred."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from project_state import project_root, native_state, resolve_feature, read_object


def counts(path):
    checked = total = 0
    fence = None
    for line in path.read_text(encoding='utf-8').splitlines():
        match = re.match(r'^\s*(`{3,}|~{3,})(.*)$', line)
        if match:
            mark, tail = match.groups()
            if fence is None:
                fence = mark
            elif mark[0] == fence[0] and len(mark) >= len(fence) and not tail.strip():
                fence = None
            continue
        row = re.match(r'^\s*[-*]\s+\[([ xX])\](?:\s|$)', line)
        if fence is None and row:
            total += 1
            checked += row[1].lower() == 'x'
    return {'completed': checked, 'total': total}


def regular(path):
    return path.is_file() and not path.is_symlink()


def feature_info(directory):
    artifacts = {name.replace('-', '_'): bool(directory and regular(directory / (name + '.md')))
                 for name in ('spec', 'plan', 'tasks', 'research', 'data-model', 'quickstart')}
    contracts = list((directory / 'contracts').glob('*')) if directory else []
    checklists = list((directory / 'checklists').glob('*.md')) if directory else []
    contracts = [p for p in contracts if regular(p)]
    checklists = [p for p in checklists if regular(p)]
    artifacts.update(contracts=bool(contracts), contract_count=len(contracts), checklists=bool(checklists),
                     checklist_count=len(checklists), checklists_all_pass=all(counts(p)['completed'] == counts(p)['total'] for p in checklists))
    tasks = counts(directory / 'tasks.md') if artifacts['tasks'] else {'completed': 0, 'total': 0}
    phase, hint = 'no_feature', 'Select a native feature pointer or --feature; no latest feature is inferred'
    if directory:
        if artifacts['tasks']:
            if not tasks['total']:
                phase, hint = 'no_tasks', 'No actionable tasks; roadmap pending'
            elif tasks['completed'] == tasks['total']:
                phase, hint = 'tasks_checked', 'Task bookkeeping checked; engineering acceptance is not assessed'
            else:
                phase, hint = 'implement', 'Tasks available; verify authorization before implementation'
        elif artifacts['plan']:
            phase, hint = 'tasks', 'Plan exists; tasks are absent'
        elif artifacts['spec']:
            phase, hint = 'plan', 'Specification exists; plan is absent'
        else:
            phase, hint = 'not_started', 'Specification is absent'
    return dict(feature_name=directory.name if directory else '', artifacts=artifacts, tasks=tasks,
                task_state='TASKS_AVAILABLE' if tasks['total'] else 'ROADMAP_PENDING',
                phase=phase, phase_hint=hint, acceptance='NOT_ASSESSED')


def status(root, requested):
    state, native = native_state(root)
    branch = ''
    has_git = False
    if shutil.which('git'):
        env = dict(os.environ, GIT_OPTIONAL_LOCKS='0')
        result = subprocess.run(['git', '-C', str(root), 'rev-parse', '--is-inside-work-tree'], env=env, capture_output=True, text=True, timeout=5)
        has_git = result.returncode == 0 and result.stdout.strip() == 'true'
        if has_git:
            result = subprocess.run(['git', '-C', str(root), 'symbolic-ref', '--quiet', '--short', 'HEAD'], env=env, capture_output=True, text=True, timeout=5)
            branch = result.stdout.strip() if result.returncode == 0 else ''
    # Native context wins over retained legacy env/numbered-branch selection.
    legacy = requested or (None if native else os.environ.get('SPECIFY_FEATURE') or (branch if re.match(r'^[0-9]{3}-', branch) else None))
    active = resolve_feature(root, legacy, legacy=True) if legacy else resolve_feature(root, native)
    directories = sorted(p for p in (root / 'specs').glob('[0-9][0-9][0-9]-*') if p.is_dir())
    features = [feature_info(resolve_feature(root, str(p))) for p in directories]
    agents = []
    for config in json.loads(Path(__file__).with_name('agent_paths.json').read_text()):
        folder = root / config['folder']
        commands = folder / config['commands']
        skills = config['key'] == 'codex' and any((root / '.agents/skills').glob('speckit-*/SKILL.md'))
        if config['key'] == 'amp' and not commands.is_dir():
            continue
        if folder.is_dir() or skills:
            agents.append(dict(key=config['key'], name=config['name'], folder='.agents/skills/' if skills else config['folder'] + '/',
                               has_commands=skills or (commands.is_dir() and any(commands.iterdir()))))
    registry = read_object(root / '.specify/extensions/.registry')
    installed = None
    if registry is not None:
        entries = registry.get('extensions')
        if not isinstance(entries, dict) or any(not isinstance(v, dict) for v in entries.values()):
            raise ValueError('Invalid extension registry')
        installed = len(entries)
    families = [family for name, family in (('bash', 'sh'), ('powershell', 'ps')) if (root / '.specify/scripts' / name).is_dir()]
    summary_tasks = {key: sum(f['tasks'][key] for f in features) for key in ('completed', 'total')}
    return dict(project_name=root.name, has_git=has_git, current_branch=branch, script_type=' + '.join(families) or 'none',
                integration=state.get('integration') if state else None, agents=agents, installed_extensions=installed,
                feature_count=len(features), features=features, summary=dict(tasks=summary_tasks,
                task_state='TASKS_AVAILABLE' if summary_tasks['total'] else 'ROADMAP_PENDING', acceptance='NOT_ASSESSED'),
                live_status='NOT_QUERIED', **feature_info(active))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--feature', help='explicit legacy NNN or NNN-name selector')
    parser.add_argument('--json', action='store_true', help='accepted for compatibility; output is always JSON')
    args = parser.parse_args()
    try:
        result = status(project_root(), args.feature)
    except (OSError, UnicodeError, ValueError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({'error': str(exc)}))
        return 1
    print(json.dumps(result, ensure_ascii=True))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

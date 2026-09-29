#!/usr/bin/env python3
"""Exercise v6 with real Git trees, violations, review drift and cleanup targets."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/verify-protocol.py'

class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / 'repo'
        self.repo.mkdir()
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Protocol test')
        self.git('config', 'user.email', 'test@example.invalid')
        (self.repo / 'src').mkdir()
        (self.repo / 'src/a.txt').write_text('before')
        self.git('add', '.')
        self.git('commit', '-m', 'baseline')
        self.path = Path(self.temp.name) / 'example.json'
        self.state = dict(protocol_version=6, task_id='example', skill_root=str(ROOT),
            candidate=dict(branch='main', worktree=str(self.repo), baseline=self.git('rev-parse', 'HEAD').strip()),
            goal='修正当前模块', authorization='用户明确要求修正并验证', write_scope=['src'],
            risk='reversible', status='active', checks=[dict(command='observe behavior', status='pending', evidence=None)])

    def git(self, *args):
        return subprocess.check_output(('git', '-C', str(self.repo), *args), stderr=subprocess.PIPE).decode()

    def run_gate(self, error=None, fingerprint=False):
        self.path.write_text(json.dumps(self.state))
        args = [sys.executable, str(SCRIPT), '--state', str(self.path), '--repo', str(self.repo), '--skill-root', str(ROOT), '--state-dir', str(self.path.parent)]
        if fingerprint: args.append('--fingerprint')
        result = subprocess.run(args, text=True, capture_output=True, env={**os.environ, 'PYTHONDONTWRITEBYTECODE':'1'})
        if error:
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn(error, result.stderr)
        else:
            self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def complete(self):
        self.state['status'] = 'completed'
        self.state['checks'][0].update(status='passed', evidence='实际目标检查通过')

    def review(self):
        self.state['review'] = dict(reviewer='independent', evidence='只读检查原始结果', fingerprint=self.run_gate(fingerprint=True))

    def test_small_record_and_completion(self):
        (self.repo / 'src/a.txt').write_text('after')
        self.run_gate()
        self.state['status'] = 'completed'
        self.run_gate('DELIVERY_INCOMPLETE')
        self.complete()
        self.run_gate()
        self.state['blockers'] = ['目标检查仍有问题']
        self.run_gate('DELIVERY_INCOMPLETE')

    def test_scope_and_branch_boundaries(self):
        (self.repo / 'outside').write_text('unrelated')
        self.run_gate('DIFF_OUTSIDE_AUTHORIZED_TARGETS')
        (self.repo / 'outside').unlink()
        self.state['candidate']['branch'] = 'other'
        self.run_gate('BRANCH_MISMATCH')
        self.state['candidate']['branch'] = 'main'
        for invalid in ['.', '../escape', '/absolute', 'src/*', 'src/../outside']:
            self.state['write_scope'] = [invalid]
            self.run_gate('INVALID' if invalid not in ['.', 'src/*'] else 'ACTION_TARGET_NOT_EXACT')

    def test_staged_file_cannot_hide_outside_scope(self):
        target = self.repo / 'outside'
        target.write_text('staged outside grant')
        self.git('add', 'outside')
        target.unlink()
        self.run_gate('DIFF_OUTSIDE_AUTHORIZED_TARGETS')

    def test_parallel_writers(self):
        self.state['writers'] = [dict(id='main', paths=['src/a']), dict(id='worker', paths=['src/b'])]
        self.run_gate()
        self.state['writers'][1]['paths'] = ['src/a/child']
        self.run_gate('OVERLAPPING_WRITERS')
        self.state['writers'][1]['paths'] = ['outside']
        self.run_gate('WRITER_OUTSIDE_SCOPE')

    def test_retry_after_three_failures(self):
        self.state['failures'] = [dict(hypothesis=f'cause-{i}', evidence=f'原始信号否定 {i}') for i in range(4)]
        self.run_gate('NEXT_ATTEMPT')
        self.state['next_attempt'] = dict(hypothesis='new cause', new_evidence='新日志定位另一条路径')
        self.run_gate()
        self.state['next_attempt']['hypothesis'] = 'cause-0'
        self.run_gate('REPEATED_FAILED_HYPOTHESIS')

    def test_security_review_and_drift(self):
        self.state.update(risk='high-risk', impact='权限变化', rollback='恢复代码')
        self.run_gate()  # Implementation can precede review.
        self.complete()
        self.run_gate('INDEPENDENT_REVIEW_INCOMPLETE')
        self.review()
        self.run_gate()
        (self.repo / 'src/a.txt').write_text('new behavior')
        self.run_gate('REVIEW_STALE')
        self.review()
        self.run_gate()
        self.state['review']['reviewer'] = 'main'
        self.run_gate('INDEPENDENT_REVIEWER_REQUIRED')

    def test_index_change_invalidates_review(self):
        self.state.update(risk='high-risk', impact='权限变化', rollback='恢复代码')
        target = self.repo / 'src/a.txt'
        target.write_text('reviewed')
        self.complete()
        self.review()
        target.write_text('unreviewed staged content')
        self.git('add', 'src/a.txt')
        target.write_text('reviewed')
        self.run_gate('REVIEW_STALE')

    def test_action_order_does_not_change_requirements(self):
        self.state["checks"][0].update(status="passed", evidence="验证完成")
        commit = dict(action='commit', target='main', authorization='提交当前候选')
        deploy = dict(action='deploy', target='prod/service', authorization='部署当前服务', impact='线上变化', rollback='恢复前版')
        for actions in [[commit, deploy], [deploy, commit]]:
            self.state['actions'] = actions
            self.review()
            self.run_gate()

    def test_external_action_cannot_downgrade_risk(self):
        self.state['actions'] = [dict(action='deploy', target='prod/service', authorization='明确部署授权')]
        self.run_gate('IMPACT')
        self.state['actions'][0].update(impact='线上行为变化', rollback='恢复前一版本')
        self.run_gate('INDEPENDENT_REVIEW_INCOMPLETE')
        self.review()
        self.run_gate('DELIVERY_INCOMPLETE')
        self.state['checks'][0].update(status='passed', evidence='验证完成')
        self.run_gate()
        self.state['actions'][0]['target'] = 'prod/other-service'
        self.run_gate('REVIEW_STALE')

    def test_merge_uses_candidate_risk_and_requires_checks(self):
        self.state['actions'] = [dict(action='merge', target='feature->main', authorization='合并当前候选')]
        self.run_gate('MERGE_RISK_EVIDENCE')
        self.state['actions'][0]['risk_evidence'] = dict(diff='本次 diff 未触及高风险内容')
        self.run_gate('MERGE_RISK_EVIDENCE_FIELDS_INVALID')
        self.state['actions'][0]['risk_evidence']['target_branch'] = '已核对 main 的保护规则'
        self.run_gate('DELIVERY_INCOMPLETE')
        self.state['checks'][0].update(status='passed', evidence='合并前检查通过')
        self.run_gate()
        self.state['actions'][0]['risk_evidence']['target_branch'] = ''
        self.run_gate('MERGE_TARGET_BRANCH_EVIDENCE')
        del self.state['actions'][0]['risk_evidence']
        self.state.update(risk='high-risk', impact='主分支权限变化', rollback='建立反向提交')
        self.run_gate('IMPACT')
        self.state['actions'][0].update(impact='主分支权限变化', rollback='建立反向提交')
        self.run_gate('INDEPENDENT_REVIEW_INCOMPLETE')
        self.review()
        self.run_gate()

    def test_blocked_task(self):
        self.state['blockers'] = ['范围待决定']
        self.run_gate('OPEN_BLOCKER_PREVENTS_WRITE')
        self.state['status'] = 'blocked'
        self.run_gate()
        self.state['actions'] = [dict(action='push', target='origin:main', authorization='push')]
        self.run_gate('BLOCKED_CANDIDATE_CANNOT_EXECUTE')

    def test_merged_branch_cleanup(self):
        self.git('branch', 'finished')
        action = dict(action='branch-delete', target='finished', authorization='删除 finished', safe_cleanup=dict(merged_into='main', unused_evidence='无任务占用'))
        self.state['actions'] = [action]
        self.run_gate()
        action['target'] = 'main'
        self.run_gate('CLEANUP_BRANCH_IN_USE')
        action['action'] = 'deploy'
        self.run_gate('SAFE_CLEANUP_ACTION_INVALID')

    def test_worktree_cleanup_protects_files(self):
        target = Path(self.temp.name) / 'finished'
        self.git('worktree', 'add', '-b', 'finished', str(target))
        self.state['actions'] = [dict(action='worktree-delete', target=str(target), authorization='删除该目录', safe_cleanup=dict(merged_into='main', unused_evidence='已核对无任务与进程'))]
        self.run_gate()
        (target / 'notes').write_text('keep me')
        self.run_gate('CLEANUP_WORKTREE_DIRTY')
        (target / 'notes').unlink()
        subprocess.check_call(('git', '-C', str(target), 'commit', '--allow-empty', '-m', 'unique'), stdout=subprocess.DEVNULL)
        self.run_gate('CLEANUP_UNMERGED')

    def test_invalid_action_authority_and_syntax(self):
        self.state['actions'] = [dict(action='push', target='origin:*', authorization='明确请求')]
        self.run_gate('ACTION_TARGET_NOT_EXACT')
        self.state['actions'][0]['target'] = 'origin:main'
        self.state['actions'][0]['authorization'] = ''
        self.run_gate('ACTION_AUTHORIZATION')
        self.state['actions'][0]['authorization'] = '明确请求'
        self.state['actions'][0]['action'] = 'workspace-write'
        self.run_gate('ACTION_KIND_INVALID')
        self.state['actions'][0].update(action='push', target='origin:main', risk_evidence=dict(diff='不适用', target_branch='main'))
        self.run_gate('MERGE_RISK_EVIDENCE_NOT_APPLICABLE')

if __name__ == '__main__':
    unittest.main()

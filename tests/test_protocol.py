#!/usr/bin/env python3
"""Executable positive and negative scenarios for the local protocol."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "scripts" / "verify-protocol.py"
FIXTURES = ROOT / "tests" / "fixtures" / "protocol"
NO_BYTECODE = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}


def run(*args: str, expected: int = 0) -> str:
    result = subprocess.run(args, text=True, capture_output=True, env=NO_BYTECODE)
    if result.returncode != expected:
        raise AssertionError(f"expected {expected}, got {result.returncode}: {result.stderr}")
    return result.stdout + result.stderr


def verify(state_path: Path, *checks: str, expected: int = 0) -> str:
    return run(sys.executable, str(VERIFY), "--state", str(state_path), *checks, expected=expected)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def state_for(repo: Path, task_id: str = "protocol-test") -> dict:
    state = json.loads((FIXTURES / "valid.json").read_text(encoding="utf-8"))
    state["task_id"] = task_id
    state["skill_root"] = str(ROOT)
    state["git_baseline"] = run("git", "-C", str(repo), "rev-parse", "HEAD").strip()
    state["ignored_untracked_policy"] = "excluded"
    state["primary_branch"] = "main"
    state["candidate"].update(branch="main", worktree=str(repo), isolation="主分支直接写")
    state["candidate"]["blocks_new_business_goal"] = True
    state["authorization_card"]["candidate_and_worktree"] = f"main；{repo}"
    state["write_scope"]["initial_allowed_paths"] = ["allowed"]
    state["delivery_evidence"]["feedback_scope"] = ["allowed/tests"]
    return state


def write_state(repo: Path, state: dict, task_id: str = "protocol-test") -> Path:
    path = repo / ".dev-team" / "state" / f"{task_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    return path


def checks(repo: Path) -> tuple[str, ...]:
    return ("--repo", str(repo), "--state-dir", str(repo / ".dev-team" / "state"), "--skill-root", str(ROOT))


def failure(index: int) -> dict:
    return {"id": f"failure-{index}", "outcome": "failed", "hypothesis": f"hypothesis {index}", "stable_signal": "python3 reproduce.py", "observed_at": f"2026-09-0{index}T00:00:00Z"}


def complete_delivery(state: dict) -> None:
    state["delivery_evidence"]["target_check"] = {"status": "passed", "evidence": "目标命令退出码为 0"}
    state["delivery_evidence"]["adjacent_regression"] = {"status": "passed", "evidence": "相邻协议场景通过"}


def add_gitlink(repo: Path, name: str, dirty: bool) -> None:
    nested = repo / name
    nested.mkdir()
    run("git", "init", "-b", "main", str(nested))
    run("git", "-C", str(nested), "config", "user.email", "test@example.invalid")
    run("git", "-C", str(nested), "config", "user.name", "Protocol test")
    (nested / "tracked.txt").write_text("initial", encoding="utf-8")
    run("git", "-C", str(nested), "add", ".")
    run("git", "-C", str(nested), "commit", "-m", "initial")
    if dirty:
        (nested / "tracked.txt").write_text("dirty", encoding="utf-8")
    run("git", "-C", str(repo), "add", name)


def main() -> int:
    check("PROTOCOL_RESULT=PASS" in verify(FIXTURES / "valid.json", "--structure-only"), "valid structure")
    check("AUTHORIZATION_CARD_FIELDS_INVALID" in verify(FIXTURES / "missing-card-field.json", "--structure-only", expected=1), "missing card field")
    check("FAILURE_COUNT_MISMATCH" in verify(FIXTURES / "mismatched-failure-count.json", "--structure-only", expected=1), "failure count")
    with tempfile.TemporaryDirectory() as directory:
        legacy_v2 = json.loads((FIXTURES / "valid.json").read_text(encoding="utf-8"))
        legacy_v2["protocol_version"] = 2
        legacy_v2.pop("delivery_evidence")
        legacy_path = Path(directory) / "legacy-v2.json"
        legacy_path.write_text(json.dumps(legacy_v2, ensure_ascii=False), encoding="utf-8")
        check("PROTOCOL_RESULT=PASS" in verify(legacy_path, "--structure-only"), "v2 remains valid")
        legacy_v2["protocol_version"] = 3
        legacy_path.write_text(json.dumps(legacy_v2, ensure_ascii=False), encoding="utf-8")
        check("STATE_FIELDS_INVALID" in verify(legacy_path, "--structure-only", expected=1), "v3 requires delivery evidence")
    fence = chr(96) * 3
    protocol_document = (ROOT / "references" / "executable-protocol.md").read_text(encoding="utf-8")
    document_example = re.search(rf"{fence}json\n(.*?)\n{fence}", protocol_document, re.DOTALL)
    check(document_example is not None, "document state example")
    check("--check-worktree" not in protocol_document, "protocol document uses removed CLI flag")
    check("--check-worktree" not in (ROOT / "references" / "git-lifecycle.md").read_text(encoding="utf-8"), "git lifecycle uses removed CLI flag")
    check("不得因无法读取主对话而重新裁定授权" in (ROOT / "references" / "dispatch-packet.md").read_text(encoding="utf-8"), "parent owns chat authorization")
    for role in ("team-developer.toml", "team-explorer.toml", "team-reviewer.toml", "team-ui-maker.toml"):
        instructions = (ROOT / "templates" / "agents" / role).read_text(encoding="utf-8")
        check("主任务是唯一核对聊天授权事实的角色" in instructions, f"{role} delegates chat authorization")
    with tempfile.TemporaryDirectory() as directory:
        example_state = Path(directory) / "example.json"
        example_state.write_text(document_example.group(1), encoding="utf-8")
        check("PROTOCOL_RESULT=PASS" in verify(example_state, "--structure-only"), "document state example structure")

    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory) / "repo"
        repo.mkdir()
        run("git", "init", "-b", "main", str(repo))
        run("git", "-C", str(repo), "config", "user.email", "test@example.invalid")
        run("git", "-C", str(repo), "config", "user.name", "Protocol test")
        run("git", "-C", str(repo), "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
        (repo / "allowed").mkdir()
        (repo / "allowed" / "initial.txt").write_text("initial", encoding="utf-8")
        (repo / ".gitignore").write_text("ignored/\n", encoding="utf-8")
        run("git", "-C", str(repo), "add", ".")
        run("git", "-C", str(repo), "commit", "-m", "initial")
        baseline = run("git", "-C", str(repo), "rev-parse", "HEAD").strip()
        (repo / "ignored").mkdir()
        (repo / "ignored" / "preexisting.txt").write_text("preexisting", encoding="utf-8")

        state = state_for(repo)
        state_path = write_state(repo, state)
        state["git_baseline"] = "0000000000000000000000000000000000000000"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("BASELINE_NOT_CANDIDATE_ANCESTOR" in verify(state_path, *checks(repo), expected=1), "baseline ancestor")
        state["git_baseline"] = baseline
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        state["candidate"]["blocks_new_business_goal"] = False
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("BLOCKS_NEW_BUSINESS_GOAL_MISMATCH" in verify(state_path, *checks(repo), expected=1), "active blocks")
        state["candidate"].update(state="已收口", closeout_state="建议收口", blocks_new_business_goal=False)
        complete_delivery(state)
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("PROTOCOL_RESULT=PASS" in verify(state_path, *checks(repo)), "closed candidate")

        state = state_for(repo)
        state["delivery_evidence"]["before_status"] = "captured"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("DELIVERY_RED_REQUIRED" in verify(state_path, *checks(repo), expected=1), "bug requires red evidence")

        state = state_for(repo)
        state["failure_identity"] = None
        state["delivery_evidence"].update(
            task_kind="feature",
            feedback_signal="python3 feature-test.py",
            before_status="captured",
            before_evidence="只捕获了页面，没有功能失败信号",
        )
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("DELIVERY_RED_REQUIRED" in verify(state_path, *checks(repo), expected=1), "feature requires red evidence")

        state = state_for(repo)
        state["delivery_evidence"]["feedback_signal"] = "python3 different.py"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("DELIVERY_BUG_SIGNAL_MISMATCH" in verify(state_path, *checks(repo), expected=1), "bug signal matches identity")

        state = state_for(repo)
        state["candidate"].update(state="已收口", closeout_state="建议收口", blocks_new_business_goal=False)
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("DELIVERY_TARGET_NOT_PASSED" in verify(state_path, *checks(repo), expected=1), "closeout requires target evidence")
        state["delivery_evidence"]["target_check"] = {"status": "passed", "evidence": "目标命令退出码为 0"}
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("DELIVERY_REGRESSION_INCOMPLETE" in verify(state_path, *checks(repo), expected=1), "closeout requires adjacent regression")
        state["delivery_evidence"]["adjacent_regression"] = {"status": "passed", "evidence": "相邻场景通过"}
        state["delivery_evidence"]["real_environment"] = {"status": "pending", "evidence": None}
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("DELIVERY_REAL_ENVIRONMENT_INCOMPLETE" in verify(state_path, *checks(repo), expected=1), "closeout requires real environment")

        state = state_for(repo)
        state["delivery_evidence"].update(task_kind="visual", before_status="red")
        state["failure_identity"] = None
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("DELIVERY_VISUAL_CAPTURE_REQUIRED" in verify(state_path, *checks(repo), expected=1), "visual requires captured baseline")

        state = state_for(repo)
        state["candidate"]["state"] = "待判断"
        state["delivery_evidence"].update(before_status="pending", before_evidence=None)
        state["delivery_evidence"]["real_environment"] = {"status": "pending", "evidence": None}
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("PROTOCOL_RESULT=PASS" in verify(state_path, *checks(repo)), "feedback setup may be pending")
        feedback_file = repo / "allowed" / "tests" / "repro.py"
        feedback_file.parent.mkdir()
        feedback_file.write_text("assert False\n", encoding="utf-8")
        check("PROTOCOL_RESULT=PASS" in verify(state_path, *checks(repo)), "pending allows feedback changes")
        shutil.rmtree(feedback_file.parent)
        (repo / "allowed" / "production.py").write_text("production = True\n", encoding="utf-8")
        check("DIFF_OUTSIDE_FEEDBACK_SCOPE: allowed/production.py" in verify(state_path, *checks(repo), expected=1), "pending blocks production changes")
        for bypass_status in ("baseline-green", "captured", "not-applicable"):
            state["delivery_evidence"].update(before_status=bypass_status, before_evidence=f"伪造状态 {bypass_status}")
            state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            check("DELIVERY_RED_REQUIRED" in verify(state_path, *checks(repo), expected=1), f"bug rejects {bypass_status} bypass")
        state["delivery_evidence"].update(before_status="red", before_evidence="反馈信号已经真实失败")
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("DIFF_OUTSIDE_FEEDBACK_SCOPE: allowed/production.py" in verify(state_path, *checks(repo), expected=1), "waiting red still blocks production changes")
        state["delivery_evidence"].update(task_kind="visual", before_status="red")
        state["failure_identity"] = None
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("DELIVERY_VISUAL_CAPTURE_REQUIRED" in verify(state_path, *checks(repo), expected=1), "visual rejects red bypass")
        state["delivery_evidence"].update(before_status="captured", before_evidence="浏览器基线已捕获")
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("DIFF_OUTSIDE_FEEDBACK_SCOPE: allowed/production.py" in verify(state_path, *checks(repo), expected=1), "waiting captured still blocks production changes")
        (repo / "allowed" / "production.py").unlink()
        state = state_for(repo)
        state["candidate"]["state"] = "待判断"
        state["delivery_evidence"].update(before_status="pending", before_evidence=None, feedback_scope=["outside-feedback"])
        state["delivery_evidence"]["real_environment"] = {"status": "pending", "evidence": None}
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("DELIVERY_FEEDBACK_SCOPE_OUTSIDE_WRITE_SCOPE" in verify(state_path, *checks(repo), expected=1), "feedback scope stays inside write scope")
        state = state_for(repo)
        state["candidate"]["state"] = "待判断"
        state["delivery_evidence"].update(before_status="pending", before_evidence=None)
        state["delivery_evidence"]["real_environment"] = {"status": "pending", "evidence": None}
        state["candidate"]["state"] = "开发中"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("DELIVERY_RED_REQUIRED" in verify(state_path, *checks(repo), expected=1), "production implementation requires red")

        state = state_for(repo)
        state["failure_identity"] = None
        state["lifecycle"] = "recovery-diagnosis"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("RECOVERY_LIFECYCLE_WITHOUT_THREE_FAILURES" in verify(state_path, *checks(repo), expected=1), "non-fault diagnosis")
        state["lifecycle"] = "recovery-repair"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("RECOVERY_LIFECYCLE_WITHOUT_THREE_FAILURES" in verify(state_path, *checks(repo), expected=1), "non-fault repair")

        state = state_for(repo)
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        (repo / "allowed" / "initial.txt").write_text("changed", encoding="utf-8")
        state["candidate"]["blocks_new_business_goal"] = False
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("BLOCKS_NEW_BUSINESS_GOAL_MISMATCH" in verify(state_path, *checks(repo), expected=1), "dirty active")
        state["candidate"]["blocks_new_business_goal"] = True
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("PROTOCOL_RESULT=PASS" in verify(state_path, *checks(repo)), "active candidate")
        state["authorization_card"].update(authorization_status="未获得", authorization_message="草稿", authorization_basis="等待精确1")
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("AUTHORIZATION_REQUIRED" in verify(state_path, *checks(repo), expected=1), "authorization")
        state = state_for(repo)
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        state["authorization_card"]["execution_endpoint"] = "自定义"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("CARD_CUSTOM_ENDPOINT_EMPTY" in verify(state_path, *checks(repo), expected=1), "custom endpoint")
        state["authorization_card"]["execution_endpoint"] = "自定义：本地验收完成"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("PROTOCOL_RESULT=PASS" in verify(state_path, *checks(repo)), "custom endpoint pass")
        state = state_for(repo)
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("PROTOCOL_RESULT=PASS" in verify(state_path, *checks(repo)), "default pass")
        default_state_checks = ("--repo", str(repo), "--skill-root", str(ROOT))
        check("PROTOCOL_RESULT=PASS" in verify(state_path, *default_state_checks), "realtime default")
        check("REPO_NOT_GIT_ROOT" in verify(state_path, "--repo", str(repo / "allowed"), "--skill-root", str(ROOT), expected=1), "repo root")
        state["failure_identity"] = None
        state["delivery_evidence"].update(
            task_kind="feature",
            feedback_signal="python3 feature-test.py",
            before_evidence="功能尚未实现，目标测试退出码为 1",
        )
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("PROTOCOL_RESULT=PASS" in verify(state_path, *checks(repo)), "non-fault pass")

        state = state_for(repo)
        state["candidate"]["isolation"] = "当前目录候选分支"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("MAIN_BRANCH_REQUIRES_DIRECT_ISOLATION" in verify(state_path, *checks(repo), expected=1), "main isolation")

        state = state_for(repo)
        state["candidate"]["isolation"] = "任意候选"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("CANDIDATE_ISOLATION_INVALID" in verify(state_path, *checks(repo), expected=1), "isolation enum")

        state = state_for(repo)
        state["lifecycle"] = "recovery-diagnosis"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("RECOVERY_LIFECYCLE_WITHOUT_THREE_FAILURES" in verify(state_path, *checks(repo), expected=1), "diagnosis lifecycle")
        state["lifecycle"] = "recovery-repair"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("RECOVERY_LIFECYCLE_WITHOUT_THREE_FAILURES" in verify(state_path, *checks(repo), expected=1), "repair lifecycle")

        run("git", "-C", str(repo), "checkout", "-b", "codex/impersonated-main")
        state = state_for(repo)
        state["primary_branch"] = "codex/impersonated-main"
        state["candidate"]["branch"] = "codex/impersonated-main"
        state["authorization_card"]["candidate_and_worktree"] = f"codex/impersonated-main；{repo}"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("STATE_PRIMARY_BRANCH_MISMATCH" in verify(state_path, *checks(repo), expected=1), "primary impersonation")
        run("git", "-C", str(repo), "checkout", "main")

        run("git", "-C", str(repo), "symbolic-ref", "-d", "refs/remotes/origin/HEAD")
        run("git", "-C", str(repo), "checkout", "-b", "codex/no-primary")
        state = state_for(repo)
        state["primary_branch"] = "unresolved"
        state["candidate"].update(branch="codex/no-primary", isolation="当前目录候选分支")
        state["authorization_card"]["candidate_and_worktree"] = f"codex/no-primary；{repo}"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("PROTOCOL_RESULT=PASS" in verify(state_path, *checks(repo)), "offline candidate")
        state["candidate"]["isolation"] = "主分支直接写"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("DIRECT_MAIN_WRITE_REQUIRES_PRIMARY_BRANCH" in verify(state_path, *checks(repo), expected=1), "offline direct write")
        run("git", "-C", str(repo), "checkout", "main")
        run("git", "-C", str(repo), "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")

        run("git", "-C", str(repo), "checkout", "-b", "release/main")
        run("git", "-C", str(repo), "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/release/main")
        state = state_for(repo)
        state["primary_branch"] = "release/main"
        state["candidate"].update(branch="release/main", isolation="主分支直接写")
        state["authorization_card"]["candidate_and_worktree"] = f"release/main；{repo}"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("PROTOCOL_RESULT=PASS" in verify(state_path, *checks(repo)), "slash primary")
        run("git", "-C", str(repo), "checkout", "main")
        run("git", "-C", str(repo), "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")

        state = state_for(repo)
        state["candidate"]["branch"] = "codex/stale-candidate"
        state["authorization_card"]["candidate_and_worktree"] = f"codex/stale-candidate；{repo}"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("CURRENT_BRANCH_MISMATCH" in verify(state_path, *checks(repo), expected=1), "branch mismatch")

        state = state_for(repo)
        state["primary_branch"] = "codex/impersonated-main"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("STATE_PRIMARY_BRANCH_MISMATCH" in verify(state_path, *checks(repo), expected=1), "primary state")

        state = state_for(repo)
        state["candidate"]["worktree"] = str(repo / "wrong")
        state["authorization_card"]["candidate_and_worktree"] = f"main；{repo / 'wrong'}"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("CURRENT_WORKTREE_MISMATCH" in verify(state_path, *checks(repo), expected=1), "worktree mismatch")

        state = state_for(repo)
        state["candidate"]["worktree"] = "."
        state["authorization_card"]["candidate_and_worktree"] = "main；."
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        structure_checks = ("--repo", str(repo), "--state-dir", str(repo / ".dev-team" / "state"), "--structure-only")
        check("CANDIDATE_WORKTREE_MUST_BE_ABSOLUTE" in verify(state_path, *structure_checks, expected=1), "absolute worktree")

        state = state_for(repo)
        state["authorization_card"]["candidate_and_worktree"] = f"other；{repo}"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("CARD_CANDIDATE_MISMATCH" in verify(state_path, *checks(repo), expected=1), "card candidate")

        state = state_for(repo)
        state["authorization_card"]["authorization_basis"] = "摘要"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("AUTHORIZATION_EVIDENCE_INVALID" in verify(state_path, *checks(repo), expected=1), "authorization evidence")

        state = state_for(repo)
        state["write_scope"]["discovered_paths"] = [{"path": "shared", "reason": "权威入口", "business_goal": "验证协议", "discovered_at": "2026-09-02T00:00:00Z"}]
        (repo / "shared").mkdir()
        (repo / "shared" / "entry.txt").write_text("discovered", encoding="utf-8")
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        state["write_scope"]["discovered_paths"][0]["business_goal"] = "错误目标"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("DISCOVERED_PATH_BUSINESS_GOAL_MISMATCH" in verify(state_path, *checks(repo), expected=1), "discovered goal")
        state["write_scope"]["discovered_paths"][0]["business_goal"] = "验证协议"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("PROTOCOL_RESULT=PASS" in verify(state_path, *checks(repo)), "discovered pass")
        preexisting = repo / "ignored" / "preexisting.txt"
        preexisting.write_text("changed", encoding="utf-8")
        check("PROTOCOL_RESULT=PASS" in verify(state_path, *checks(repo)), "ignored preexisting excluded")
        (repo / "outside.txt").write_text("outside", encoding="utf-8")
        check("DIFF_OUTSIDE_WRITE_SCOPE: outside.txt" in verify(state_path, *checks(repo), expected=1), "outside")
        (repo / "outside.txt").unlink()
        ignored_outside = repo / "ignored" / "outside.txt"
        ignored_outside.write_text("ignored outside", encoding="utf-8")
        check("PROTOCOL_RESULT=PASS" in verify(state_path, *checks(repo)), "ignored new file excluded")
        ignored_outside.unlink()
        check("PROTOCOL_RESULT=PASS" in verify(state_path, *checks(repo)), "ignored cleanup")
        shutil.rmtree(repo / "shared")

        state = state_for(repo)
        state["production_failure_count"] = 3
        state["failure_records"] = [failure(1), failure(2), failure(3)]
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("THREE_FAILURES_REQUIRE_RECOVERY_DISPATCH" in verify(state_path, *checks(repo), expected=1), "three failures")
        state["failure_records"][2]["hypothesis"] = "hypothesis 1"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("FAILURE_RECORD_HYPOTHESIS_DUPLICATE" in verify(state_path, *checks(repo), expected=1), "duplicate hypothesis")
        state["failure_records"][2]["hypothesis"] = "hypothesis 3"
        state["lifecycle"] = "recovery-diagnosis"
        state["authorization_card"]["version"] = "2"
        state["recovery"] = {"kind": "diagnosis", "pre_recovery_authorization": {"card_version": "1", "authorization_message": "1", "authorization_basis": "最新完整十四项卡的精确1"}, "diagnosis_authorization": {"card_version": "2", "authorization_message": "1", "authorization_basis": "最新完整十四项卡的精确1"}, "new_evidence": "新的复现日志", "diagnosis_stage": "2", "diagnosis_conclusion": None, "repair_stable_signal": None, "repair_hypothesis": None, "repair_authorization": None, "previous_failure_ids": ["failure-1", "failure-2", "failure-3"]}
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("PROTOCOL_RESULT=PASS" in verify(state_path, *checks(repo)), "recovery diagnosis")
        state["lifecycle"] = "recovery-repair"
        state["recovery"]["kind"] = "repair"
        state["recovery"]["diagnosis_stage"] = "completed"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("RECOVERY_REPAIR_REQUIRES_REPLACEMENT_CARD" in verify(state_path, *checks(repo), expected=1), "repair old diagnosis card")
        state["recovery"].update(diagnosis_conclusion="根因已证实", repair_stable_signal="python3 reproduce.py", repair_hypothesis="新的假设", repair_authorization={"card_version": "2", "authorization_message": "1", "authorization_basis": "最新完整十四项卡的精确1"})
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("RECOVERY_REPAIR_REQUIRES_REPLACEMENT_CARD" in verify(state_path, *checks(repo), expected=1), "repair reused card")
        state["authorization_card"]["version"] = "3"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("RECOVERY_REPAIR_AUTHORIZATION_STALE" in verify(state_path, *checks(repo), expected=1), "repair stale evidence")
        state["recovery"]["repair_authorization"]["card_version"] = "3"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("PROTOCOL_RESULT=PASS" in verify(state_path, *checks(repo)), "repair replacement")

        wrong_path = repo / ".dev-team" / "state" / "different.json"
        wrong_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        location_checks = checks(repo)
        check("STATE_LOCATION_MISMATCH" in verify(wrong_path, *location_checks, expected=1), "state location")
        wrong_path.unlink()
        unrelated = repo / ".dev-team" / "state" / "unrelated-task.json"
        state["write_scope"]["initial_allowed_paths"].append(".dev-team")
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        unrelated.write_text("{}", encoding="utf-8")
        check("PROTOCOL_RESULT=PASS" in verify(state_path, *checks(repo)), "multiple task states")
        unrelated.unlink()
        committed_outside = repo / "committed-outside.txt"
        committed_outside.write_text("committed outside", encoding="utf-8")
        run("git", "-C", str(repo), "add", "committed-outside.txt")
        run("git", "-C", str(repo), "commit", "-m", "outside")
        state = state_for(repo)
        state["git_baseline"] = baseline
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("DIFF_OUTSIDE_WRITE_SCOPE: committed-outside.txt" in verify(state_path, *checks(repo), expected=1), "committed outside")

    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory) / "repo"
        repo.mkdir()
        run("git", "init", "-b", "main", str(repo))
        run("git", "-C", str(repo), "config", "user.email", "test@example.invalid")
        run("git", "-C", str(repo), "config", "user.name", "Protocol test")
        run("git", "-C", str(repo), "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
        (repo / "allowed").mkdir()
        (repo / "outside").mkdir()
        (repo / "outside" / "old.txt").write_text("rename", encoding="utf-8")
        run("git", "-C", str(repo), "add", ".")
        run("git", "-C", str(repo), "commit", "-m", "initial")
        state = state_for(repo)
        state_path = write_state(repo, state)
        state["protocol_version"] = 1
        state["migration"] = None
        state.pop("delivery_evidence")
        state.pop("ignored_untracked_policy")
        state["ignored_untracked_at_start"] = []
        state["recovery"] = {
            "kind": "none",
            "new_evidence": None,
            "diagnosis_stage": None,
            "diagnosis_conclusion": None,
            "repair_stable_signal": None,
            "repair_hypothesis": None,
            "repair_authorization": None,
            "previous_failure_ids": [],
        }
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("PROTOCOL_VERSION_INVALID" in verify(state_path, *checks(repo), expected=1), "legacy state rejected before migration")
        check("PROTOCOL_RESULT=PASS" in verify(state_path, "--migrate-v1-state", *checks(repo)), "v1 migration")
        migrated = json.loads(state_path.read_text(encoding="utf-8"))
        check(migrated["protocol_version"] == 2 and migrated["migration"]["from_protocol_version"] == 1, "migration evidence")
        check(set(migrated["recovery"]) == set(state_for(repo)["recovery"]), "legacy recovery normalized")
        check("V1_MIGRATION_REQUIRES_PROTOCOL_VERSION_1" in verify(state_path, "--migrate-v1-state", *checks(repo), expected=1), "migration cannot relabel v2")
        state = state_for(repo)
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        run("git", "-C", str(repo), "mv", "outside/old.txt", "allowed/renamed.txt")
        check("outside/old.txt" in verify(state_path, *checks(repo), expected=1), "rename old path outside scope")

    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory) / "repo"
        repo.mkdir()
        run("git", "init", "-b", "main", str(repo))
        run("git", "-C", str(repo), "config", "user.email", "test@example.invalid")
        run("git", "-C", str(repo), "config", "user.name", "Protocol test")
        run("git", "-C", str(repo), "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
        (repo / "allowed").mkdir()
        (repo / "allowed" / "initial.txt").write_text("initial", encoding="utf-8")
        run("git", "-C", str(repo), "add", ".")
        run("git", "-C", str(repo), "commit", "-m", "initial")
        state = state_for(repo)
        state_path = write_state(repo, state)
        run("git", "-C", str(repo), "update-index", "--assume-unchanged", "allowed/initial.txt")
        check("SPECIAL_INDEX_ENTRY: allowed/initial.txt" in verify(state_path, *checks(repo), expected=1), "special index")
        run("git", "-C", str(repo), "update-index", "--no-assume-unchanged", "allowed/initial.txt")
        run("git", "-C", str(repo), "config", "core.sparseCheckout", "true")
        check("SPARSE_CHECKOUT_NOT_SUPPORTED" in verify(state_path, *checks(repo), expected=1), "sparse checkout")

    for name, dirty in (("干净子模块", False), ("脏子模块", True)):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            repo.mkdir()
            run("git", "init", "-b", "main", str(repo))
            run("git", "-C", str(repo), "config", "user.email", "test@example.invalid")
            run("git", "-C", str(repo), "config", "user.name", "Protocol test")
            run("git", "-C", str(repo), "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
            (repo / "allowed").mkdir()
            (repo / "allowed" / "initial.txt").write_text("initial", encoding="utf-8")
            run("git", "-C", str(repo), "add", ".")
            run("git", "-C", str(repo), "commit", "-m", "initial")
            state = state_for(repo)
            state_path = write_state(repo, state)
            add_gitlink(repo, name, dirty)
            check(f"GITLINK_NOT_SUPPORTED: {name}" in verify(state_path, *checks(repo), expected=1), f"gitlink {name}")

    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory) / "repo"
        repo.mkdir()
        run("git", "init", "-b", "main", str(repo))
        run("git", "-C", str(repo), "config", "user.email", "test@example.invalid")
        run("git", "-C", str(repo), "config", "user.name", "Protocol test")
        run("git", "-C", str(repo), "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
        allowed = repo / "中文允许"
        allowed.mkdir()
        tracked = allowed / "初始.txt"
        tracked.write_text("initial", encoding="utf-8")
        run("git", "-C", str(repo), "add", ".")
        run("git", "-C", str(repo), "commit", "-m", "initial")
        state = state_for(repo)
        state["write_scope"]["initial_allowed_paths"] = ["中文允许"]
        state["delivery_evidence"]["feedback_scope"] = ["中文允许"]
        state_path = write_state(repo, state)
        tracked.write_text("changed", encoding="utf-8")
        check("PROTOCOL_RESULT=PASS" in verify(state_path, *checks(repo)), "unicode allowed")
        outside = repo / "中文范围外.txt"
        outside.write_text("outside", encoding="utf-8")
        check("DIFF_OUTSIDE_WRITE_SCOPE: 中文范围外.txt" in verify(state_path, *checks(repo), expected=1), "unicode outside")
        outside.unlink()
        run("git", "-C", str(repo), "update-index", "--assume-unchanged", "中文允许/初始.txt")
        check("SPECIAL_INDEX_ENTRY: 中文允许/初始.txt" in verify(state_path, *checks(repo), expected=1), "unicode special index")

    if os.environ.get("DEV_TEAM_SKIP_RUNTIME_DRIFT") != "1":
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            runtime = Path(directory) / "dev-team"
            agents = Path(directory) / "agents"
            shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(ROOT, runtime, ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(ROOT / "templates" / "agents", agents)
            verifier = runtime / "scripts" / "verify-protocol.py"
            verifier.write_text(verifier.read_text(encoding="utf-8") + "\n# runtime drift\n", encoding="utf-8")
            result = subprocess.run(
                ("bash", str(source / "scripts" / "verify-setup.sh"), str(agents), str(runtime)),
                text=True,
                capture_output=True,
                env={**NO_BYTECODE, "DEV_TEAM_SKIP_RUNTIME_DRIFT": "1"},
            )
            check(result.returncode == 1, "runtime drift status")
            check("RUNTIME_SKILL_DIFFERS: scripts/verify-protocol.py" in result.stdout + result.stderr, "runtime drift")
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            runtime = Path(directory) / "dev-team"
            agents = Path(directory) / "agents"
            shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(ROOT, runtime, ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(ROOT / "templates" / "agents", agents)
            (runtime / "scripts" / "__pycache__").mkdir(exist_ok=True)
            result = subprocess.run(
                ("bash", str(source / "scripts" / "verify-setup.sh"), str(agents), str(runtime)),
                text=True,
                capture_output=True,
                env={**NO_BYTECODE, "DEV_TEAM_SKIP_RUNTIME_DRIFT": "1"},
            )
            check(result.returncode == 1, "runtime cache status")
            check("PYTHON_CACHE_PRESENT: RUNTIME" in result.stdout + result.stderr, "runtime cache")
    print("PROTOCOL_SCENARIOS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

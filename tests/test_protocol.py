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


def v4_state() -> dict:
    return json.loads((FIXTURES / "v4-frozen-scope-valid.json").read_text(encoding="utf-8"))


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


def v5_authorization_scenarios() -> None:
    """Exercise grants against real writes; chat truth remains the coordinator's job."""
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory) / "repo"
        repo.mkdir()
        run("git", "init", "-b", "main", str(repo))
        run("git", "-C", str(repo), "config", "user.email", "test@example.invalid")
        run("git", "-C", str(repo), "config", "user.name", "Protocol test")
        run("git", "-C", str(repo), "config", "dev-team.primaryBranch", "main")
        (repo / "allowed").mkdir()
        target = repo / "allowed" / "initial.txt"
        target.write_text("initial\n", encoding="utf-8")
        run("git", "-C", str(repo), "add", ".")
        run("git", "-C", str(repo), "commit", "-m", "initial")

        def fresh_state() -> dict:
            state = json.loads((FIXTURES / "v5-explicit-request-valid.json").read_text(encoding="utf-8"))
            state["skill_root"] = str(ROOT)
            state["git_baseline"] = run("git", "-C", str(repo), "rev-parse", "HEAD").strip()
            state["candidate"].update(branch="main", worktree=str(repo), isolation="主分支直接写")
            state["authorization_card"]["candidate_and_worktree"] = f"main；{repo}"
            return state

        target.write_text("corrected\n", encoding="utf-8")
        legacy = fresh_state()
        legacy["protocol_version"] = 4
        legacy.pop("task_assessment")
        legacy.pop("authorization_context")
        legacy.pop("collaboration")
        legacy.pop("quality_exceptions")
        legacy.pop("diagnostic_events")
        legacy["delivery_evidence"].pop("verification_mode")
        # Demonstrate the actual old authorization behavior, beyond version rejection.
        check("AUTHORIZATION_EVIDENCE_INVALID" in verify(write_state(repo, legacy), *checks(repo), expected=1), "v4 still rejects natural-language authorization")
        legacy["authorization_card"].update(authorization_message="1", authorization_basis="最新完整十四项卡的精确1")
        check("PROTOCOL_RESULT=PASS" in verify(write_state(repo, legacy), *checks(repo)), "same real write passes unchanged v4 with its exact shortcut")
        print("V4_AUTHORIZATION_BEHAVIOR=PASS (natural language rejected; exact shortcut accepted)", flush=True)

        failures = []

        def expect_case(name: str, state: dict, expected: int, signal: str) -> None:
            result = subprocess.run(
                (sys.executable, str(VERIFY), "--state", str(write_state(repo, state)), *checks(repo)),
                text=True, capture_output=True, env=NO_BYTECODE,
            )
            output = result.stdout + result.stderr
            if result.returncode != expected or signal not in output:
                failures.append(f"{name}: expected exit {expected} / {signal}, got exit {result.returncode}: {output.strip()}")

        expect_case("explicit request permits reversible file write", fresh_state(), 0, "PROTOCOL_RESULT=PASS")

        state = fresh_state()
        state["authorization_context"]["intent"] = "discuss"
        state["authorization_card"]["authorization_message"] = "讨论一下这份文档应该怎么改"
        expect_case("discussion cannot authorize a real write", state, 1, "DISCUSSION_CANNOT_WRITE")

        state = fresh_state()
        state["authorization_context"]["planned_actions"] = [{"action": "workspace-write", "target": "allowed/other.txt"}]
        expect_case("grant binds the exact target", state, 1, "PLANNED_ACTION_NOT_AUTHORIZED")

        state = fresh_state()
        state["authorization_context"]["granted_actions"] = [{"action": "pr-create", "target": "origin:codex/example->main"}]
        state["authorization_context"]["planned_actions"] = [{"action": "merge", "target": "origin:codex/example->main"}]
        expect_case("PR grant cannot authorize merge despite reversible risk label", state, 1, "PLANNED_ACTION_NOT_AUTHORIZED")

        state = fresh_state()
        merge = {"action": "merge", "target": "origin:codex/example->main"}
        state["authorization_context"].update(granted_actions=[merge.copy()], planned_actions=[merge.copy()])
        expect_case("known high risk action requires impact and rollback", state, 1, "HIGH_RISK_DETAILS_REQUIRED")

        state = fresh_state()
        outside = repo / "outside.txt"
        outside.write_text("outside authorized scope\n", encoding="utf-8")
        expect_case("natural-language authorization preserves live diff scope", state, 1, "DIFF_OUTSIDE_WRITE_SCOPE: outside.txt")
        outside.unlink()

        state = fresh_state()
        state["authorization_context"]["source"] = "explicit-consent"
        state["authorization_card"]["authorization_message"] = "同意按这些动作执行"
        expect_case("natural-language consent is accepted", state, 0, "PROTOCOL_RESULT=PASS")
        state["authorization_context"]["source"] = "shortcut"
        expect_case("shortcut must preserve actual 1", state, 1, "AUTHORIZATION_SHORTCUT_INVALID")
        state["authorization_card"]["authorization_message"] = "1"
        expect_case("1 remains a shortcut", state, 0, "PROTOCOL_RESULT=PASS")

        state = fresh_state()
        state["authorization_context"]["planned_actions"] = [{"action": "commit", "target": "main"}]
        expect_case("local completion does not authorize commit", state, 1, "PLANNED_ACTION_NOT_AUTHORIZED")
        state = fresh_state()
        state["authorization_context"]["granted_actions"][0]["target"] = "allowed/*"
        expect_case("wildcard grants are not exact objects", state, 1, "ACTION_TARGET_NOT_EXACT")
        state = fresh_state()
        state["authorization_context"].update(granted_actions=[], planned_actions=[])
        expect_case("unplanned historical diff still needs a grant", state, 1, "DIFF_OUTSIDE_AUTHORIZED_TARGETS")
        state["authorization_context"]["intent"] = "discuss"
        expect_case("discussion cannot hide real diff with empty actions", state, 1, "DISCUSSION_CANNOT_WRITE")
        state = fresh_state()
        state["task_assessment"]["operation_risk"] = "read-only"
        expect_case("difficulty does not override read-only impact", state, 1, "READ_ONLY_CANNOT_WRITE")

        def agent(identifier: str, role: str) -> dict:
            return {"id": identifier, "role": role, "model": "gpt-5.6-terra" if role == "explorer" else "gpt-6-astra", "effort": "high", "permission": "workspace-write" if role in {"developer", "ui-maker"} else "read-only", "observation": "测试夹具中的请求回执，不声称真实模型已运行"}

        def delegated_state() -> dict:
            state = fresh_state()
            state["task_assessment"]["difficulty"] = "normal"
            state["collaboration"].update(writer="dev-1", dispatches=[agent("dev-1", "developer")])
            return state

        state = fresh_state()
        state["task_assessment"]["difficulty"] = "normal"
        expect_case("ordinary feature uses one executor", state, 1, "DELEGATED_WRITER_REQUIRED")
        expect_case("one observed executor is valid", delegated_state(), 0, "PROTOCOL_RESULT=PASS")
        state = delegated_state()
        state["collaboration"]["dispatches"].append(agent("dev-2", "developer"))
        expect_case("two current writers are rejected", state, 1, "SINGLE_WRITER_REQUIRED")
        state["collaboration"].update(writer="dev-2", dispatches=[agent("dev-2", "developer")])
        expect_case("completed writer can hand off current ownership", state, 0, "PROTOCOL_RESULT=PASS")
        state = delegated_state()
        state["collaboration"]["dispatches"][0]["effort"] = "xhigh"
        expect_case("model override needs an explicit basis", state, 1, "MODEL_OVERRIDE_MUST_BE_OBJECT")
        state["collaboration"]["dispatches"][0]["override"] = {"reason": "复杂状态提高思考强度", "authorization_card_version": "1", "authorization_evidence": "主任务核对当前授权和工具支持的 xhigh"}
        expect_case("authorized xhigh is not blocked by defaults", state, 0, "PROTOCOL_RESULT=PASS")
        state["collaboration"]["dispatches"][0]["override"]["authorization_card_version"] = "0"
        expect_case("stale model override is rejected", state, 1, "MODEL_OVERRIDE_AUTHORIZATION_STALE")
        state = delegated_state()
        explorer = agent("explorer-1", "explorer")
        explorer.update(model="gpt-6-astra", override={"reason": "复杂勘察", "authorization_card_version": "1", "authorization_evidence": "当前允许升级，工具能力已核对"})
        state["collaboration"]["dispatches"].append(explorer)
        expect_case("exploration can use a supported stronger model", state, 0, "PROTOCOL_RESULT=PASS")
        explorer["permission"] = "workspace-write"
        expect_case("model override cannot widen read-only role", state, 1, "DISPATCH_MODEL_OR_PERMISSION_MISMATCH")

        def finished_state() -> dict:
            state = fresh_state()
            state["candidate"]["state"] = "可收口"
            for name in ("target_check", "adjacent_regression", "real_environment"):
                state["delivery_evidence"][name].update(status="passed", evidence="测试夹具中的固定检查结果")
            return state

        state = finished_state()
        merge = {"action": "merge", "target": "origin:codex/example->main", "impact": "变更 main", "rollback": "创建反向提交"}
        state["authorization_context"]["granted_actions"].append(merge)
        state["authorization_context"]["planned_actions"].append(merge.copy())
        expect_case("known high risk needs independent acceptance", state, 1, "INDEPENDENT_REVIEW_INCOMPLETE")
        state["candidate"]["state"] = "开发中"
        expect_case("merge cannot bypass review by claiming development stage", state, 1, "INDEPENDENT_REVIEW_INCOMPLETE")
        state["candidate"]["state"] = "可收口"
        state["collaboration"]["dispatches"] = [agent("review-1", "reviewer")]
        state["collaboration"]["independent_review"] = {"status": "passed", "reviewer_id": "review-1", "evidence": "独立检查的原始证据位置（测试夹具）"}
        expect_case("high risk with exact grant and independent review", state, 0, "PROTOCOL_RESULT=PASS")
        state["collaboration"]["independent_review"]["reviewer_id"] = "main"
        expect_case("writer cannot impersonate independent reviewer", state, 1, "INDEPENDENT_REVIEWER_REQUIRED")

        exception = {"id": "compatibility", "reason": "短期兼容旧接口", "boundary": "仅旧接口适配层", "exit_condition": "调用方迁移完成后删除", "authorization_card_version": "1", "authorization_evidence": "用户明确同意该局部取舍", "status": "approved"}
        state = finished_state()
        state["quality_exceptions"] = [exception.copy()]
        expect_case("explicit bounded quality exception permits completion", state, 0, "PROTOCOL_RESULT=PASS")
        state["quality_exceptions"][0]["status"] = "pending"
        expect_case("unapproved debt prevents completion", state, 1, "QUALITY_EXCEPTION_UNAPPROVED")
        state["quality_exceptions"][0]["status"] = "approved"
        state["delivery_evidence"]["target_check"].update(status="failed", evidence="固定检查失败")
        expect_case("approved debt cannot waive fixed checks", state, 1, "DELIVERY_TARGET_NOT_PASSED")
        state = finished_state()
        finding = {"id": "unrelated", "summary": "无关格式建议", "classification": "deferred", "causal_relation": "historical-debt", "causal_evidence": "不影响固定目标", "action": "record-only", "status": "open"}
        state["finding_records"] = [finding]
        expect_case("unrelated findings do not restart completed work", state, 0, "PROTOCOL_RESULT=PASS")
        finding.update(classification="scope-change", causal_relation="new-request", action="stop-for-decision")
        state["candidate"].update(state="阻塞", closeout_state="阻塞")
        expect_case("undecided new scope blocks planned writes", state, 1, "BLOCKED_CANDIDATE_CANNOT_EXECUTE")
        state["authorization_context"]["planned_actions"] = []
        expect_case("blocked record can retain existing candidate evidence", state, 0, "PROTOCOL_RESULT=PASS")
        state = fresh_state()
        state["scope_control"]["status"] = "draft"
        expect_case("v5 keeps v4 scope freeze", state, 1, "SCOPE_CONTROL_STATUS_INVALID")

        state = fresh_state()
        state["delivery_evidence"].update(task_kind="feature", before_status="baseline-green", before_evidence="既有基础检查通过，新功能使用相称目标验证")
        expect_case("new feature need not manufacture red", state, 0, "PROTOCOL_RESULT=PASS")
        state["delivery_evidence"].update(before_status="pending", before_evidence=None)
        expect_case("unprepared feature cannot claim ready", state, 1, "V5_FEEDBACK_EVIDENCE_REQUIRED")
        state = fresh_state()
        state["delivery_evidence"].update(task_kind="visual", verification_mode="new-ui", before_status="not-applicable", before_evidence="此前不存在页面")
        expect_case("new UI has no invented historical baseline", state, 0, "PROTOCOL_RESULT=PASS")
        state["delivery_evidence"]["verification_mode"] = "existing-ui"
        expect_case("existing UI still requires captured baseline", state, 1, "V5_FEEDBACK_EVIDENCE_REQUIRED")
        state["delivery_evidence"].update(before_status="captured", before_evidence="准确路由与状态截图")
        expect_case("existing UI accepts captured evidence", state, 0, "PROTOCOL_RESULT=PASS")

        def bug_state() -> dict:
            state = fresh_state()
            state["failure_identity"] = {"id": "original-bug", "symptom": "原始操作偶发失败", "stable_signal": "python3 reproduce.py"}
            state["delivery_evidence"].update(task_kind="bug", verification_mode="bug-repro", feedback_signal="python3 reproduce.py", before_status="red", before_evidence="原始操作失败且根因路径已捕获")
            return state

        state = bug_state()
        expect_case("reproducible bug retains original red", state, 0, "PROTOCOL_RESULT=PASS")
        state["delivery_evidence"]["feedback_signal"] = "python3 easier.py"
        expect_case("v5 cannot swap original bug signal", state, 1, "DELIVERY_BUG_SIGNAL_MISMATCH")
        state = bug_state()
        state["delivery_evidence"].update(verification_mode="bug-diagnosis", before_status="captured", before_evidence="原始偶发日志与追踪", feedback_scope=["allowed/initial.txt"], unverified_boundaries=["仅可诊断，尚未证实故障修复"])
        expect_case("intermittent bug may deliver diagnostic evidence", state, 0, "PROTOCOL_RESULT=PASS")
        state["delivery_evidence"]["unverified_boundaries"] = []
        expect_case("diagnostic work cannot hide unverified repair", state, 1, "DIAGNOSIS_UNVERIFIED_BOUNDARY_REQUIRED")
        state["delivery_evidence"]["unverified_boundaries"] = ["尚未修复"]
        state["authorization_context"]["granted_actions"][0]["target"] = "allowed"
        state["authorization_context"]["planned_actions"][0]["target"] = "allowed"
        production = repo / "allowed/production.txt"
        production.write_text("production behavior\n", encoding="utf-8")
        expect_case("diagnostic mode cannot write production outside feedback", state, 1, "DIFF_OUTSIDE_FEEDBACK_SCOPE")
        production.unlink()

        state = bug_state()
        state["diagnostic_events"] = [{"kind": kind, "evidence": "命令未经过原始故障路径，不能证伪假设", "observed_at": "2026-09-05T00:00:00Z"} for kind in ("tool", "syntax", "environment")]
        expect_case("tool syntax environment events do not count as original failures", state, 0, "PROTOCOL_RESULT=PASS")
        state["production_failure_count"] = 3
        expect_case("counter cannot substitute diagnostic events for failures", state, 1, "FAILURE_COUNT_MISMATCH")
        state = bug_state()
        state["failure_records"] = [failure(index) for index in range(1, 4)]
        state["production_failure_count"] = 3
        expect_case("three original failed hypotheses still stop", state, 1, "THREE_FAILURES_REQUIRE_RECOVERY_DISPATCH")
        state["lifecycle"] = "recovery-diagnosis"
        state["authorization_card"].update(version="2", authorization_message="同意按新证据进行恢复诊断", authorization_basis="主任务核对独立诊断授权")
        state["scope_control"]["authorization_card_version"] = "2"
        state["recovery"].update(kind="diagnosis", pre_recovery_authorization={"card_version": "1", "authorization_message": "请修复原始故障", "authorization_basis": "明确请求"}, diagnosis_authorization={"card_version": "2", "authorization_message": state["authorization_card"]["authorization_message"], "authorization_basis": state["authorization_card"]["authorization_basis"]}, new_evidence="新追踪确认根因接缝", diagnosis_stage="4", previous_failure_ids=["failure-1", "failure-2", "failure-3"])
        expect_case("natural-language v5 recovery diagnosis preserves history", state, 0, "PROTOCOL_RESULT=PASS")
        state["recovery"]["previous_failure_ids"] = []
        expect_case("new context cannot clear failed hypothesis history", state, 1, "RECOVERY_FAILURE_HISTORY_MISMATCH")
        state["recovery"]["previous_failure_ids"] = ["failure-1", "failure-2", "failure-3"]
        state["lifecycle"] = "recovery-repair"
        state["authorization_card"].update(version="3", authorization_message="同意使用新假设修复准确原始故障", authorization_basis="独立的恢复修复授权")
        state["scope_control"]["authorization_card_version"] = "3"
        repair = {"action": "recovery-repair", "target": "original-bug", "impact": "修改已定位的生产行为", "rollback": "保留失败证据并撤回本次独立改动"}
        state["authorization_context"]["granted_actions"].append(repair)
        state["authorization_context"]["planned_actions"].append(repair.copy())
        state["recovery"].update(kind="repair", diagnosis_stage="completed", diagnosis_conclusion="根因证据已确认", repair_stable_signal="python3 reproduce.py", repair_hypothesis="new hypothesis", repair_authorization={"card_version": "3", "authorization_message": state["authorization_card"]["authorization_message"], "authorization_basis": state["authorization_card"]["authorization_basis"]})
        expect_case("separately authorized recovery repair accepts natural consent", state, 0, "PROTOCOL_RESULT=PASS")
        state["recovery"]["repair_hypothesis"] = "hypothesis 2"
        expect_case("new agent cannot reuse disproved original hypothesis", state, 1, "RECOVERY_REPAIR_HYPOTHESIS_REUSED")

        if failures:
            raise AssertionError("V5_AUTHORIZATION_SCENARIOS_FAILED\n" + "\n".join(failures))


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
        v3_closeable = json.loads((FIXTURES / "valid.json").read_text(encoding="utf-8"))
        v3_closeable["candidate"].update(state="可收口", closeout_state="建议收口")
        legacy_path.write_text(json.dumps(v3_closeable, ensure_ascii=False), encoding="utf-8")
        check("PROTOCOL_RESULT=PASS" in verify(legacy_path, "--structure-only"), "v3 keeps closeout checks for closed candidates only")
    check(
        "PROTOCOL_RESULT=PASS" in verify(FIXTURES / "v4-frozen-scope-valid.json", "--structure-only"),
        "v4 frozen scope accepts an authorization-bound scope without findings",
    )
    with tempfile.TemporaryDirectory() as directory:
        v4_path = Path(directory) / "v4.json"

        def verify_v4(state: dict, *, expected: int = 0) -> str:
            v4_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            return verify(v4_path, "--structure-only", expected=expected)

        state = v4_state()
        state["scope_control"]["status"] = "draft"
        check("SCOPE_CONTROL_STATUS_INVALID" in verify_v4(state, expected=1), "v4 freezes scope before implementation")

        state = v4_state()
        state.pop("scope_control")
        check("STATE_FIELDS_INVALID" in verify_v4(state, expected=1), "v4 requires frozen scope control")

        state = v4_state()
        state.pop("finding_records")
        check("STATE_FIELDS_INVALID" in verify_v4(state, expected=1), "v4 requires finding records")

        state = v4_state()
        state["scope_control"]["authorization_card_version"] = "2"
        check("SCOPE_CONTROL_CARD_VERSION_MISMATCH" in verify_v4(state, expected=1), "v4 binds scope to authorization card")

        state = v4_state()
        state["delivery_evidence"]["target_check"].pop("baseline_status")
        check("DELIVERY_TARGET_CHECK_FIELDS_INVALID" in verify_v4(state, expected=1), "v4 records a target baseline")

        state = v4_state()
        state["finding_records"] = [{"id": "blocker", "summary": "目标失败", "classification": "current-blocker", "causal_relation": "historical-debt", "causal_evidence": "目标命令失败", "action": "repair-current", "status": "open"}]
        check("CURRENT_BLOCKER_CAUSAL_RELATION_INVALID" in verify_v4(state, expected=1), "current blocker needs causal relation")

        state = v4_state()
        state["finding_records"] = [{"id": "blocker", "summary": "目标失败", "classification": "current-blocker", "causal_relation": "target-required", "causal_evidence": "", "action": "repair-current", "status": "open"}]
        check("FINDING_CAUSAL_EVIDENCE_MUST_BE_NONEMPTY_STRING" in verify_v4(state, expected=1), "current blocker needs causal evidence")

        state = v4_state()
        state["finding_records"] = [{"id": "debt", "summary": "旧债务", "classification": "deferred", "causal_relation": "historical-debt", "causal_evidence": "不影响目标", "action": "repair-current", "status": "open"}]
        check("DEFERRED_ACTION_INVALID" in verify_v4(state, expected=1), "deferred finding cannot repair current candidate")

        state = v4_state()
        state["finding_records"] = [{"id": "new-goal", "summary": "新增目标", "classification": "scope-change", "causal_relation": "new-request", "causal_evidence": "不属于当前目标", "action": "stop-for-decision", "status": "open"}]
        check("OPEN_SCOPE_CHANGE_REQUIRES_BLOCKED_CANDIDATE" in verify_v4(state, expected=1), "open scope change blocks instead of expanding")
        state["candidate"].update(state="阻塞", closeout_state="阻塞")
        check("PROTOCOL_RESULT=PASS" in verify_v4(state), "blocked scope change remains record-only")
        state["finding_records"][0]["action"] = "create-task"
        check("SCOPE_CHANGE_ACTION_INVALID" in verify_v4(state, expected=1), "scope changes cannot create tasks")

        state = v4_state()
        state["finding_records"] = [{"id": "blocker", "summary": "目标失败", "classification": "current-blocker", "causal_relation": "target-required", "causal_evidence": "目标命令失败", "action": "repair-current", "status": "open"}]
        state["write_scope"]["discovered_paths"] = [{"path": "shared", "reason": "共享入口", "business_goal": "验证协议", "discovered_at": "2026-09-03T00:00:00Z", "authorization_card_version": "1", "source_kind": "current-blocker", "source_id": "debt", "causal_evidence": "失败由共享入口造成"}]
        check("DISCOVERED_PATH_CURRENT_BLOCKER_INVALID" in verify_v4(state, expected=1), "paths can only cite current blockers")

        state = v4_state()
        state["write_scope"]["discovered_paths"] = [{"path": "shared", "reason": "共享入口", "business_goal": "验证协议", "discovered_at": "2026-09-03T00:00:00Z"}]
        check("DISCOVERED_PATH_FIELDS_INVALID" in verify_v4(state, expected=1), "v4 paths need causal metadata")

        state = v4_state()
        state["finding_records"] = [{"id": "debt", "summary": "旧债务", "classification": "deferred", "causal_relation": "historical-debt", "causal_evidence": "不影响目标", "action": "record-only", "status": "open"}]
        state["write_scope"]["discovered_paths"] = [{"path": "shared", "reason": "共享入口", "business_goal": "验证协议", "discovered_at": "2026-09-03T00:00:00Z", "authorization_card_version": "1", "source_kind": "current-blocker", "source_id": "debt", "causal_evidence": "失败由共享入口造成"}]
        check("DISCOVERED_PATH_CURRENT_BLOCKER_INVALID" in verify_v4(state, expected=1), "deferred finding cannot expand paths")

        state = v4_state()
        state["finding_records"] = [{"id": "debt", "summary": "旧债务", "classification": "deferred", "causal_relation": "historical-debt", "causal_evidence": "不影响目标", "action": "record-only", "status": "open"}]
        state["candidate"].update(state="可收口", closeout_state="建议收口")
        check("DELIVERY_TARGET_NOT_PASSED" in verify_v4(state, expected=1), "pending fixed checks prevent v4 closeout")
        for check_name in ("target_check", "adjacent_regression", "real_environment"):
            state["delivery_evidence"][check_name]["status"] = "passed"
            state["delivery_evidence"][check_name]["evidence"] = "固定检查通过"
        check("PROTOCOL_RESULT=PASS" in verify_v4(state), "open deferred finding permits closeout")
        state["finding_records"].append({"id": "blocker", "summary": "目标失败", "classification": "current-blocker", "causal_relation": "target-required", "causal_evidence": "目标命令失败", "action": "repair-current", "status": "open"})
        check("OPEN_BLOCKER_PREVENTS_CLOSEOUT" in verify_v4(state, expected=1), "open current blocker prevents closeout")
        state["finding_records"][-1]["status"] = "resolved"
        check("PROTOCOL_RESULT=PASS" in verify_v4(state), "resolved current blocker permits closeout")

        state = v4_state()
        state["write_scope"]["discovered_paths"] = [{"path": "shared", "reason": "目标权威入口", "business_goal": "验证协议", "discovered_at": "2026-09-03T00:00:00Z", "authorization_card_version": "1", "source_kind": "target-authority", "source_id": "scope-control", "causal_evidence": "目标行为由该入口定义"}]
        check("PROTOCOL_RESULT=PASS" in verify_v4(state), "scope control can authorize target authority path")
        state["write_scope"]["discovered_paths"][0]["source_id"] = "arbitrary-target"
        check("DISCOVERED_PATH_TARGET_SOURCE_INVALID" in verify_v4(state, expected=1), "target authority needs fixed source id")

        state = v4_state()
        state["write_scope"]["discovered_paths"] = [{"path": "shared", "reason": "验收接缝", "business_goal": "验证协议", "discovered_at": "2026-09-03T00:00:00Z", "authorization_card_version": "1", "source_kind": "acceptance-check", "source_id": "target_check", "causal_evidence": "固定目标检查需要该路径"}]
        check("PROTOCOL_RESULT=PASS" in verify_v4(state), "fixed check can authorize acceptance path")
        state["write_scope"]["discovered_paths"][0]["source_id"] = "arbitrary-check"
        check("DISCOVERED_PATH_ACCEPTANCE_SOURCE_INVALID" in verify_v4(state, expected=1), "acceptance path needs fixed check id")

        state = v4_state()
        state["finding_records"] = [{"id": "blocker", "summary": "目标失败", "classification": "current-blocker", "causal_relation": "target-required", "causal_evidence": "目标命令失败", "action": "repair-current", "status": "open"}]
        state["write_scope"]["discovered_paths"] = [{"path": "shared", "reason": "当前阻塞", "business_goal": "验证协议", "discovered_at": "2026-09-03T00:00:00Z", "authorization_card_version": "1", "source_kind": "current-blocker", "source_id": "blocker", "causal_evidence": "失败由共享入口造成"}]
        check("PROTOCOL_RESULT=PASS" in verify_v4(state), "current blocker can authorize path")
    fence = chr(96) * 3
    protocol_document = (ROOT / "references" / "executable-protocol.md").read_text(encoding="utf-8")
    document_example = re.search(rf"{fence}json\n(.*?)\n{fence}", protocol_document, re.DOTALL)
    check(document_example is not None, "document state example")
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
        state["authorization_card"].update(
            execution_endpoint="已合并并清理",
            automatic_actions=["复验", "执行内部收口审计"],
        )
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("PROTOCOL_RESULT=PASS" in verify(state_path, *checks(repo)), "internal closeout audit pass")
        state["authorization_card"]["automatic_actions"] = ["复验"]
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("CLOSEOUT_AUDIT_ACTION_MISSING" in verify(state_path, *checks(repo), expected=1), "closeout audit required")
        state["authorization_card"]["automatic_actions"] = ["复验", "调用 `shoukou` 收口审计"]
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        check("CLOSEOUT_AUDIT_ACTION_MISSING" in verify(state_path, *checks(repo), expected=1), "legacy closeout audit rejected")
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
            shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns("__pycache__", ".git"))
            shutil.copytree(ROOT, runtime, ignore=shutil.ignore_patterns("__pycache__", ".git"))
            shutil.copytree(ROOT / "templates/agents", agents)

            def setup_result(*arguments: str) -> str:
                return run("bash", str(source / "scripts/verify-setup.sh"), *arguments, expected=1)

            template = source / "templates/agents/team-developer.toml"
            original = template.read_text(encoding="utf-8")
            template.write_text(original.replace('model = "gpt-6-astra"', 'model = "gpt-5.6-terra"'), encoding="utf-8")
            check("AGENT_CONFIG_MISMATCH" in setup_result("--source-only"), "setup catches stale model default")
            template.write_text(original, encoding="utf-8")
            reviewer = source / "templates/agents/team-reviewer.toml"
            original = reviewer.read_text(encoding="utf-8")
            reviewer.write_text(original.replace('sandbox_mode = "read-only"', 'sandbox_mode = "workspace-write"'), encoding="utf-8")
            check("AGENT_CONFIG_MISMATCH" in setup_result("--source-only"), "setup catches widened reviewer permission")
            reviewer.write_text(original, encoding="utf-8")
            installed = agents / "team-developer.toml"
            installed.write_text(installed.read_text(encoding="utf-8") + "\n# stale installed instructions\n", encoding="utf-8")
            check("AGENT_COPY_DIFFERS" in setup_result(str(agents), str(runtime)), "same model does not hide stale installed instructions")
            skill = source / "SKILL.md"
            skill.write_text(skill.read_text(encoding="utf-8") + "\n[missing reference](references/not-present.md)\n", encoding="utf-8")
            check("REFERENCE_MISSING" in setup_result("--source-only"), "setup checks local reference resolution")
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
    v5_authorization_scenarios()
    print("PROTOCOL_SCENARIOS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

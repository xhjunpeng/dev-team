#!/usr/bin/env python3
"""Validate the local, auditable part of a dev-team dispatch state record."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


CARD_FIELDS = (
    "execution_mode", "version", "business_goal", "candidate_and_worktree",
    "execution_endpoint", "one_time_actions", "automatic_actions",
    "repair_and_reverify", "stop_conditions", "will_not_do", "progress_mode",
    "authorization_status", "authorization_message", "authorization_basis",
)
CARD_ENUMS = {
    "execution_mode": {"普通", "连续执行"},
    "progress_mode": {"只汇报", "需要确认"},
    "authorization_status": {"未获得", "已获得"},
}
CANDIDATE_STATES = {"待判断", "开发中", "验证中", "待验收", "阻塞", "可收口", "已收口"}
CLOSEOUT_STATES = {"继续开发", "建议收口", "阻塞"}
ISOLATION_STATES = {"复用当前候选", "主分支直接写", "当前目录候选分支", "独立分支与 worktree", "先收口或明确保留"}
LIFECYCLES = {"dispatch", "active", "recovery-diagnosis", "recovery-repair", "completed"}
TASK_KINDS = {"feature", "bug", "refactor", "visual", "documentation", "operations"}
BEFORE_STATUSES = {"pending", "red", "captured", "baseline-green", "not-applicable"}
CHECK_STATUSES = {"pending", "passed", "failed", "not-applicable"}
TASK_ID = re.compile(r"[a-z0-9][a-z0-9-]{2,63}\Z")
GIT_SHA = re.compile(r"[0-9a-f]{40}\Z")
CURRENT_PROTOCOL_VERSION = 3
SUPPORTED_PROTOCOL_VERSIONS = {2, CURRENT_PROTOCOL_VERSION}
IGNORED_UNTRACKED_POLICY = "excluded"


def fail(message: str) -> None:
    raise ValueError(message)


def require_object(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        fail(f"{label}_MUST_BE_OBJECT")
    return value


def require_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(f"{label}_MUST_BE_NONEMPTY_STRING")
    return value


def require_list(value: object, label: str, allow_empty: bool = False) -> list:
    if not isinstance(value, list) or (not allow_empty and not value):
        fail(f"{label}_MUST_BE_{'LIST' if allow_empty else 'NONEMPTY_LIST'}")
    return value


def validate_card(card: dict) -> None:
    if set(card) != set(CARD_FIELDS):
        fail("AUTHORIZATION_CARD_FIELDS_INVALID")
    list_fields = {"one_time_actions", "automatic_actions", "repair_and_reverify", "stop_conditions", "will_not_do"}
    for field in CARD_FIELDS:
        if field in list_fields:
            for item in require_list(card[field], f"CARD_{field.upper()}"):
                require_string(item, f"CARD_{field.upper()}_ITEM")
        else:
            require_string(card[field], f"CARD_{field.upper()}")
    for field, allowed in CARD_ENUMS.items():
        if card[field] not in allowed:
            fail(f"CARD_{field.upper()}_INVALID")
    card_version(card["version"], "AUTHORIZATION_CARD_VERSION")
    endpoint = card["execution_endpoint"]
    if endpoint == "自定义":
        fail("CARD_CUSTOM_ENDPOINT_EMPTY")
    if endpoint not in {"本地候选完成", "PR 可评审", "已合并并清理"}:
        if not endpoint.startswith("自定义：") or not endpoint.removeprefix("自定义：").strip():
            fail("CARD_EXECUTION_ENDPOINT_INVALID")
    if card["authorization_status"] != "已获得":
        fail("AUTHORIZATION_REQUIRED")
    if card["authorization_message"] != "1" or card["authorization_basis"] != "最新完整十四项卡的精确1":
        fail("AUTHORIZATION_EVIDENCE_INVALID")
    if card["execution_endpoint"] == "已合并并清理":
        if "调用 `shoukou` 收口审计" not in card["one_time_actions"] + card["automatic_actions"]:
            fail("CLOSEOUT_AUDIT_ACTION_MISSING")


def resolve_primary_branch(repo: Path) -> str | None:
    result = subprocess.run(("git", "-C", str(repo), "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"), text=True, capture_output=True)
    if result.returncode == 0:
        return result.stdout.strip().removeprefix("refs/remotes/origin/")
    configured = subprocess.run(("git", "-C", str(repo), "config", "--get", "dev-team.primaryBranch"), text=True, capture_output=True)
    if configured.returncode == 0 and configured.stdout.strip():
        return configured.stdout.strip()
    return None


def validate_candidate(candidate: dict, card: dict, state_primary: str, current_branch: str | None, resolved_primary: str | None) -> None:
    required = {"branch", "worktree", "isolation", "state", "closeout_state", "blocks_new_business_goal"}
    if set(candidate) != required:
        fail("CANDIDATE_FIELDS_INVALID")
    branch = require_string(candidate["branch"], "CANDIDATE_BRANCH")
    worktree = require_string(candidate["worktree"], "CANDIDATE_WORKTREE")
    if not Path(worktree).is_absolute():
        fail("CANDIDATE_WORKTREE_MUST_BE_ABSOLUTE")
    if require_string(candidate["isolation"], "CANDIDATE_ISOLATION") not in ISOLATION_STATES:
        fail("CANDIDATE_ISOLATION_INVALID")
    if candidate["state"] not in CANDIDATE_STATES:
        fail("CANDIDATE_STATE_INVALID")
    if candidate["closeout_state"] not in CLOSEOUT_STATES:
        fail("CANDIDATE_CLOSEOUT_STATE_INVALID")
    if not isinstance(candidate["blocks_new_business_goal"], bool):
        fail("CANDIDATE_BLOCKS_NEW_BUSINESS_GOAL_INVALID")
    if card["candidate_and_worktree"] != f"{branch}；{worktree}":
        fail("CARD_CANDIDATE_MISMATCH")
    if current_branch is None:
        return
    if resolved_primary is not None and state_primary != resolved_primary:
        fail("STATE_PRIMARY_BRANCH_MISMATCH")
    if resolved_primary is not None and current_branch == resolved_primary:
        if candidate["isolation"] != "主分支直接写":
            fail("MAIN_BRANCH_REQUIRES_DIRECT_ISOLATION")
        if branch != resolved_primary:
            fail("DIRECT_MAIN_WRITE_REQUIRES_PRIMARY_BRANCH")
    elif candidate["isolation"] == "主分支直接写":
        fail("DIRECT_MAIN_WRITE_REQUIRES_PRIMARY_BRANCH")


def validate_timestamp(value: object, label: str) -> None:
    try:
        datetime.fromisoformat(require_string(value, label).replace("Z", "+00:00"))
    except ValueError:
        fail(f"{label}_INVALID")


def validate_migration(value: object, protocol_version: int) -> None:
    """Require auditable metadata when a state was converted from an older protocol."""
    if value is None:
        return
    migration = require_object(value, "MIGRATION")
    if set(migration) != {"from_protocol_version", "migrated_at"}:
        fail("MIGRATION_FIELDS_INVALID")
    source_version = migration["from_protocol_version"]
    if not isinstance(source_version, int) or source_version < 1 or source_version >= protocol_version:
        fail("MIGRATION_SOURCE_VERSION_INVALID")
    validate_timestamp(migration["migrated_at"], "MIGRATION_TIME")


def migrate_v1_state(state: dict) -> dict:
    """Convert the former v1 schema without claiming that it was already v2."""
    if state.get("protocol_version") != 1:
        fail("V1_MIGRATION_REQUIRES_PROTOCOL_VERSION_1")
    legacy = dict(state)
    legacy.pop("ignored_untracked_at_start", None)
    recovery = legacy.get("recovery")
    if isinstance(recovery, dict):
        normalized_recovery = empty_recovery()
        normalized_recovery.update(recovery)
        legacy["recovery"] = normalized_recovery
    # A v1 record can be normalized to v2 without inventing delivery evidence.
    # Moving to v3 requires facts from a real run and is therefore explicit.
    legacy["protocol_version"] = 2
    legacy["migration"] = {
        "from_protocol_version": 1,
        "migrated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    legacy["ignored_untracked_policy"] = IGNORED_UNTRACKED_POLICY
    return legacy


def empty_recovery() -> dict:
    return {"kind": "none", "pre_recovery_authorization": None, "diagnosis_authorization": None, "new_evidence": None, "diagnosis_stage": None, "diagnosis_conclusion": None, "repair_stable_signal": None, "repair_hypothesis": None, "repair_authorization": None, "previous_failure_ids": []}


def card_version(value: object, label: str) -> int:
    text = require_string(value, label)
    if not text.isdecimal() or int(text) < 1:
        fail(f"{label}_INVALID")
    return int(text)


def validate_failures(identity: object, failures: list, failure_count: object, recovery: dict, lifecycle: str, card: dict) -> None:
    if not isinstance(failure_count, int) or failure_count < 0:
        fail("FAILURE_COUNT_INVALID")
    require_list(failures, "FAILURE_RECORDS", allow_empty=True)
    required_recovery = {"kind", "pre_recovery_authorization", "diagnosis_authorization", "new_evidence", "diagnosis_stage", "diagnosis_conclusion", "repair_stable_signal", "repair_hypothesis", "repair_authorization", "previous_failure_ids"}
    if set(recovery) != required_recovery:
        fail("RECOVERY_FIELDS_INVALID")
    if recovery["kind"] not in {"none", "diagnosis", "repair"}:
        fail("RECOVERY_KIND_INVALID")
    if identity is None:
        if lifecycle in {"recovery-diagnosis", "recovery-repair"}:
            fail("RECOVERY_LIFECYCLE_WITHOUT_THREE_FAILURES")
        if failure_count != 0 or failures != [] or recovery != empty_recovery():
            fail("NON_FAULT_TASK_FAILURE_DATA_INVALID")
        return
    identity = require_object(identity, "FAILURE_IDENTITY")
    if set(identity) != {"id", "symptom", "stable_signal"}:
        fail("FAILURE_IDENTITY_FIELDS_INVALID")
    for field in identity:
        require_string(identity[field], f"FAILURE_IDENTITY_{field.upper()}")
    if failure_count != len(failures):
        fail("FAILURE_COUNT_MISMATCH")
    ids: list[str] = []
    prior_hypotheses: list[str] = []
    for record in failures:
        record = require_object(record, "FAILURE_RECORD")
        if set(record) != {"id", "outcome", "hypothesis", "stable_signal", "observed_at"}:
            fail("FAILURE_RECORD_FIELDS_INVALID")
        identifier = require_string(record["id"], "FAILURE_RECORD_ID")
        ids.append(identifier)
        if record["outcome"] != "failed":
            fail("FAILURE_RECORD_OUTCOME_INVALID")
        prior_hypotheses.append(require_string(record["hypothesis"], "FAILURE_RECORD_HYPOTHESIS"))
        if record["stable_signal"] != identity["stable_signal"]:
            fail("FAILURE_RECORD_SIGNAL_MISMATCH")
        validate_timestamp(record["observed_at"], "FAILURE_RECORD_OBSERVED_AT")
    if len(ids) != len(set(ids)):
        fail("FAILURE_RECORD_ID_DUPLICATE")
    if len(prior_hypotheses) != len(set(prior_hypotheses)):
        fail("FAILURE_RECORD_HYPOTHESIS_DUPLICATE")
    if failure_count < 3:
        if lifecycle in {"recovery-diagnosis", "recovery-repair"}:
            fail("RECOVERY_LIFECYCLE_WITHOUT_THREE_FAILURES")
        if recovery != empty_recovery():
            fail("RECOVERY_NOT_ALLOWED_BEFORE_THREE_FAILURES")
        return
    if lifecycle not in {"recovery-diagnosis", "recovery-repair"} or recovery["kind"] not in {"diagnosis", "repair"}:
        fail("THREE_FAILURES_REQUIRE_RECOVERY_DISPATCH")
    if recovery["previous_failure_ids"] != ids:
        fail("RECOVERY_FAILURE_HISTORY_MISMATCH")
    pre_authorization = require_object(recovery["pre_recovery_authorization"], "PRE_RECOVERY_AUTHORIZATION")
    if set(pre_authorization) != {"card_version", "authorization_message", "authorization_basis"}:
        fail("PRE_RECOVERY_AUTHORIZATION_FIELDS_INVALID")
    pre_version = card_version(pre_authorization["card_version"], "PRE_RECOVERY_CARD_VERSION")
    if pre_authorization["authorization_message"] != "1" or pre_authorization["authorization_basis"] != "最新完整十四项卡的精确1":
        fail("PRE_RECOVERY_AUTHORIZATION_INVALID")
    diagnosis_authorization = require_object(recovery["diagnosis_authorization"], "DIAGNOSIS_AUTHORIZATION")
    if set(diagnosis_authorization) != {"card_version", "authorization_message", "authorization_basis"}:
        fail("DIAGNOSIS_AUTHORIZATION_FIELDS_INVALID")
    diagnosis_version = card_version(diagnosis_authorization["card_version"], "DIAGNOSIS_CARD_VERSION")
    if diagnosis_authorization["authorization_message"] != "1" or diagnosis_authorization["authorization_basis"] != "最新完整十四项卡的精确1" or diagnosis_version <= pre_version:
        fail("DIAGNOSIS_AUTHORIZATION_INVALID")
    if lifecycle == "recovery-diagnosis" and recovery["kind"] == "diagnosis":
        require_string(recovery["new_evidence"], "RECOVERY_NEW_EVIDENCE")
        if recovery["diagnosis_stage"] not in {"1", "2", "3", "4"}:
            fail("RECOVERY_DIAGNOSIS_STAGE_INVALID")
        if any(recovery[field] is not None for field in ("diagnosis_conclusion", "repair_stable_signal", "repair_hypothesis", "repair_authorization")):
            fail("RECOVERY_DIAGNOSIS_MUST_NOT_INCLUDE_REPAIR")
        return
    if lifecycle != "recovery-repair" or recovery["kind"] != "repair":
        fail("RECOVERY_REPAIR_STATE_INVALID")
    if card_version(card["version"], "AUTHORIZATION_CARD_VERSION") <= diagnosis_version:
        fail("RECOVERY_REPAIR_REQUIRES_REPLACEMENT_CARD")
    require_string(recovery["new_evidence"], "RECOVERY_NEW_EVIDENCE")
    if recovery["diagnosis_stage"] != "completed":
        fail("RECOVERY_REPAIR_DIAGNOSIS_INCOMPLETE")
    require_string(recovery["diagnosis_conclusion"], "RECOVERY_DIAGNOSIS_CONCLUSION")
    if recovery["repair_stable_signal"] != identity["stable_signal"]:
        fail("RECOVERY_REPAIR_SIGNAL_MISMATCH")
    if require_string(recovery["repair_hypothesis"], "RECOVERY_REPAIR_HYPOTHESIS") in prior_hypotheses:
        fail("RECOVERY_REPAIR_HYPOTHESIS_REUSED")
    authorization = require_object(recovery["repair_authorization"], "RECOVERY_REPAIR_AUTHORIZATION")
    if set(authorization) != {"card_version", "authorization_message", "authorization_basis"}:
        fail("RECOVERY_REPAIR_AUTHORIZATION_FIELDS_INVALID")
    require_string(authorization["card_version"], "RECOVERY_REPAIR_CARD_VERSION")
    if authorization["card_version"] != card["version"] or authorization["authorization_message"] != card["authorization_message"] or authorization["authorization_basis"] != card["authorization_basis"]:
        fail("RECOVERY_REPAIR_AUTHORIZATION_STALE")


def validate_relative_path(path: object) -> None:
    if not isinstance(path, str) or not path or Path(path).is_absolute() or ".." in Path(path).parts:
        fail("ALLOWED_PATH_INVALID")


def git_paths(command: tuple[str, ...]) -> set[str]:
    return {entry.decode("utf-8") for entry in subprocess.check_output(command).split(b"\0") if entry}


def changed_paths(repo: Path, baseline: str) -> set[str]:
    result: set[str] = set()
    for command in (
        ("diff", "--no-renames", "--name-only", "-z", baseline),
        ("ls-files", "-z", "--others", "--exclude-standard"),
    ):
        result.update(git_paths(("git", "-C", str(repo), *command)))
    return result


def current_changes(repo: Path, state_path: Path, baseline: str) -> set[str]:
    try:
        state_relative = state_path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        state_relative = None
    return {path for path in changed_paths(repo, baseline) if path != state_relative}


def validate_scope(scope: dict, business_goal: str, repo: Path, state_path: Path, baseline: str, check_diff: bool) -> list[str]:
    if set(scope) != {"initial_allowed_paths", "discovered_paths"}:
        fail("WRITE_SCOPE_FIELDS_INVALID")
    initial = require_list(scope["initial_allowed_paths"], "INITIAL_ALLOWED_PATHS")
    discovered = require_list(scope["discovered_paths"], "DISCOVERED_PATHS", allow_empty=True)
    allowed = list(initial)
    for path in initial:
        validate_relative_path(path)
    for record in discovered:
        record = require_object(record, "DISCOVERED_PATH")
        if set(record) != {"path", "reason", "business_goal", "discovered_at"}:
            fail("DISCOVERED_PATH_FIELDS_INVALID")
        path = require_string(record["path"], "DISCOVERED_PATH")
        validate_relative_path(path)
        require_string(record["reason"], "DISCOVERED_PATH_REASON")
        if require_string(record["business_goal"], "DISCOVERED_PATH_BUSINESS_GOAL") != business_goal:
            fail("DISCOVERED_PATH_BUSINESS_GOAL_MISMATCH")
        validate_timestamp(record["discovered_at"], "DISCOVERED_PATH_TIME")
        allowed.append(path)
    if len(allowed) != len(set(allowed)):
        fail("WRITE_SCOPE_PATH_DUPLICATE")
    if check_diff:
        outside = sorted(path for path in current_changes(repo, state_path, baseline) if not any(path == allowed_path or path.startswith(f"{allowed_path}/") for allowed_path in allowed))
        if outside:
            fail(f"DIFF_OUTSIDE_WRITE_SCOPE: {', '.join(outside)}")
    return allowed


def validate_runtime(candidate: dict, repo: Path, check_worktree: bool) -> tuple[str | None, str | None]:
    if not check_worktree:
        return None, None
    branch = subprocess.check_output(("git", "-C", str(repo), "branch", "--show-current"), text=True).strip()
    if branch != candidate["branch"]:
        fail("CURRENT_BRANCH_MISMATCH")
    if Path(candidate["worktree"]).resolve() != repo.resolve():
        fail("CURRENT_WORKTREE_MISMATCH")
    return branch, resolve_primary_branch(repo)


def validate_location(state: dict, state_path: Path, state_dir: Path, check_location: bool) -> None:
    if not check_location:
        return
    expected = (state_dir / f"{state['task_id']}.json").resolve()
    if state_path.resolve() != expected:
        fail("STATE_LOCATION_MISMATCH")


def validate_closeout(candidate: dict) -> None:
    expected = candidate["state"] != "已收口"
    if candidate["blocks_new_business_goal"] != expected:
        fail("BLOCKS_NEW_BUSINESS_GOAL_MISMATCH")


def validate_check(value: object, label: str, *, target: bool = False) -> str:
    check = require_object(value, label)
    if set(check) != {"status", "evidence"}:
        fail(f"{label}_FIELDS_INVALID")
    status = check["status"]
    if status not in CHECK_STATUSES or (target and status == "not-applicable"):
        fail(f"{label}_STATUS_INVALID")
    evidence = check["evidence"]
    if status == "pending":
        if evidence is not None:
            fail(f"{label}_PENDING_EVIDENCE_INVALID")
    else:
        require_string(evidence, f"{label}_EVIDENCE")
    return status


def validate_delivery_evidence(
    evidence: object,
    identity: object,
    candidate: dict,
    repo: Path,
    state_path: Path,
    baseline: str,
    allowed_paths: list[str],
    check_diff: bool,
) -> None:
    evidence = require_object(evidence, "DELIVERY_EVIDENCE")
    required = {
        "task_kind", "user_visible_outcome", "target_entrypoint", "feedback_signal",
        "before_status", "before_evidence", "feedback_scope", "target_check", "adjacent_regression",
        "real_environment", "unverified_boundaries",
    }
    if set(evidence) != required:
        fail("DELIVERY_EVIDENCE_FIELDS_INVALID")
    task_kind = evidence["task_kind"]
    if task_kind not in TASK_KINDS:
        fail("DELIVERY_TASK_KIND_INVALID")
    require_string(evidence["user_visible_outcome"], "DELIVERY_USER_VISIBLE_OUTCOME")
    require_string(evidence["target_entrypoint"], "DELIVERY_TARGET_ENTRYPOINT")
    signal = require_string(evidence["feedback_signal"], "DELIVERY_FEEDBACK_SIGNAL")
    before_status = evidence["before_status"]
    if before_status not in BEFORE_STATUSES:
        fail("DELIVERY_BEFORE_STATUS_INVALID")
    before_evidence = evidence["before_evidence"]
    if before_status == "pending":
        if before_evidence is not None:
            fail("DELIVERY_BEFORE_PENDING_EVIDENCE_INVALID")
    else:
        require_string(before_evidence, "DELIVERY_BEFORE_EVIDENCE")
    feedback_ready = candidate["state"] != "待判断"
    if task_kind in {"feature", "bug"}:
        if before_status not in {"pending", "red"} or (feedback_ready and before_status != "red"):
            fail("DELIVERY_RED_REQUIRED")
    if task_kind == "visual":
        if before_status not in {"pending", "captured"} or (feedback_ready and before_status != "captured"):
            fail("DELIVERY_VISUAL_CAPTURE_REQUIRED")
    if task_kind == "bug":
        if not isinstance(identity, dict) or signal != identity.get("stable_signal"):
            fail("DELIVERY_BUG_SIGNAL_MISMATCH")
    feedback_scope = require_list(evidence["feedback_scope"], "DELIVERY_FEEDBACK_SCOPE")
    for path in feedback_scope:
        validate_relative_path(path)
        if not any(path == allowed or path.startswith(f"{allowed}/") for allowed in allowed_paths):
            fail("DELIVERY_FEEDBACK_SCOPE_OUTSIDE_WRITE_SCOPE")
    if len(feedback_scope) != len(set(feedback_scope)):
        fail("DELIVERY_FEEDBACK_SCOPE_DUPLICATE")
    target_status = validate_check(evidence["target_check"], "DELIVERY_TARGET_CHECK", target=True)
    regression_status = validate_check(evidence["adjacent_regression"], "DELIVERY_ADJACENT_REGRESSION")
    environment_status = validate_check(evidence["real_environment"], "DELIVERY_REAL_ENVIRONMENT")
    boundaries = require_list(evidence["unverified_boundaries"], "DELIVERY_UNVERIFIED_BOUNDARIES", allow_empty=True)
    for boundary in boundaries:
        require_string(boundary, "DELIVERY_UNVERIFIED_BOUNDARY")
    if before_status == "pending" and any(status != "pending" for status in (target_status, regression_status, environment_status)):
        fail("DELIVERY_CHECKS_BEFORE_FEEDBACK")
    if candidate["state"] == "待判断" and check_diff:
        outside_feedback = sorted(
            path for path in current_changes(repo, state_path, baseline)
            if not any(path == allowed or path.startswith(f"{allowed}/") for allowed in feedback_scope)
        )
        if outside_feedback:
            fail(f"DIFF_OUTSIDE_FEEDBACK_SCOPE: {', '.join(outside_feedback)}")
    if candidate["state"] == "已收口":
        if target_status != "passed":
            fail("DELIVERY_TARGET_NOT_PASSED")
        if regression_status not in {"passed", "not-applicable"}:
            fail("DELIVERY_REGRESSION_INCOMPLETE")
        if environment_status not in {"passed", "not-applicable"}:
            fail("DELIVERY_REAL_ENVIRONMENT_INCOMPLETE")


def validate_repo_root(repo: Path) -> None:
    result = subprocess.run(("git", "-C", str(repo), "rev-parse", "--show-toplevel"), text=True, capture_output=True)
    if result.returncode != 0 or Path(result.stdout.strip()).resolve() != repo.resolve():
        fail("REPO_NOT_GIT_ROOT")


def validate_submodules(repo: Path) -> None:
    entries = subprocess.check_output(("git", "-C", str(repo), "ls-files", "--stage", "-z")).split(b"\0")
    for entry in entries:
        if entry.startswith(b"160000 "):
            path = entry.partition(b"\t")[2].decode("utf-8")
            fail(f"GITLINK_NOT_SUPPORTED: {path}")


def validate_index(repo: Path) -> None:
    sparse_checkout = subprocess.run(
        ("git", "-C", str(repo), "config", "--bool", "core.sparseCheckout"),
        text=True,
        capture_output=True,
    )
    if sparse_checkout.returncode == 0 and sparse_checkout.stdout.strip().lower() == "true":
        fail("SPARSE_CHECKOUT_NOT_SUPPORTED")
    entries = subprocess.check_output(("git", "-C", str(repo), "ls-files", "-v", "-z")).split(b"\0")
    for entry in entries:
        if entry and entry[:1] != b"H":
            path = entry[2:].decode("utf-8")
            fail(f"SPECIAL_INDEX_ENTRY: {path}")


def validate_skill_root(skill_root: Path) -> None:
    if not skill_root.is_absolute() or skill_root.resolve() != Path(__file__).resolve().parents[1]:
        fail("SKILL_ROOT_INVALID")


def validate_baseline(state: dict, repo: Path, check_worktree: bool) -> str:
    baseline = require_string(state["git_baseline"], "GIT_BASELINE")
    if not GIT_SHA.fullmatch(baseline):
        fail("GIT_BASELINE_INVALID")
    if state["ignored_untracked_policy"] != IGNORED_UNTRACKED_POLICY:
        fail("IGNORED_UNTRACKED_POLICY_INVALID")
    if check_worktree:
        ancestor = subprocess.run(("git", "-C", str(repo), "merge-base", "--is-ancestor", baseline, "HEAD"), capture_output=True)
        if ancestor.returncode != 0:
            fail("BASELINE_NOT_CANDIDATE_ANCESTOR")
    return baseline


def validate(state: dict, repo: Path, state_path: Path, state_dir: Path, check_diff: bool, check_worktree: bool, check_location: bool) -> None:
    base_required = {"protocol_version", "migration", "task_id", "lifecycle", "skill_root", "git_baseline", "ignored_untracked_policy", "primary_branch", "authorization_card", "candidate", "failure_identity", "production_failure_count", "failure_records", "recovery", "write_scope"}
    protocol_version = state.get("protocol_version")
    if protocol_version not in SUPPORTED_PROTOCOL_VERSIONS:
        fail("PROTOCOL_VERSION_INVALID")
    required = base_required | ({"delivery_evidence"} if protocol_version == CURRENT_PROTOCOL_VERSION else set())
    if set(state) != required:
        fail("STATE_FIELDS_INVALID")
    validate_migration(state["migration"], protocol_version)
    if not isinstance(state["task_id"], str) or not TASK_ID.fullmatch(state["task_id"]):
        fail("TASK_ID_INVALID")
    if state["lifecycle"] not in LIFECYCLES:
        fail("LIFECYCLE_INVALID")
    require_string(state["skill_root"], "SKILL_ROOT")
    primary = require_string(state["primary_branch"], "PRIMARY_BRANCH")
    card = require_object(state["authorization_card"], "AUTHORIZATION_CARD")
    candidate = require_object(state["candidate"], "CANDIDATE")
    validate_card(card)
    baseline = validate_baseline(state, repo, check_worktree)
    current_branch, resolved_primary = validate_runtime(candidate, repo, check_worktree)
    validate_candidate(candidate, card, primary, current_branch, resolved_primary)
    validate_failures(state["failure_identity"], state["failure_records"], state["production_failure_count"], require_object(state["recovery"], "RECOVERY"), state["lifecycle"], card)
    validate_location(state, state_path, state_dir, check_location)
    validate_closeout(candidate)
    allowed_paths = validate_scope(require_object(state["write_scope"], "WRITE_SCOPE"), card["business_goal"], repo, state_path, baseline, check_diff)
    if protocol_version == CURRENT_PROTOCOL_VERSION:
        validate_delivery_evidence(state["delivery_evidence"], state["failure_identity"], candidate, repo, state_path, baseline, allowed_paths, check_diff)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--skill-root", type=Path)
    parser.add_argument("--structure-only", action="store_true")
    parser.add_argument("--migrate-v1-state", action="store_true")
    args = parser.parse_args()
    try:
        repo = args.repo.resolve()
        if not args.structure_only:
            if not args.state.is_absolute() or args.skill_root is None:
                fail("REALTIME_PATHS_MUST_BE_ABSOLUTE")
            validate_repo_root(repo)
            validate_submodules(repo)
            validate_index(repo)
            validate_skill_root(args.skill_root)
        state_dir = args.state_dir or Path(os.environ.get("DEV_TEAM_STATE_DIR", ".dev-team/state"))
        if not state_dir.is_absolute():
            state_dir = repo / state_dir
        state = json.loads(args.state.read_text(encoding="utf-8"))
        if args.migrate_v1_state:
            state = migrate_v1_state(require_object(state, "STATE"))
            args.state.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if not args.structure_only and Path(require_string(state.get("skill_root"), "SKILL_ROOT")).resolve() != args.skill_root.resolve():
            fail("STATE_SKILL_ROOT_MISMATCH")
        validate(require_object(state, "STATE"), repo, args.state.resolve(), state_dir.resolve(), not args.structure_only, not args.structure_only, not args.structure_only)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError, ValueError) as error:
        print(f"PROTOCOL_INVALID: {error}", file=sys.stderr)
        return 1
    print("PROTOCOL_RESULT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

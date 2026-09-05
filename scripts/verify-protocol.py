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
BASELINE_STATUSES = {"passed", "failed", "not-applicable", "unknown"}
TASK_ID = re.compile(r"[a-z0-9][a-z0-9-]{2,63}\Z")
GIT_SHA = re.compile(r"[0-9a-f]{40}\Z")
CURRENT_PROTOCOL_VERSION = 5
SUPPORTED_PROTOCOL_VERSIONS = {2, 3, 4, 5}
DELIVERY_EVIDENCE_PROTOCOL_VERSIONS = {3, 4, 5}
FROZEN_SCOPE_PROTOCOL_VERSIONS = {4, 5}
IGNORED_UNTRACKED_POLICY = "excluded"
ROLE_MODELS = {
    "developer": ("gpt-6-astra", "high", "workspace-write"),
    "ui-maker": ("gpt-6-astra", "high", "workspace-write"),
    "reviewer": ("gpt-6-astra", "high", "read-only"),
    "explorer": ("gpt-5.6-terra", "high", "read-only"),
}
READ_ACTIONS = {"read", "verify"}
HIGH_RISK_ACTIONS = {
    "merge", "branch-delete", "worktree-delete", "force-push", "deploy",
    "data-migration", "schema-migration", "production-write", "payment",
    "secret-change", "security-change", "recovery-repair",
}
REVIEW_BEFORE_EXECUTION = HIGH_RISK_ACTIONS - {"security-change", "recovery-repair"}
ACTION_KINDS = READ_ACTIONS | HIGH_RISK_ACTIONS | {
    "workspace-write", "branch-create", "worktree-create", "commit", "push",
    "pr-create", "pr-update", "sync-branch", "recovery-diagnosis",
}


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


def validate_card(card: dict, protocol_version: int = 4) -> None:
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
    if protocol_version < 5 and (card["authorization_message"] != "1" or card["authorization_basis"] != "最新完整十四项卡的精确1"):
        fail("AUTHORIZATION_EVIDENCE_INVALID")
    if protocol_version < 5 and card["execution_endpoint"] == "已合并并清理":
        if "执行内部收口审计" not in card["one_time_actions"] + card["automatic_actions"]:
            fail("CLOSEOUT_AUDIT_ACTION_MISSING")


def validate_v5_governance(state: dict) -> None:
    """Check recorded decisions, never infer consent or model identity from prose."""
    assessment = require_object(state["task_assessment"], "TASK_ASSESSMENT")
    if set(assessment) != {"difficulty", "operation_risk"}:
        fail("TASK_ASSESSMENT_FIELDS_INVALID")
    if require_string(assessment["difficulty"], "TASK_DIFFICULTY") not in {"small", "normal", "complex"}:
        fail("TASK_DIFFICULTY_INVALID")
    risk = require_string(assessment["operation_risk"], "OPERATION_RISK")
    if risk not in {"read-only", "reversible", "high-risk"}:
        fail("OPERATION_RISK_INVALID")
    authorization = require_object(state["authorization_context"], "AUTHORIZATION_CONTEXT")
    if set(authorization) != {"source", "intent", "granted_actions", "planned_actions"}:
        fail("AUTHORIZATION_CONTEXT_FIELDS_INVALID")
    if require_string(authorization["source"], "AUTHORIZATION_SOURCE") not in {"explicit-request", "explicit-consent", "shortcut"}:
        fail("AUTHORIZATION_SOURCE_INVALID")
    if authorization["source"] == "shortcut" and state["authorization_card"]["authorization_message"] != "1":
        fail("AUTHORIZATION_SHORTCUT_INVALID")
    if require_string(authorization["intent"], "AUTHORIZATION_INTENT") not in {"execute", "discuss"}:
        fail("AUTHORIZATION_INTENT_INVALID")
    grants = require_list(authorization["granted_actions"], "GRANTED_ACTIONS", allow_empty=True)
    planned = require_list(authorization["planned_actions"], "PLANNED_ACTIONS", allow_empty=True)
    grant_keys = set()
    for records, label in ((grants, "GRANTED"), (planned, "PLANNED")):
        seen = set()
        for record in records:
            record = require_object(record, label + "_ACTION")
            if not {"action", "target"} <= set(record) or set(record) - {"action", "target", "impact", "rollback"}:
                fail(label + "_ACTION_FIELDS_INVALID")
            if require_string(record["action"], "ACTION") not in ACTION_KINDS:
                fail("ACTION_KIND_INVALID")
            target = require_string(record["target"], "ACTION_TARGET")
            if any(char in target for char in ("*", "?", "\n", "\r")):
                fail("ACTION_TARGET_NOT_EXACT")
            if record["action"] == "workspace-write":
                validate_relative_path(target)
                if target == "." or Path(target).as_posix() != target:
                    fail("ACTION_TARGET_NOT_EXACT")
            key = (record["action"], target)
            if key in seen:
                fail(label + "_ACTION_DUPLICATE")
            seen.add(key)
            if label == "GRANTED":
                grant_keys.add(key)
            elif key not in grant_keys:
                fail("PLANNED_ACTION_NOT_AUTHORIZED")
    mutating = [record for record in planned if record["action"] not in READ_ACTIONS]
    if authorization["intent"] == "discuss" and mutating:
        fail("DISCUSSION_CANNOT_WRITE")
    if risk == "read-only" and mutating:
        fail("READ_ONLY_CANNOT_WRITE")
    if state["candidate"]["state"] == "阻塞" and mutating:
        fail("BLOCKED_CANDIDATE_CANNOT_EXECUTE")
    high_risk = risk == "high-risk" or any(record["action"] in HIGH_RISK_ACTIONS for record in grants + planned)
    for grant in grants:
        if grant["action"] in HIGH_RISK_ACTIONS or (risk == "high-risk" and grant["action"] not in READ_ACTIONS):
            if not all(isinstance(grant.get(field), str) and grant[field].strip() for field in ("impact", "rollback")):
                fail("HIGH_RISK_DETAILS_REQUIRED")
    identity = state["failure_identity"]
    if state["lifecycle"] == "recovery-repair" and (not isinstance(identity, dict) or not any(record["action"] == "recovery-repair" and record["target"] == identity.get("id") for record in planned)):
        fail("RECOVERY_REPAIR_ACTION_REQUIRED")
    validate_collaboration(state, high_risk)
    exceptions = require_list(state["quality_exceptions"], "QUALITY_EXCEPTIONS", allow_empty=True)
    ids = set()
    for exception in exceptions:
        exception = require_object(exception, "QUALITY_EXCEPTION")
        if set(exception) != {"id", "reason", "boundary", "exit_condition", "authorization_card_version", "authorization_evidence", "status"}:
            fail("QUALITY_EXCEPTION_FIELDS_INVALID")
        for field in ("id", "reason", "boundary", "exit_condition"):
            require_string(exception[field], "QUALITY_EXCEPTION_" + field.upper())
        if exception["id"] in ids:
            fail("QUALITY_EXCEPTION_ID_DUPLICATE")
        ids.add(exception["id"])
        if require_string(exception["status"], "QUALITY_EXCEPTION_STATUS") not in {"pending", "approved"}:
            fail("QUALITY_EXCEPTION_STATUS_INVALID")
        if exception["status"] == "approved":
            if exception["authorization_card_version"] != state["authorization_card"]["version"]:
                fail("QUALITY_EXCEPTION_AUTHORIZATION_STALE")
            require_string(exception["authorization_evidence"], "QUALITY_EXCEPTION_AUTHORIZATION_EVIDENCE")
        elif state["candidate"]["state"] in {"可收口", "已收口"}:
            fail("QUALITY_EXCEPTION_UNAPPROVED")
    events = require_list(state["diagnostic_events"], "DIAGNOSTIC_EVENTS", allow_empty=True)
    for event in events:
        event = require_object(event, "DIAGNOSTIC_EVENT")
        if set(event) != {"kind", "evidence", "observed_at"} or require_string(event["kind"], "DIAGNOSTIC_EVENT_KIND") not in {"environment", "tool", "syntax"}:
            fail("DIAGNOSTIC_EVENT_FIELDS_INVALID")
        require_string(event["evidence"], "DIAGNOSTIC_EVENT_EVIDENCE")
        validate_timestamp(event["observed_at"], "DIAGNOSTIC_EVENT_TIME")


def validate_collaboration(state: dict, high_risk: bool) -> None:
    collaboration = require_object(state["collaboration"], "COLLABORATION")
    if set(collaboration) != {"writer", "dispatches", "independent_review"}:
        fail("COLLABORATION_FIELDS_INVALID")
    writer = collaboration["writer"]
    if writer is not None:
        require_string(writer, "WRITER")
    dispatches = require_list(collaboration["dispatches"], "DISPATCHES", allow_empty=True)
    agents = {}
    for dispatch in dispatches:
        dispatch = require_object(dispatch, "DISPATCH")
        required = {"id", "role", "model", "effort", "permission", "observation"}
        if not required <= set(dispatch) or set(dispatch) - required - {"override"}:
            fail("DISPATCH_FIELDS_INVALID")
        identifier = require_string(dispatch["id"], "DISPATCH_ID")
        if identifier in agents or identifier == "main":
            fail("DISPATCH_ID_DUPLICATE")
        role = require_string(dispatch["role"], "DISPATCH_ROLE")
        if role not in ROLE_MODELS or dispatch["permission"] != ROLE_MODELS[role][2]:
            fail("DISPATCH_MODEL_OR_PERMISSION_MISMATCH")
        if (dispatch["model"], dispatch["effort"]) != ROLE_MODELS[role][:2]:
            override = require_object(dispatch.get("override"), "MODEL_OVERRIDE")
            if set(override) != {"reason", "authorization_card_version", "authorization_evidence"}:
                fail("MODEL_OVERRIDE_FIELDS_INVALID")
            for field in ("reason", "authorization_evidence"):
                require_string(override[field], "MODEL_OVERRIDE_" + field.upper())
            if override["authorization_card_version"] != state["authorization_card"]["version"]:
                fail("MODEL_OVERRIDE_AUTHORIZATION_STALE")
            require_string(dispatch["model"], "DISPATCH_MODEL")
            if require_string(dispatch["effort"], "DISPATCH_EFFORT") not in {"low", "medium", "high", "xhigh", "max", "ultra"}:
                fail("DISPATCH_EFFORT_INVALID")
        require_string(dispatch["observation"], "DISPATCH_OBSERVATION")
        agents[identifier] = dispatch
    writable = [key for key, agent in agents.items() if agent["permission"] == "workspace-write"]
    if len(writable) > 1 or (writer in {None, "main"} and writable) or (writer not in {None, "main"} and writable != [writer]):
        fail("SINGLE_WRITER_REQUIRED")
    writes = any(record["action"] == "workspace-write" for record in state["authorization_context"]["planned_actions"])
    if writes and writer is None:
        fail("WRITER_REQUIRED")
    if writes and state["task_assessment"]["difficulty"] != "small" and writer == "main":
        fail("DELEGATED_WRITER_REQUIRED")
    review = require_object(collaboration["independent_review"], "INDEPENDENT_REVIEW")
    if set(review) != {"status", "reviewer_id", "evidence"} or require_string(review["status"], "INDEPENDENT_REVIEW_STATUS") not in {"pending", "passed", "failed", "not-applicable"}:
        fail("INDEPENDENT_REVIEW_FIELDS_INVALID")
    if review["status"] == "passed":
        reviewer = agents.get(require_string(review["reviewer_id"], "INDEPENDENT_REVIEWER_ID"))
        if reviewer is None or reviewer["role"] != "reviewer" or review["reviewer_id"] == writer:
            fail("INDEPENDENT_REVIEWER_REQUIRED")
        require_string(review["evidence"], "INDEPENDENT_REVIEW_EVIDENCE")
    elif review["status"] in {"failed", "not-applicable"}:
        require_string(review["evidence"], "INDEPENDENT_REVIEW_EVIDENCE")
    if any(action["action"] in REVIEW_BEFORE_EXECUTION for action in state["authorization_context"]["planned_actions"]) and review["status"] != "passed":
        fail("INDEPENDENT_REVIEW_INCOMPLETE")
    if state["candidate"]["state"] in {"可收口", "已收口"}:
        if (high_risk and review["status"] != "passed") or review["status"] in {"pending", "failed"}:
            fail("INDEPENDENT_REVIEW_INCOMPLETE")


def validate_v5_diff(state: dict, repo: Path, state_path: Path, baseline: str) -> None:
    changes = current_changes(repo, state_path, baseline)
    authorization = state["authorization_context"]
    if changes and authorization["intent"] == "discuss":
        fail("DISCUSSION_CANNOT_WRITE")
    if changes and state["task_assessment"]["operation_risk"] == "read-only":
        fail("READ_ONLY_CANNOT_WRITE")
    targets = [grant["target"] for grant in authorization["granted_actions"] if grant["action"] == "workspace-write"]
    outside = sorted(path for path in changes if not any(path == target or path.startswith(target + "/") for target in targets))
    if outside:
        fail("DIFF_OUTSIDE_AUTHORIZED_TARGETS: " + ", ".join(outside))


def validate_v5_feedback(evidence: dict, ready: bool) -> None:
    kind, mode, before = evidence["task_kind"], require_string(evidence["verification_mode"], "VERIFICATION_MODE"), evidence["before_status"]
    modes = {"bug": {"bug-repro", "bug-diagnosis"}, "visual": {"existing-ui", "new-ui"}}
    if mode not in modes.get(kind, {"standard"}):
        fail("VERIFICATION_MODE_INVALID")
    allowed = {"pending", "red", "captured", "baseline-green", "not-applicable"}
    if mode == "bug-repro":
        allowed = {"pending", "red"}
    elif mode in {"bug-diagnosis", "existing-ui"}:
        allowed = {"pending", "captured"}
    elif mode == "new-ui":
        allowed = {"pending", "not-applicable"}
    if before not in allowed or (ready and before == "pending"):
        fail("V5_FEEDBACK_EVIDENCE_REQUIRED")
    if mode == "bug-diagnosis" and not evidence["unverified_boundaries"]:
        fail("DIAGNOSIS_UNVERIFIED_BOUNDARY_REQUIRED")


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


def validate_failures(identity: object, failures: list, failure_count: object, recovery: dict, lifecycle: str, card: dict, protocol_version: int = 4) -> None:
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
    if protocol_version == 5:
        for field in ("authorization_message", "authorization_basis"):
            require_string(pre_authorization[field], "PRE_RECOVERY_" + field.upper())
    pre_version = card_version(pre_authorization["card_version"], "PRE_RECOVERY_CARD_VERSION")
    if protocol_version < 5 and (pre_authorization["authorization_message"] != "1" or pre_authorization["authorization_basis"] != "最新完整十四项卡的精确1"):
        fail("PRE_RECOVERY_AUTHORIZATION_INVALID")
    diagnosis_authorization = require_object(recovery["diagnosis_authorization"], "DIAGNOSIS_AUTHORIZATION")
    if set(diagnosis_authorization) != {"card_version", "authorization_message", "authorization_basis"}:
        fail("DIAGNOSIS_AUTHORIZATION_FIELDS_INVALID")
    if protocol_version == 5:
        for field in ("authorization_message", "authorization_basis"):
            require_string(diagnosis_authorization[field], "DIAGNOSIS_" + field.upper())
    diagnosis_version = card_version(diagnosis_authorization["card_version"], "DIAGNOSIS_CARD_VERSION")
    if (protocol_version < 5 and (diagnosis_authorization["authorization_message"] != "1" or diagnosis_authorization["authorization_basis"] != "最新完整十四项卡的精确1")) or diagnosis_version <= pre_version:
        fail("DIAGNOSIS_AUTHORIZATION_INVALID")
    if lifecycle == "recovery-diagnosis" and recovery["kind"] == "diagnosis":
        if protocol_version == 5 and any(diagnosis_authorization[field] != card[card_field] for field, card_field in (("card_version", "version"), ("authorization_message", "authorization_message"), ("authorization_basis", "authorization_basis"))):
            fail("DIAGNOSIS_AUTHORIZATION_STALE")
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


def validate_scope(scope: dict, business_goal: str, repo: Path, state_path: Path, baseline: str, check_diff: bool, *, protocol_version: int, card_version: str, findings: list[dict] | None) -> list[str]:
    if set(scope) != {"initial_allowed_paths", "discovered_paths"}:
        fail("WRITE_SCOPE_FIELDS_INVALID")
    initial = require_list(scope["initial_allowed_paths"], "INITIAL_ALLOWED_PATHS")
    discovered = require_list(scope["discovered_paths"], "DISCOVERED_PATHS", allow_empty=True)
    allowed = list(initial)
    for path in initial:
        validate_relative_path(path)
    finding_by_id = {finding["id"]: finding for finding in findings or []}
    for record in discovered:
        record = require_object(record, "DISCOVERED_PATH")
        required = {"path", "reason", "business_goal", "discovered_at"}
        if protocol_version in FROZEN_SCOPE_PROTOCOL_VERSIONS:
            required |= {"authorization_card_version", "source_kind", "source_id", "causal_evidence"}
        if set(record) != required:
            fail("DISCOVERED_PATH_FIELDS_INVALID")
        path = require_string(record["path"], "DISCOVERED_PATH")
        validate_relative_path(path)
        require_string(record["reason"], "DISCOVERED_PATH_REASON")
        if require_string(record["business_goal"], "DISCOVERED_PATH_BUSINESS_GOAL") != business_goal:
            fail("DISCOVERED_PATH_BUSINESS_GOAL_MISMATCH")
        validate_timestamp(record["discovered_at"], "DISCOVERED_PATH_TIME")
        if protocol_version in FROZEN_SCOPE_PROTOCOL_VERSIONS:
            if require_string(record["authorization_card_version"], "DISCOVERED_PATH_CARD_VERSION") != card_version:
                fail("DISCOVERED_PATH_CARD_VERSION_MISMATCH")
            source_kind = require_string(record["source_kind"], "DISCOVERED_PATH_SOURCE_KIND")
            if source_kind not in {"target-authority", "acceptance-check", "current-blocker"}:
                fail("DISCOVERED_PATH_SOURCE_KIND_INVALID")
            source_id = require_string(record["source_id"], "DISCOVERED_PATH_SOURCE_ID")
            require_string(record["causal_evidence"], "DISCOVERED_PATH_CAUSAL_EVIDENCE")
            if source_kind == "target-authority":
                if source_id != "scope-control":
                    fail("DISCOVERED_PATH_TARGET_SOURCE_INVALID")
            elif source_kind == "acceptance-check":
                if source_id not in {"target_check", "adjacent_regression", "real_environment"}:
                    fail("DISCOVERED_PATH_ACCEPTANCE_SOURCE_INVALID")
            else:
                finding = finding_by_id.get(source_id)
                if finding is None or finding["classification"] != "current-blocker":
                    fail("DISCOVERED_PATH_CURRENT_BLOCKER_INVALID")
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


def validate_scope_control(value: object, card: dict) -> None:
    scope_control = require_object(value, "SCOPE_CONTROL")
    if set(scope_control) != {"authorization_card_version", "status", "in_scope", "out_of_scope", "completion_policy"}:
        fail("SCOPE_CONTROL_FIELDS_INVALID")
    if require_string(scope_control["authorization_card_version"], "SCOPE_CONTROL_CARD_VERSION") != card["version"]:
        fail("SCOPE_CONTROL_CARD_VERSION_MISMATCH")
    if scope_control["status"] != "frozen":
        fail("SCOPE_CONTROL_STATUS_INVALID")
    for field in ("in_scope", "out_of_scope"):
        for item in require_list(scope_control[field], f"SCOPE_CONTROL_{field.upper()}"):
            require_string(item, f"SCOPE_CONTROL_{field.upper()}_ITEM")
    if require_string(scope_control["completion_policy"], "SCOPE_CONTROL_COMPLETION_POLICY") != "delivery-evidence-passed-no-open-blocker":
        fail("SCOPE_CONTROL_COMPLETION_POLICY_INVALID")


def validate_findings(value: object, candidate: dict) -> list[dict]:
    findings = require_list(value, "FINDING_RECORDS", allow_empty=True)
    finding_ids: set[str] = set()
    for finding in findings:
        finding = require_object(finding, "FINDING_RECORD")
        if set(finding) != {"id", "summary", "classification", "causal_relation", "causal_evidence", "action", "status"}:
            fail("FINDING_RECORD_FIELDS_INVALID")
        finding_id = require_string(finding["id"], "FINDING_ID")
        if finding_id in finding_ids:
            fail("FINDING_ID_DUPLICATE")
        finding_ids.add(finding_id)
        require_string(finding["summary"], "FINDING_SUMMARY")
        classification = require_string(finding["classification"], "FINDING_CLASSIFICATION")
        causal_relation = require_string(finding["causal_relation"], "FINDING_CAUSAL_RELATION")
        require_string(finding["causal_evidence"], "FINDING_CAUSAL_EVIDENCE")
        action = require_string(finding["action"], "FINDING_ACTION")
        if finding["status"] not in {"open", "resolved"}:
            fail("FINDING_STATUS_INVALID")
        if classification == "current-blocker":
            if causal_relation not in {"target-required", "introduced-by-current-diff", "worsened-by-current-diff"}:
                fail("CURRENT_BLOCKER_CAUSAL_RELATION_INVALID")
            if action != "repair-current":
                fail("CURRENT_BLOCKER_ACTION_INVALID")
        elif classification == "deferred":
            if action != "record-only":
                fail("DEFERRED_ACTION_INVALID")
        elif classification == "scope-change":
            if action != "stop-for-decision":
                fail("SCOPE_CHANGE_ACTION_INVALID")
            if finding["status"] == "open" and (candidate["state"] != "阻塞" or candidate["closeout_state"] != "阻塞"):
                fail("OPEN_SCOPE_CHANGE_REQUIRES_BLOCKED_CANDIDATE")
        else:
            fail("FINDING_CLASSIFICATION_INVALID")
    return findings


def validate_check(value: object, label: str, *, target: bool = False, require_baseline: bool = False) -> str:
    check = require_object(value, label)
    required = {"status", "evidence"}
    if require_baseline:
        required |= {"signal", "baseline_status", "baseline_evidence"}
    if set(check) != required:
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
    if require_baseline:
        require_string(check["signal"], f"{label}_SIGNAL")
        baseline_status = check["baseline_status"]
        if baseline_status not in BASELINE_STATUSES:
            fail(f"{label}_BASELINE_STATUS_INVALID")
        baseline_evidence = check["baseline_evidence"]
        if baseline_status == "unknown":
            if baseline_evidence is not None:
                fail(f"{label}_BASELINE_UNKNOWN_EVIDENCE_INVALID")
        else:
            require_string(baseline_evidence, f"{label}_BASELINE_EVIDENCE")
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
    *,
    protocol_version: int,
) -> None:
    evidence = require_object(evidence, "DELIVERY_EVIDENCE")
    required = {
        "task_kind", "user_visible_outcome", "target_entrypoint", "feedback_signal",
        "before_status", "before_evidence", "feedback_scope", "target_check", "adjacent_regression",
        "real_environment", "unverified_boundaries",
    }
    if protocol_version == 5:
        required.add("verification_mode")
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
    if protocol_version == 5:
        validate_v5_feedback(evidence, feedback_ready)
    elif task_kind in {"feature", "bug"}:
        if before_status not in {"pending", "red"} or (feedback_ready and before_status != "red"):
            fail("DELIVERY_RED_REQUIRED")
    if protocol_version < 5 and task_kind == "visual":
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
    require_baseline = protocol_version in FROZEN_SCOPE_PROTOCOL_VERSIONS
    target_status = validate_check(evidence["target_check"], "DELIVERY_TARGET_CHECK", target=True, require_baseline=require_baseline)
    regression_status = validate_check(evidence["adjacent_regression"], "DELIVERY_ADJACENT_REGRESSION", require_baseline=require_baseline)
    environment_status = validate_check(evidence["real_environment"], "DELIVERY_REAL_ENVIRONMENT", require_baseline=require_baseline)
    boundaries = require_list(evidence["unverified_boundaries"], "DELIVERY_UNVERIFIED_BOUNDARIES", allow_empty=True)
    for boundary in boundaries:
        require_string(boundary, "DELIVERY_UNVERIFIED_BOUNDARY")
    if before_status == "pending" and any(status != "pending" for status in (target_status, regression_status, environment_status)):
        fail("DELIVERY_CHECKS_BEFORE_FEEDBACK")
    if (candidate["state"] == "待判断" or evidence.get("verification_mode") == "bug-diagnosis") and check_diff:
        outside_feedback = sorted(
            path for path in current_changes(repo, state_path, baseline)
            if not any(path == allowed or path.startswith(f"{allowed}/") for allowed in feedback_scope)
        )
        if outside_feedback:
            fail(f"DIFF_OUTSIDE_FEEDBACK_SCOPE: {', '.join(outside_feedback)}")
    if candidate["state"] == "已收口" or (protocol_version in FROZEN_SCOPE_PROTOCOL_VERSIONS and candidate["state"] == "可收口"):
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
    required_fields_by_version = {
        2: base_required,
        3: base_required | {"delivery_evidence"},
        4: base_required | {"delivery_evidence", "scope_control", "finding_records"},
        5: base_required | {"delivery_evidence", "scope_control", "finding_records", "task_assessment", "authorization_context", "collaboration", "quality_exceptions", "diagnostic_events"},
    }
    required = required_fields_by_version[protocol_version]
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
    validate_card(card, protocol_version)
    baseline = validate_baseline(state, repo, check_worktree)
    current_branch, resolved_primary = validate_runtime(candidate, repo, check_worktree)
    validate_candidate(candidate, card, primary, current_branch, resolved_primary)
    if protocol_version == 5:
        validate_v5_governance(state)
    validate_failures(state["failure_identity"], state["failure_records"], state["production_failure_count"], require_object(state["recovery"], "RECOVERY"), state["lifecycle"], card, protocol_version)
    validate_location(state, state_path, state_dir, check_location)
    validate_closeout(candidate)
    findings: list[dict] | None = None
    if protocol_version in FROZEN_SCOPE_PROTOCOL_VERSIONS:
        validate_scope_control(state["scope_control"], card)
        findings = validate_findings(state["finding_records"], candidate)
    allowed_paths = validate_scope(
        require_object(state["write_scope"], "WRITE_SCOPE"),
        card["business_goal"],
        repo,
        state_path,
        baseline,
        check_diff,
        protocol_version=protocol_version,
        card_version=card["version"],
        findings=findings,
    )
    if protocol_version == 5 and check_diff:
        validate_v5_diff(state, repo, state_path, baseline)
    if protocol_version in DELIVERY_EVIDENCE_PROTOCOL_VERSIONS:
        validate_delivery_evidence(
            state["delivery_evidence"], state["failure_identity"], candidate, repo, state_path, baseline,
            allowed_paths, check_diff, protocol_version=protocol_version,
        )
    if protocol_version in FROZEN_SCOPE_PROTOCOL_VERSIONS and candidate["state"] in {"可收口", "已收口"}:
        if any(finding["status"] == "open" and finding["classification"] in {"current-blocker", "scope-change"} for finding in findings or []):
            fail("OPEN_BLOCKER_PREVENTS_CLOSEOUT")


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

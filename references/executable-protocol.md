# 严格任务协议 v6

普通任务不创建状态文件、不运行本脚本。长任务用简短交接记录即可。涉及权限、重要数据、生产或难撤销动作时，主任务建立以下记录；已有 v2–v5 使用 [旧协议](legacy-protocol.md)，脚本按版本分别校验，不自动迁移。

## 最小记录

```json
{
  "protocol_version": 6,
  "task_id": "access-repair",
  "skill_root": "/absolute/path/to/dev-team",
  "candidate": {"branch": "dev/quanxian-xiufu", "worktree": "/absolute/path/to/project", "baseline": "完整基线 SHA"},
  "goal": "修复成员越权读取",
  "authorization": "当前用户明确请求及消息位置",
  "write_scope": ["src/access", "tests/access"],
  "risk": "high-risk",
  "impact": "成员读取权限变化",
  "rollback": "恢复本次候选代码；未执行生产迁移",
  "status": "active",
  "checks": [{"command": "项目实际权限检查命令", "status": "pending", "evidence": null}]
}
```

模板占位值须替换为真实事实。目标与 authorization 保存业务范围和已有授权，write_scope 是唯一文件范围来源，使用规范仓库相对路径或目录，不能以 `.` 或通配符覆盖仓库。范围内发现新入口可由主任务更新，业务目标变化须用户决定。Git 已忽略的未跟踪产物不计入源码 diff；已跟踪文件仍检查。运行态写入等不能借 Git 排除规则获得权限。

risk 为 reversible 或 high-risk；status 为 active、blocked 或 completed。checks 按当前阶段列出必要检查，每项保存实际命令或观察入口、pending/passed/failed 和证据。部署前检查可运行的前置条件；部署后健康检查先保留在任务未完成项中，部署完成后加入 checks 并执行，最终交付前完成所有必要后置检查。不得将已可运行却失败或待执行的检查移走以绕过门禁。完成时全部通过且无 blockers；不制造固定的“不适用”检查。高风险保存 impact、rollback，无法回滚时如实说明后果与已有明确同意。

## 按需字段

- `writers`：并行时列出 `{"id":"执行者标识","paths":["src/module"]}`，包含主任务自己的写入职责。同一文件及父子目录不得分给不同写入者。共享接口由主任务保证职责不冲突，路径不重叠不能证明业务独立。
- `actions`：只列即将执行的 Git 或外部动作，保存 `action`、准确 `target`、`authorization`；高风险动作另带 `impact`、`rollback`。动作名沿用脚本 ACTION_KINDS，workspace-write 与 recovery 动作不在 v6 actions 中：源码范围由 write_scope 管理，恢复按证据推进。已有 v6 记录中的普通合并按 `reversible` 核对授权及全部必要检查，并在该动作的 `risk_evidence` 中填写 `diff` 与 `target_branch`：前者指向真实变更及不涉及高风险内容的依据，后者指向目标分支和保护规则的核对结果。高风险合并按 `high-risk` 增加影响、回滚和执行前独立验收。校验器只检查这些文字非空，主任务仍须核对原始事实。用户聊天是授权来源，记录无法证明真实同意。完成动作从即将执行列表移到已有证据，不复制两套授权数组。
- `review`：`reviewer`、`evidence`、`fingerprint`。验收者必须不同于所有写入者且只读，主任务核对真实身份、权限和工具证据。高风险交付、合并、部署等外部高风险执行前必须完成必要检查且通过独立验收；权限代码可先实现再验收。指纹绑定代码内容、候选、范围、风险、授权及动作对象，变化后需重新验收受影响部分。
- `blockers`：当前阻塞的文字列表。新增范围未决也属于阻塞；有阻塞时 status 为 blocked，暂停受影响写入，不用“已完成”绕过。
- `failures` 与 `next_attempt`：实际失败后才添加。前者为 `{"hypothesis":"已证伪假设","evidence":"原始结果"}` 列表；继续时后者记录不同的 hypothesis 与 new_evidence。没有按次数停止，也不清除历史；语义上重复的假设由主任务核对。
- `safe_cleanup`：仅本地分支或 worktree 删除动作可附 `{"merged_into":"保留分支或提交","unused_evidence":"无任务与进程占用的核对结果"}`，按 [Git 生命周期](git-lifecycle.md) 验证后免额外独立验收。该检查不执行删除，也不能证明文本证据的真实性。

## 检查时机与命令

首次写入、职责交接、目录/分支/权限变化、跨上下文恢复、交付和高风险动作执行前运行一次。稳定环境中的连续编辑不重复全检。失败后依据错误修正真实问题，不为让校验通过伪造记录。

```sh
python3 /absolute/path/to/dev-team/scripts/verify-protocol.py --skill-root /absolute/path/to/dev-team --state-dir /absolute/user/state --state /absolute/user/state/access-repair.json --repo /absolute/path/to/project
```

验收者先对稳定候选运行同一命令加 `--fingerprint`，记录指纹并检查；完成后主任务填入 review，实时校验确认候选未变化。获取指纹只计算内容，不代表验收或授权。`--structure-only` 只用于夹具测试，不作为实际执行证据。

脚本检查真实 Git 根、基线祖先、分支/worktree、累计 diff 和范围交集；拒绝 gitlink、稀疏检出与特殊索引。它不是沙箱，不能阻止绕过工具的写入，不能证明测试或用户授权。运行 `python3 tests/test_protocol.py` 检查旧协议，`python3 tests/test_v6.py` 检查新协议，`bash scripts/verify-setup.sh --source-only` 检查完整源码包。

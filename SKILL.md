---
name: dev-team
description: 手动调用的通用开发协作路由器；按任务风险选择最小团队，协调开发、UI、验证、Git 候选和安全收口。
disable-model-invocation: true
---

# 通用开发协作

按任务需要增加协作与检查。主任务保留用户选择的模型，自主决定实现方法；项目与全局规则已覆盖的事项执行一次。

## 选择路径

- 普通且可逆：主任务直接实现并验证。写入前确认目标、范围、完成标准和实际目录，复用已有任务记录；不创建完整 JSON，不运行机器协议，不额外派单。
- 长任务或独立工作能并行：按 [协作与交接](references/dispatch-packet.md) 分工，用简短记录保存目标、目录、职责、证据和未完成项。每个文件或紧密关联范围只有一个写入者；独立模块可并行，集成由主任务负责。
- 权限、重要数据、生产或难撤销动作：使用 [严格协议](references/executable-protocol.md) 的 v6，保留独立只读验收。普通任务执行中出现这些动作时，先为该阶段补齐严格记录。复杂度或文件数量本身不触发严格路径。
- 已有 v2–v5 机器记录：继续按 [旧协议](references/legacy-protocol.md) 执行，不改版本号绕过原约束。

## 必要时读取

- 候选准备、Git 或清理：[Git 生命周期](references/git-lifecycle.md)。写入前判断同任务续做、独立任务或归属不明；同目标复用，独立目标另建候选，有并发或无关改动时用独立 worktree。
- 项目或运行事实不清：[项目发现](references/project-discovery.md)。
- 实现与验证：[工程质量](references/engineering-quality.md)；UI：[UI 路由](references/ui-routing.md)。
- 故障反复失败：[诊断与恢复](references/recovery.md)。
- 需要专业方法：[专项选择](references/specialist-routing.md)；实际派单再读 [模型策略](references/model-policy.md)。

## 完成

目标检查通过、当前阻塞解决后交付，不把无关建议变成新增验收条件。说明结果、验证、未验证边界和候选去向。已授权的实现、验证和返工连续完成；提交、发布和清理按准确对象核对已有授权。

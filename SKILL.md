---
name: dev-team
description: 手动调用的通用开发协作路由器；按任务风险选择最小团队，协调开发、UI、验证、Git 候选和安全收口。
disable-model-invocation: true
---

# 通用开发协作

在用户明确调用时协调开发至已授权终点。主任务负责目标、授权、候选归属和最终结果；模型与角色默认值保持现有配置。

## 选择路径

按 [routing.md](references/routing.md) 判断实际操作风险与协作收益。普通实现可由主任务直接完成；只有独立子任务能减少等待、提供必要专业能力或独立核验时才派单。高风险保留全新只读独立验收。同一业务目标同一阶段只有一个写入者，子 Agent 不再派生，默认最多两个子 Agent 同时活动。

## 按需读取

- 只读解释或讨论：直接回答相关问题，不建候选、不加载写入协议。
- 写入：确认目标、范围、候选和相称的完成标准，遵循 [engineering-quality.md](references/engineering-quality.md)。一份 [任务记录](references/candidate-ledger.md) 保存授权、范围、验证和恢复事实；主任务与执行员都须在派单、写入及恢复前运行默认实时门禁；字段和命令用法见 [executable-protocol.md](references/executable-protocol.md)，示例按需读取。新任务用 v5，旧任务按原版本。
- 项目或运行事实不清：查 [project-discovery.md](references/project-discovery.md)；候选准备、Git 操作或收口：查 [git-lifecycle.md](references/git-lifecycle.md)。同目标复用候选，不吸收无关改动。
- 准备派单或授权对象存在疑问：查 [dispatch-packet.md](references/dispatch-packet.md)；实际派单才查 [model-policy.md](references/model-policy.md)，不为主任务直做重复核验子角色能力。
- UI 查 [ui-routing.md](references/ui-routing.md)；未知根因或修复反复失败查 [recovery.md](references/recovery.md)；确需专业方法时查 [specialist-routing.md](references/specialist-routing.md)。

## 完成

已授权范围内的准备、实现、验证和返工连续完成，不因阶段交接重复请求确认。适用检查通过且没有当前阻塞、未决范围变化或未批准质量例外后交付，不再提高完成标准。协议通过和子任务总结不能代替实际证据。

报告改动、必要验证、未验证边界和候选状态。提交、推送、PR、合并、清理和外部操作分别核对已有授权与准确对象；本地完成不自动授权后续动作。

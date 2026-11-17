# BRACE-MSI 第一性原理重建取证报告

## 结论

第一次完成官方全流程的是 2026-11-13 12:50:58 的试运行。它完成 A/B/C 各 10 轮和 14,773 条隐藏预测，但输入、输出 Token 均为 0。该运行证明旧容器能够完成平台旧流程，不证明 PyTRiO Agent 实际参与。平台报告与本地冻结链的指标指纹一致；`0.3.0rc3`是最强镜像候选，但平台没有公开该次运行所绑定镜像的直接 ID 或 SHA-256，所以精确绑定保持 `UNKNOWN`。

2026-11-15 12:45:25 的第二次成功运行与首次成功的逐轮指标、隐藏指标和零 Token 特征一致，只是 CPU/墙钟略有变化。它没有新增 Agent 合规证据。

最近两次失败已有平台原始错误，不再按猜测修补：

1. 2026-11-16 18:07:30：原生入口只支持 PyTRiO 私有 Sampler 协议，无法忠实桥接平台 Chat Completions；确定性/失败降级产生零模型调用，违反每轮模型调用硬门。
2. 2026-11-17 12:49:50：`brace_msi.contest_submission.train(rnd)`在平台代入测试中没有产生真实模型调用；固定`/workspace/state`和`candidate`目录导致第二轮违反新目录/空目录约束；平台同时质疑预测命令。后一点与官方 SDK 1.0.2 明示的`["python3", "/app/harness.py", "predict"]`冲突，正式实现以官方 SDK 文档为准并用其原包测试验证。

## 已证实因果链

```text
私有 PyTRiO ServiceClient 路径
  -> 宿主只提供 workspace v2 Chat Completions
  -> 无法忠实桥接
  -> 训练轮没有真实 call_id
  -> MODEL_CALL_REQUIRED / 运行失败

复杂 adapter + 模型调用藏在策略分支
  -> NOOP/ROLLBACK/异常恢复可能跳过模型调用
  -> finish(model_call_ids=[])
  -> workspace v2 硬门失败

固定 /workspace/state 和 /workspace/candidate
  -> 跨轮持久目录在第二轮已存在
  -> state_workspace 要求全新目的目录
  -> FileExistsError / 十轮无法继续
```

## 保留与淘汰

- 保留：官方 `contest_harness` 1.0.2 原包、父 checkpoint 哈希验证、原生 `contest.cpu-mlp.v1` 加载/Adam续训/保存、纯本地预测、候选提交和平台测量、Docker非 root/CPU限制。
- 淘汰：正式镜像内的 PyTRiO 私有客户端、SFT、SwanLab SDK、代理模拟、论文实验、完整包审计、固定工作目录、把模型调用放在可跳过策略分支中的做法。
- 冻结证据：所有历史 RC、成功/失败运行、代理实验和 INVALID 记录，不删除、不覆盖。

## 直接证据

- 官方 SDK：`C:/Users/Administrator/Desktop/人工智能创新大赛/新增/contest-harness-sdk-1.0.2.txt`
- 首次运行：平台评测运行页 2026-11-13 12:50:58；`docs/source_notes/PLATFORM_TRIAL_V1_2026-11-13.md`
- 最近失败：平台评测运行页 2026-11-17 12:49:50 原始失败详情
- 前次失败：平台评测运行页 2026-11-16 18:07:30 原始失败详情
- 历史恢复：`0.3.0rc3`标签`c528420`，归档 SHA-256 `0DAEF2E0...6D325A`

## 边界

本报告不声称已定位平台未公开的内部实现，也不声称任何本地模拟等于隐藏评测。下一次平台机会只能由新最小正式镜像在完整本地 workspace v2 十轮验收后使用。

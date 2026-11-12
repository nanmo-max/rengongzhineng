# PYTRIO-HARNESS-001-A2 对照结果

## 证据边界

- 数据：官方A/B/C公开训练包与公开验证；没有隐藏数据、官方试运行或SwanLab。
- 两臂使用同一`formal_agent_dev.json`、官方训练器、预算与SafetyGate；运行根互相隔离。
- 公开验证已经历史暴露，本结果只证明链路、合规和相对行为，不是官方成绩。

## 结果

| 臂 | 任务 | 初始主指标 | 最终主指标 | 真实候选 | 上线 | Agent调用 | 输入/输出Token | 合规覆盖 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| deterministic | A Macro-F1↑ | 0.714030 | 0.725695 | 3 | 1 | 0 | 0/0 | 0 |
| deterministic | B RMSE↓ | 681.159833 | 656.351785 | 3 | 2 | 0 | 0/0 | 0 |
| deterministic | C RMSE↓ | 52.868573 | 52.350178 | 3 | 1 | 0 | 0/0 | 0 |
| PyTRiO A2 Sampler | A Macro-F1↑ | 0.714030 | 0.725695 | 3 | 1 | 10 | 6722/660 | 3 |
| PyTRiO A2 Sampler | B RMSE↓ | 681.159833 | 656.351785 | 3 | 2 | 10 | 6678/652 | 3 |
| PyTRiO A2 Sampler | C RMSE↓ | 52.868573 | 52.350178 | 3 | 1 | 10 | 6672/649 | 3 |

六个运行均由`official-agent-run --validate-only`复算为`valid=true`。PyTRiO臂30/30次原始建议均为合法`noop`；每任务前三次由`minimum_candidate_events`守卫覆盖为白名单训练动作，因此最终性能与确定性臂相同。

## 结论

A2 Sampler已经解决结构化JSON与安全边界，但没有在当前静态公开包上下文中增加动作决策价值，反而增加20,072输入Token、1,961输出Token和服务延迟。按R-028不能包装成性能创新。下一步只允许一次有界的合规语料SFT，直接检验模型能否在最低候选证据存在时主动提出动作；若失败，正式系统保留Sampler可选接口与确定性降级，默认由BRACE执行候选策略。

机器产物：`D:/brace-msi-pytrio/PYTRIO-HARNESS-001-A2/`。

# GENERALIZATION-MATRIX-001-A5 审计修复复演（复审阻断）

## 结论

A5修正了A4的末轮虚假回滚，原始数值显示`bounded_exploration`是唯一通过当时机器门的策略。但独立复审发现路径链接检查时序不正确，且最终checkpoint未与选中内存状态绑定，因此A5只保留为完整运行数值，不得晋级。

| 策略 | A平均有向收益 | B平均有向收益 | C平均有向收益 | 最差相对收益 | 本地机器门 |
|---|---:|---:|---:|---:|---|
| strict_parent_gate | +0.313085 | +52.809619 | +0.128450 | -14.7288% | 否 |
| bounded_exploration | +0.312990 | +89.198667 | +0.173614 | -1.3983% | 是 |
| conditional_champion | +0.313085 | +63.414421 | +0.147862 | -1.3983% | 否（artifact恢复未验证） |
| recipe_feedback | +0.313085 | +52.809619 | +0.524004 | -14.7288% | 否 |

## 审计修复证据

- 第10轮`rollback_available=false`。B/C的有限探索候选退化时均保留父模型，`exploration_consumed=0`。
- 12条链都为10个真实训练轮，每条至少10个可加载候选，`final_selection_safe=true`。
- 运行只允许`round-01..10/{feedback,update,gate}.jsonl`；不支持的文件名、越界路径和符号链接失败关闭。
- 晋级门比较严格父子门的聚合相对收益和最差相对收益，不再只检查平均值。
- `conditional_champion`在官方SDK的历史产物持久化/恢复未通过前明确不得晋级。

## 独立复审阻断

- 实际A5输入中没有发现symlink/junction，所以不存在已发生泄漏的证据。
- runner对轮目录先`resolve()`再`is_symlink()`，会丢失链接身份；同根未来轮或confirmation别名理论上可绕过边界。
- `promotion_pass`只检查`final_selection_safe`，没有验证保存checkpoint的全状态/预测与末轮选中模型一致。
- 两项问题必须用新实验ID复演；A5不得因数值正向而跳过。

## 资源

- 4策略 × 3任务 × 10轮，120/120轮训练完成。
- 总墙钟42.27秒；各策略累计CPU约2.33—3.03秒。
- Token=0；confirmation/public validation读取0；官方试运行0。

## 证据边界

A5与A3/A4使用同一开发代理流，而尺度异质触发条件来自该流的已开放证据。因此A5只能支持“本地开发候选”，不能支持“未见任务泛化已证明”或“可直接替换正式RC”。性能方法冻结后，还必须在未用于触发条件选择的替代流/任务留出上完成最终泛化验收。

## 机器产物

- `D:/brace-msi-generalization/GENERALIZATION-MATRIX-001-A5/summary.json`
- SHA-256：`9903249414FE93D6B4708A348D7E00CDF2DC73F0E9F683BB4C52FED55070B252`

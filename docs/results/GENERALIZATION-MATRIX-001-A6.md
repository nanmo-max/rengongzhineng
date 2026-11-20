# GENERALIZATION-MATRIX-001-A6 路径与最终checkpoint绑定复演

## 结论

A6关闭了A5独立复审发现的两项缺陷：输入路径现在在解析前拒绝symlink/junction；最终保存checkpoint现在必须与末轮选中内存模型的全状态指纹和Gate预测一致。`bounded_exploration`是唯一通过修正后开发机器门的策略。

| 策略 | A平均有向收益 | B平均有向收益 | C平均有向收益 | 最差相对收益 | 开发晋级 |
|---|---:|---:|---:|---:|---|
| strict_parent_gate | +0.313085 | +52.809619 | +0.128450 | -14.7288% | 否 |
| bounded_exploration | +0.312990 | +89.198667 | +0.173614 | -1.3983% | 是 |
| conditional_champion | +0.313085 | +63.414421 | +0.147862 | -1.3983% | 否（artifact恢复未验证） |
| recipe_feedback | +0.313085 | +52.809619 | +0.524004 | -14.7288% | 否 |

## 路径与未来隔离

- `runtime-inputs`根、轮目录和JSONL文件在`resolve()`前拒绝symlink；Windows junction同样拒绝。
- 真实对抗测试覆盖同根轮目录symlink、运行根symlink和Windows junction；三项均先复现绕过，再验证失败关闭。
- A6实际输入根的reparse point数为0；本次没有读取confirmation/public validation。

## 最终checkpoint绑定

- 保存前对元数据、模型参数、Adam一/二阶矩、预处理mean/scale生成确定性状态SHA-256。
- 保存后使用正式`_NativeModel.load`重新加载，再比较状态SHA-256和末轮Gate逐样本预测。
- 12/12最终checkpoint均`final_checkpoint_verified=true`；该字段为false时`promotion_pass`必然失败。

## 资源与证据边界

- 4策略 × 3任务 × 10轮，120/120轮真实候选训练。
- 总墙钟42.41秒；Token=0；官方试运行0。
- A6仍复用开发代理流，只证明开发策略筛选完成。它不是隐藏成绩，也不是正式RC的最终泛化门；性能方法冻结后仍需D-088规定的独立替代流/任务留出。
- 独立二次复审未发现剩余技术P0/P1；专项测试`24 passed`，完整回归`511 passed in 145.39s`。

## 机器产物

- `D:/brace-msi-generalization/GENERALIZATION-MATRIX-001-A6/summary.json`
- SHA-256：`BA850904FFE1A839CD839F87C0F6999A53751FE786E5BC12296A8E9F6B126F68`

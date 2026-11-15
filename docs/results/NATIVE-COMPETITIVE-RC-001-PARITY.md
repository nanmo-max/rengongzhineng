# NATIVE-COMPETITIVE-RC-001 Task 1

## Native逐状态等价

使用A/B/C三个官方父`checkpoint.npz`及各自完整`public/train.jsonl`，在相同样本顺序、父状态、seed、batch size、learning rate与1 epoch条件下比较官方`baselines/model.py::Model.fit`和`platform_runtime._NativeModel.fit`。

- A/B/C的epoch loss逐值相同。
- 全部`w1/b1/w2/b2`、Adam一阶/二阶矩、mean/scale逐数组相同。
- metadata、epoch、step及全训练集预测逐值相同。
- Native连续2 epoch与两次1 epoch在A/B/C上逐状态相同。
- 新增官方同级checkpoint验证：device、batch size、parameter count、learning rate/target scale及Adam二阶矩非法时失败关闭。

验证命令：

```text
D:/anaconda3/python.exe -m pytest tests/platform_runtime/test_platform_runtime.py tests/official_package/test_trainer.py -q
37 passed in 57.95s
```

## A4既有30轮Gate局部反事实

本节只读取既有`PLATFORM-NATIVE-CONTAINER-002-A2-FINAL`状态，不训练、不改变父链，也不把局部反事实串成伪造的最终成绩。

| 任务 | 正收益 | 达到5% | Anchor无退化 | 实际接受 | 若仅移除5%且仍要求Anchor无退化 |
|---|---:|---:|---:|---:|---:|
| A | 0/10 | 0/10 | 10/10 | 0/10 | 0/10 |
| B | 4/10 | 4/10 | 1/10 | 1/10 | 1/10 |
| C | 6/10 | 0/10 | 8/10 | 0/10 | 5/10 |

状态文件SHA-256：A `19E81E87...C0F8D62`；B `56ECF642...9AD3115`；C `A0100D48...6DEE2B3`。

结论：Native数值执行与官方训练器等价；`0.6.0rc1`性能缺口不是反向传播实现差异。A需要更有效候选，B需要处理当前适应与Anchor风险冲突，C的统一5%门结构性拒绝小步正收益。

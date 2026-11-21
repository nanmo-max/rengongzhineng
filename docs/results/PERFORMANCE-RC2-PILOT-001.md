# PERFORMANCE-RC2-PILOT-001 结果

- 实验ID：`PERFORMANCE-RC2-PILOT-001-A1`
- 结论：`COMPLETED_NEGATIVE_NO_PROMOTION`
- 机器摘要：`D:/brace-msi-competition/PERFORMANCE-RC2-PILOT-001-A1/summary.json`
- SHA-256：`A676ABBFDB8B42655E3C13480E75372D1868BA88F75FD25DAED0D3516E03071E`
- 数据边界：只读取A/B/C官方`public/train.jsonl`与父`checkpoint.npz`；`public/validation.jsonl`、密封数据、隐藏数据和官方试运行均为0。

## 方法

将train内部先冻结为十轮开发流与一份确认组。分类使用分层ID顺序，Bearing使用完整bearing留出，Engine使用完整`source_subset+unit`留出。每轮Gate只用于选择，不进入历史训练。RC2比较原生、类别平衡、近期加权回放、Huber、非对称回归和自适应标准化等互补候选，路由只依赖分类/回归合同。

自适应标准化使用首层精确仿射重参数化，训练前预测最大差异门为`1e-10`；专项测试8项通过。Smoke在两个身份不透明同格式任务完成8个候选，确认数据读取0次。

## 一次性确认结果

| 任务 | 主指标 | 静态父模型 | `core_robust` | RC2 | RC2相对对照有向相对收益 |
| --- | --- | ---: | ---: | ---: | ---: |
| A | Macro-F1↑ | 0.938433 | 0.938433 | 0.938433 | 0.000000 |
| B | RMSE↓ | 126.258498 | 163.985950 | 206.207286 | -25.7469% |
| C | RMSE↓ | 54.589901 | 54.883384 | 55.106327 | -0.4062% |

确认组每任务只评价一次，共3次；开发期`public/validation` 读取0次。A两条策略都未接受候选。B的RC2在开发Gate上接受8次，却在完整未见bearing确认组显著退化，说明当前Gate与候选对设备外推的代表性不足。C的RC2开发平均收益略优于对照，但确认仍小幅退化。

## 资源

| 任务 | 对照CPU秒 | RC2 CPU秒 | 对照峰值RSS | RC2峰值RSS |
| --- | ---: | ---: | ---: | ---: |
| A | 0.000 | 0.578 | 47.3 MiB | 47.4 MiB |
| B | 0.688 | 1.750 | 82.3 MiB | 84.2 MiB |
| C | 5.406 | 15.281 | 416.7 MiB | 420.3 MiB |

## 决策

四项预注册晋级门均未通过：三任务平均确认收益非正、不足2/3改善、存在主指标退化、开发最差阶段劣于对照。因此RC2不进入正式RecipeRegistry，不修改或重建`0.11.0rc1`镜像，不上传平台。这些结果是train内部代理证据，不是官方成绩。

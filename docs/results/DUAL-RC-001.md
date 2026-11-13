# DUAL-RC-001 本地Release Candidate验收

## 结论

`BRACE-MSI-0.5.0rc1`已完成本地可执行范围内的Release Candidate验收。镜像使用统一的身份盲数值表格训练逻辑：只按分类/回归接口、数值schema和父检查点工作，不以Gas、Bearing或Engine名称选择模型。A按冻结SafetyGate保留官方父模型；B/C在运行时从官方父检查点训练HGB候选并使用固定50/50父模型集成。

该结论是本地RC证据，不是平台“镜像可用”、模型校验、续训协议或正式评测通过。正式SDK事件、挂载和输出字段仍为外部阻塞。

## 验收结果

| 项目 | 结果 |
|---|---|
| 完整回归 | 329项通过 |
| 镜像 | linux/amd64，241,051,292字节，UID 10001 |
| 4核8GB断网 | 十轮受控闭环Smoke、B/C完整训练和B/C独立预测均通过 |
| 运行时模型产物 | B 239,914字节；C 200,616字节；均为单个`checkpoint.npz`且实际嵌入父检查点 |
| 禁入扫描 | 无数据、模型权重、密钥或受禁后缀被打包 |
| 依赖与编译 | 容器`pip check`和`compileall`通过 |
| Docker归档 | `docker save`生成，241,074,176字节；删除本地标签后`docker load`成功 |
| 官方试运行 | 0次 |

## 冻结性能边界

公开validation已经历史暴露，只用于冻结门控与跨平台等价性核验，不是独立测试或官方成绩。

- A：通用候选被拒，保留父模型；Macro-F1 0.714030、Accuracy 0.878617。
- B：父模型集成RMSE 675.010677、MAE 544.886250，均优于父模型681.159833/563.105841。
- C：父模型集成RMSE 49.336020、MAE 35.423070、NASA 2.4038e9，均优于父模型52.868573/38.899830/5.8234e9。

Linux重训产物的序列化哈希与Windows研究产物不同，但同一冻结算法在公开validation上的预测指标完全一致；未据此修改权重、模型池或参数。

## 上传入口与边界

- 归档：`D:/brace-msi-release/BRACE-MSI-0.5.0rc1/BRACE-MSI-0.5.0rc1-image-clean.tar`
- SHA-256：`e3cc5f1c3c2a879344632e083623001864c8dac380c6ebb87239ac5de9799747`
- 机器证据：[DUAL_RC_CONTAINER_ACCEPTANCE.json](DUAL_RC_CONTAINER_ACCEPTANCE.json)、[DUAL_RC_VERIFICATION.json](DUAL_RC_VERIFICATION.json)

上传后仍必须分别观察：上传状态、镜像可用状态、模型校验、续训协议和评测结果。任一未发生步骤不得写成通过。

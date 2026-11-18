# FORMAL-AGENT-OUTPUT-001 正式宿主输出契约修复

## 平台根因证据

O-PLATFORM-017完成A/B/C各10轮并结算输入14,289、输出7,680、合计21,969 Token，因此正式宿主模型调用已经发生。30轮全部为`host proposal was invalid`、候选数0；输出7,680恰为30×256，对应`0.10.3rc1`参赛代码自设的256 Token上限。原解析器还只接受整段纯JSON或完整围栏JSON。

## 最小修复

- 不再向`rnd.model()`传`max_tokens`，由官方SDK自动使用宿主每轮下发的完整`rnd.max_output_tokens`；不存在256或1024参赛者上限。
- 使用官方SDK支持的`response_format={"type":"json_object"}`与`enable_thinking=False`，提示只要求`train/retain`意图和简短理由。
- 删除未被执行层采用的Agent epoch/LR枚举要求；实际recipe继续由训练内部证据和受控执行层决定。
- 解析器接受回复中唯一合法JSON对象；多个对象、无对象或非法动作继续保留父模型并保存真实call ID。
- 训练器、portfolio、平台测量门、父链、预测和官方SDK均未修改。

## 红绿测试与回归

- 红灯：固定256预算、带外包装文字的唯一合法JSON、多个歧义JSON及未使用参数四类测试在旧实现上分别失败。
- 绿灯：Agent专项`10 passed`；正式运行与SDK专项`37 passed`；完整项目`469 passed in 155.18s`。

## 容器验收

- 镜像：`brace-msi:0.10.4rc2`，linux/amd64，UID/GID `10001:10001`，镜像大小81,188,642字节。
- A/B/C各10轮，30个宿主调用ID；候选提交分别为1/0/3；每任务5行独立预测；机器结果`valid=true`。
- 宿主替身强制核验传出的`max_tokens`等于start frame授权值，证明参赛代码未自设上限而由官方SDK补全。
- `pip check`为`No broken requirements found`；`/app`仅19个白名单运行文件，无PyTRiO、SwanLab、测试、数据、权重、密钥或报告。
- `docker save`后删除标签再加载，镜像ID保持`sha256:db223ed5a17bd70b9f2dbd88bddce032f4667292167d5c3232de8533bd2cd02e`。

## 产物

- 正式归档：`D:/brace-msi-first-principles-release/BRACE-MSI-0.10.4rc2-A1/harness.tar`
- 归档大小：81,206,784字节
- 归档SHA-256：`97948BD45502CFFE6082184DB06799A8E0FD8BE6BB008C048C7CE9DE47B335EA`
- 容器验收：`D:/brace-msi-first-principles-performance/FORMAL-AGENT-OUTPUT-001-A2-CONTAINER/acceptance.json`
- 验收SHA-256：`81F31E55802AD00BB5B604FE829744E892218C4E731A5413E51338F0806042B2`

`0.10.4rc1`包含用户否决的1024参赛者上限，验收被主动终止，只保留失败证据，禁止上传。以上均为本地验证，不代表平台已修复；下一次平台运行仍需确认有效提案、候选训练和非零Token。

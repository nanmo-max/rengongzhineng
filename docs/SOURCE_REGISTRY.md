# 证据与来源登记

## 使用规则

本文件只登记外部事实、本地可核验事实和待核实假设。研究决策登记在 [DECISION_LOG.md](DECISION_LOG.md)。事实变化时新增或更新状态，不删除旧证据。

## 官方已确认信息

### O-RULE-001 官方赛题规则PDF

- 来源：根目录 `“智训引擎”-工业制造场景下的模型训练与超参数优化-赛题规则(1)(1).pdf`
- SHA256：`DFE2972ECFEEE3845ADB917145F9F57477F9EC363B526524CB6A714BF961D3BE`
- 核验方式：2026-11-06视觉检查全部5页
- 事实：赛题要求工业模型在漂移流上自我迭代；可走持续微调或工具/技能驱动Harness路线；强调漂移监测、归因、实验优化、评估上线和回滚。
- 详见：[source_notes/OFFICIAL_RULES_EXTRACT.md](source_notes/OFFICIAL_RULES_EXTRACT.md)

### O-RULE-002 赛制与门槛

- 来源：O-RULE-001，第3-4页
- 事实：企业赛包括线上客观评测和前20队线下评审；封闭评测必须无人干预、完整记录、最终综合性能不低于静态基线。

### O-RULE-003 数据与环境

- 来源：O-RULE-001，第3-5页
- 事实：官方提供带标签公开训练/验证集、评测脚本和隐藏测试流；正式评测在统一离线环境运行；基础任务使用普通CPU即可完成；Python要求3.10及以上。

### O-RULE-004 提交与记录

- 来源：O-RULE-001，第3-4页
- 事实：提交模型配置与Harness系统镜像、完整云端实验记录依据、系统运行说明；实验需按规范完整记录。

### O-RULE-005 模型服务口径

- 来源：O-RULE-001，第3-4页
- 事实：规则PDF写明驱动Harness的大模型应为通过PyTRiO训练所得模型或PyTRiO的Qwen3.8-27B；企业赛阶段提供PyTRiO服务额度。
- 注意：该表述与后续宣讲转写中的模型名称冲突，代码不得写死，见H-002。

### O-RULE-006 安全与合规

- 来源：O-RULE-001，第5页
- 事实：禁止攻击平台、获取隐藏测试集、植入恶意代码和未授权外网访问；开源框架和预训练模型必须遵守许可证。

### O-PLATFORM-001 最新平台赛题目标与训练约束

- 来源：用户提供的`C:/Users/Administrator/Desktop/人工智能创新大赛/新增/76e834e27fd02b1ae37cae0ba07991c1.png`与`23a4f68815d88da876e2ef5c4aa1f39b.png`
- SHA-256：`FD7A8D62C11B7586569DCB5F6E8B3AB4CEC6B834FE8F4F9946A40592D28C691C`、`52088AFD4338548344D1110C93579229102CEF5F3F585CE9D63412C3A915C95F`
- 核验日期：2026-11-11，原图视觉核验。
- 事实：A为6类气体识别，主指标Macro-F1、Accuracy参考；B为轴承RUL分钟回归，RMSE/MAE越低越好；C为发动机RUL循环回归，RMSE越低越好并参考NASA非对称评分。工业模型从平台训练包检查点开始、CPU续训；每个数据集进行10轮优化，最终用隐藏测试评测。
- 边界：截图没有公开数据切分、初始权重文件内容、事件API或评分实现；当前仓库不能据此伪造平台检查点。

### O-PLATFORM-002 最新平台训练包摘要

- 来源：用户提供的`C:/Users/Administrator/Desktop/人工智能创新大赛/新增/47d3dfd0f296671679c10af7d140974d.png`
- SHA-256：`63DD5485261EE8B2CE6235A8C62A6329068EFB2C3BC13519F105945A1152775B`
- 核验日期：2026-11-11，原图视觉核验。
- 事实：平台训练包应包含训练代码、初始权重、公开训练/验证数据、公开任务与指标说明；A/B/C均为CPU任务。页面显示A模型参数4326、训练包1.08MiB；B模型参数865、训练包3.02MiB；C模型参数833、训练包7.36MiB。
- 本地状态：截至核验时，`新增`目录仅有4张PNG；Desktop与Downloads未发现对应平台训练包或初始权重。公开原始Gas、C-MAPSS和XJTU-SY数据仍可用于规则对齐开发。

### O-PLATFORM-003 最新平台评分与次数规则

- 来源：用户提供的`C:/Users/Administrator/Desktop/人工智能创新大赛/新增/76e834e27fd02b1ae37cae0ba07991c1.png`与`23a4f68815d88da876e2ef5c4aa1f39b.png`
- 事实：客观35分由平均性能提升15、最终阶段与恢复速度10、稳定性5、资源效率5构成；专家65分由方法30、实验分析15、安全与工业落地10、报告答辩10构成，另有最高10分加分。无人干预、完整过程、至少3次“读历史—做实验—依据结果决策”、不低于平台基线、材料完整可复现为要求。每队最多10次试运行且换版本不重置；正式评测最多2次，第二次需申请并取较高有效成绩；当前开放试运行不计正式成绩，正式开放时间和资源限额另行通知。
- 边界：截图没有给出35分各指标的数学公式，不能自创官方总分。

### O-PLATFORM-004 平台评测流程状态

- 来源：用户提供的`C:/Users/Administrator/Desktop/人工智能创新大赛/新增/407ec292b105c7f050fed05e20ea6900.png`
- SHA-256：`60FA118BE6CF5828A7C83BFF27D7A5B7416F61DC58CA61F76B53473FA9508D16`
- 事实：页面展示提交方案、标准运行、自动化评测、校验与发布四步；截图时作品提交页面尚未开放，提交版本与评测运行均为0。

### O-PLATFORM-005 官方A/B/C训练包

- 来源：用户2026-11-11提供的`C:/Users/Administrator/Desktop/人工智能创新大赛/训练包`。
- 核验日期：2026-11-11，只读清点、SHA-256、JSONL聚合审计、NPZ安全加载、随包测试及公开验证指标复算。
- 包：`cpu-a-guide-20261110-v1`、`cpu-b-rul-20261110-v1`、`cpu-c-guide-20261110-v1`，共64文件、60,328,967字节。
- 事实：A为128→32 tanh→6、检查点SHA-256 `FD1E08B2AAD08B2E9754F9B2DFDC029481C0DA7ECDEDCA0ABB0EC6FCC818C757`；B为34→24 tanh→1、检查点SHA-256 `C7D819FCEE9D25459C583B5FFDB35593D4A47B524ED152D0226BF81A283314B4`；C为24→32 tanh→1、检查点SHA-256 `98EC6E30E38AEE56CA15B7D624A8F412226D46FE97B170667A567601C700BC4E`。三者包含Adam状态、训练集标准化和回归目标缩放状态。
- 数据：A 445/1,244行且按Gas批次1/2隔离；B 7,032/1,679行且按9/3根轴承隔离；C 113,089/23,049行且按整台发动机隔离；训练/验证ID均无交叉。
- 复算：A Macro-F1 0.7140297220788709；B RMSE 681.1598326043113；C RMSE 52.86857256611151，与`training.json.validation_after`一致。
- 上游测试：A、C各9/9通过；B核心10项通过，另2项因未分发` scripts.package_baselines`报`ModuleNotFoundError`，属于包自包含性缺口，不影响已验证的续训入口。
- 边界：随包报告标记`purpose=development_reference`、`official_scoring_ready=false`；本地续训不是平台隐藏测试或正式成绩。原包保持只读，不将数据或检查点提交到Git/镜像。

### O-PLATFORM-006 官方首次试运行报告与提交状态

- 来源：2026-11-13登录后的官方平台提交/运行页面及用户导出的试运行报告；完整证据见`docs/source_notes/PLATFORM_TRIAL_V1_2026-11-13.md`。
- 已确认：试运行已使用1/10次、剩余9/10次；被运行的是旧提交v2，三任务均完成10轮且最终采用第1轮；平台结算输入/输出Token均为0。
- 隐藏指标：A Macro-F1 `0.413368`；B RMSE `691.660970`；C RMSE `56.220512`、NASA `48596667177.965034`。
- 用户确认：`BRACE-MSI-0.4.0rc1`尚未提交，不得把本次结果归因于RC4。
- 未确认：v2绑定的具体镜像编号、零Token由三层可回退路径中的哪一层触发；在新证据出现前保持未知。

### O-PLATFORM-007 镜像归档与续训检查点公告

- 来源：用户2026-11-13转发的官方发布消息；2026-11-15补充原始截图`新增/37c6cfe507269838bf8120f5c698ce83.png`与`新增/a0069606d5edf5d9464812984b64dc93.png`，SHA-256分别为`D0479B8506782A0092B154295E51EE9E6703E09EF756411CFCCAC969719160C8`、`082574AEA7D95923F8EF37FF5C7AB103E087AA575D3A670804E71E6DF1F0735A`；整理件见`source_notes/PLATFORM_IMAGE_AND_CHECKPOINT_NOTICE_2026-11-13.md`。
- 事实：上传文件必须由`docker save`生成；镜像状态需区分上传、导入/核验、可用、发布失败和过期；续训必须基于官方baseline及平台父检查点并保留真实历史；需独立预测入口；当前模型产物遵守`checkpoint.npz`且总量不超过64 MiB。
- 禁止：从头训练冒充续训、改后缀伪装模型、附带未使用父检查点、补造元数据或反复试运行已知不兼容版本。
- 边界：未提供checkpoint内部字段、父检查点路径、正式命令、状态API或错误码，仍由H-001约束。

### O-PLATFORM-010 旧提交完整试运行页面截图

- 来源：用户2026-11-15提供的`新增/fee684a2148fea20a384e3682f17f31c.png`、`新增/8be109b1ef14f53f50e232d8e261e2ed.png`、`新增/f6cd47c6479cb953b83c5417070a45e1.png`。
- SHA-256：`5F98EC037FFE4891DEBB107DFBEF325CCEB3006D3058339AB59942FC43A9BCA9`、`626476F2F57B41F567632DBFD3127BCCC277A9CECF6F4CA12408FCE1AC471F3B`、`AE320DBFEBE4ED08EB2BC5744DEF4B511DC6C8EF9BE75D64D3391ECA075FEDB8`。
- 已确认：旧试运行预测14,773条、输入/输出Token均0；A/B/C均完成10/10轮并最终采用第1轮。隐藏样本数分别4,886/200/9,687；隐藏指标分别为A Accuracy `0.506754`、Macro-F1 `0.413368`，B MAE `503.608618`、RMSE `691.660970`，C MAE `41.505914`、RMSE `56.220512`、NASA `48,596,667,177.965034`。
- 2026-11-15补充界面裁图SHA-256：`3A77139FB583ACA2F41B8AD6821A3EA5E5DAFF277C32669BE3DF5E1BD3FBC93E`。该图只补充页面布局与字段展示，不改变既有成绩事实或平台协议边界。
- 资源页面值：A/B/C CPU约189.948659/145.537861/658.938641秒；运行时约3,386.942601/1,990.544641/2,878.410072秒。截图中的公开验证逐轮指标随继续续训总体退化，因此平台保留第1轮。
- 边界：这是O-PLATFORM-006对应的旧提交，不是0.7.0rc1结果；截图没有公开隐藏样本、正式容器调用命令或评分公式。

### O-PLATFORM-011 薄桥接器兼容性预检反馈

- 来源：用户2026-11-16转发的平台兼容性预检原文；尚无可下载的桥接器源码或正式SDK文档，证据等级为平台运行反馈。
- 已确认：本次草稿适配器本身有缺陷，因此尚未形成对镜像兼容性的有效判定；反馈认可`platform_runtime.py`、`pytrio_agent.py`以及平台侧`workspace_io.py`所暴露能力在职责上可桥接。
- 已指出的映射要求：每轮调用`start_round`时输出挂载必须为空；平台start frame的`parent_checkpoint_sha256`位于顶层；十轮预算不能只靠未经证明的隐式轮次推断；retain/未部署轮也必须声明一个有效模型产物；命令应配置为不含mode的argv前缀，由桥接器追加具体操作。
- 已知限制：空`/data`和`/previous`无法完成Native行为预检，只能做静态入口检查；平台侧表示将重写薄桥接器并检查镜像digest。
- 边界：反馈没有提供`workspace_io.py`源码、start frame完整schema、artifact declaration完整schema或正式调用生命周期。仓库只能增加协议无关的显式校验与收据，不能自行实现或声称官方私有桥接协议。

### O-PLATFORM-012 0.8.1rc1二次预检不完整反馈

- 来源：用户2026-11-16复制的平台预检显示文本；平台页面只保留该段，尾部在`Because native PyTR...`处截断，无额外日志或错误码。
- 已确认：预检明确写出`I stopped without claiming success`；静态检查认可Native包、父checkpoint原生续训、独立预测入口、可配置PyTRiO调用链及替身transport测试，但没有完成真实平台挂载、真实在线PyTRiO或十轮行为运行。
- 本地可复现差异：首个完成平台试运行的历史镜像默认`CMD ["--help"]`；`0.8.1rc1`默认`CMD ["start"]`。后者在无四挂载裸启动时尝试创建`/workspace`，非root容器以`PermissionError`和退出码1终止。
- 边界：截断文本不足以证明这就是平台停止的唯一原因；修复无输入启动后仍必须由平台真实导入、挂载、在线模型和试运行判定兼容性。

### O-PLATFORM-008 旧提交的父检查点续训拒绝提示

- 来源：用户2026-11-15提供的平台截图，并明确说明这是“之前那个”旧提交；整理件见`source_notes/PLATFORM_REJECTION_PARENT_CONTINUATION_2026-11-15.md`。
- 原始截图SHA-256：`F51B3CB2EB30F157ABF83E1E71FDE1F2629728BEF57158B3B2092C9F2D2F783D`。
- 事实：平台实际拒绝了一个未满足题意的旧提交，提示必须基于官方baseline和平台父检查点真实续训；不能从头训练另一套模型替代baseline；`retain`仅是不训练并保留父模型的例外。
- 边界：截图不对应`0.5.0rc1`，没有暴露内部字段、旧镜像ID或正式SDK参数；不得写成`0.5.0rc1`已被平台拒绝。

### O-WEB-001 官方赛题页

- URL：https://bjcsaiic.zsyqkj.com/topics/2026/9
- 检查日期：2026-11-06
- 用途：赛题入口；动态网页未在仓库保存快照，关键规则以O-RULE-001为准。

### O-WEB-002 官方资料站

- URL：https://bjcsaiic.zsyqkj.com/resources?category=16
- 检查日期：2026-11-06
- 事实：资料站列有2026-10-27版赛题规则，并提示以最新发布版本为准。

### O-WEB-003 大赛通知与日程

- URL：https://bjcsaiic.zsyqkj.com/notice/1
- URL：https://bjcsaiic.zsyqkj.com/schedule
- 检查日期：2026-11-06
- 事实：官方通知口径包含11月26日至12月5日企业分赛场和12月26日线下决赛。若后续网站更新，需重新登记证据。

## 宣讲信息

### B-SLIDE-001 五步闭环与两条路线

- 来源：根目录 `1304cc564273d02fc101e5316e4423fe.jpg`
- SHA256：`91E1DC3157878E7B4CAA8D86170DE8FFA44DBE2F9B9385E475D5919D5694B318`
- 事实：宣讲展示“漂移监测、诊断归因、实验优化、评估上线、回滚”五步闭环，以及大模型Harness和传统持续微调两条路线。

### B-SLIDE-002 赛题背景

- 来源：根目录 `88127795c878a57dc63dbddfeb31af15.jpg`
- SHA256：`38BAFAD693BCF4F7AB518A4D43DE68A8BC038C48C2AF8E38B618A80921837207`
- 事实：宣讲强调工业数据持续漂移和工业模型自进化任务。

### B-SLIDE-003 评分权重

- 来源：根目录 `ba80dbeca694b0030c8c4d042357407b.jpg`
- SHA256：`A68D5E88DFCF1337F6A69FC58A84C6E1F338FD584E6189EC3C45B21B75D4D5DF`
- 事实：宣讲幻灯片显示客观35分、主观65分；主观包含方法设计与技术路线、实验规范与分析、安全可控与工业落地、报告与答辩。

### B-PLATFORM-001 平台与环境宣讲口径

- 来源：用户提供的2026-11-06宣讲记录及截图摘要
- 事实：预计11月9日平台上线；评测环境4核8GB CPU、无GPU、无公网，镜像不超过2GB，不得打包模型权重或Embedding；允许访问内部模型服务。
- 状态：等待正式平台规范确认。

### B-DATA-001 三个公开任务与B包

- 来源：用户提供的宣讲记录
- 事实：公开榜建议同时处理气体传感器、轴承退化和发动机寿命任务；B包为同领域但接近新任务的串行数据流。
- 状态：等待数据包和SDK确认。

### B-ITER-001 三次迭代

- 来源：用户提供的宣讲记录
- 事实：系统至少完整记录三次迭代过程。
- 状态：被拒候选是否计数、是否要求部署尚未确认。

### B-RSI-002 受控递归自我改进宣讲截图

- 类型：宣讲材料，不是正式SDK契约。
- 原件：`C:/Users/Administrator/Desktop/人工智能创新大赛/ppt/` 下13张JPG；逐文件SHA-256与字节数见 `source_notes/RSI_LECTURE_EVIDENCE_2026-11-13.md`。
- 可确认：Harness必须形成漂移监测、诊断、实验、门控部署/回滚和历史反馈闭环；宣讲明确区分工业模型执行层迭代与策略/工具决策层迭代；至少三次完整“历史→假设→实验→决策”属于最低门槛。
- 边界：不确认正式SDK字段、批次目录、被拒候选计数、影子推理权限、完整评分公式或隐藏任务结构。

### B-SWANLAB-001 SwanLab宣讲要求

- 来源：用户提供的宣讲记录
- 事实：宣讲要求使用SwanLab记录被训工业模型的完整训练过程并设为公开。
- 状态：离线环境同步和私有数据边界待正式规范确认。

### B-SCHEDULE-001 宣讲时间口径

- 来源：用户提供的宣讲截图与记录
- 事实：11月9日平台上线、11月13日校赛推荐、11月15日至12月5日企业赛、12月26日总决赛。
- 注意：与统一通知及用户先前获得的校内11月16日节点冲突，见H-005。

### B-RESOURCE-001 平台额度

- 来源：用户提供的宣讲记录
- 事实：进入企业赛阶段的队伍预计获得500元平台代金券。
- 状态：尚未发放，不计入当前可用预算。

## 本地与用户确认事实

### L-DATA-001 Gas Sensor Array Drift代理数据

- 文件：`dataji/gas+sensor+array+drift+dataset.zip`
- SHA256：`91E8F466F202E7A093D657673CE47311C3E90416F7DF3057966058961C351FE4`
- 本地状态：已解压10个`.dat`批次，共13,910行、128维、6类；只读审计与1–3/4–7/8–10冻结切分通过；未运行训练。证据见`source_notes/PROXY_DATA_AUDIT.md`。

### L-DATA-002 NASA C-MAPSS代理数据

- 文件：`dataji/6.+Turbofan+Engine+Degradation+Simulation+Data+Set.zip`
- SHA256：`C9C5DEC12A945A82E8BB4446589D7FB3CC057B5E5D81FA1A12E25EE9912AD3B2`
- 本地状态：外层压缩包和内层`CMAPSSData.zip`存在；包含FD001-FD004训练、测试及RUL文件。FD001只读审计确认20,631行、100台发动机、24维输入；按发动机60%/20%/20%冻结分组；未运行训练。证据见`source_notes/PROXY_DATA_AUDIT.md`。

### L-DATA-003 轴承代理数据

- 本地状态：未发现轴承数据文件。

### L-HW-001 开发机

- 来源：用户确认及本机检查
- 事实：Windows 10、RTX 4060 Ti 8GB、Ryzen 7 7800X3D；D盘此前检查约307GB可用；当前未检测到Docker。

### L-TEAM-001 团队与资源

- 来源：用户确认
- 事实：技术负责人承担核心技术并主要使用Codex；三名大二队员掌握基础知识，负责低风险技术任务和展示材料；指导教师尽量少打扰；个人额外预算约100元。

### L-AUTH-001 本地代理训练授权

- 来源：用户2026-11-06当前指令
- 事实：允许在已下载Gas和C-MAPSS数据上先核验结构与切分，再开发和运行分类/回归本地闭环、Smoke Test、完整基线及至少三次真实候选迭代。
- 边界：正式SDK继续阻塞；代理结果不得表述为官方成绩；不得修改原始数据、使用未来批次或提交最终模型权重。

### L-AUTH-002 完整候选系统本地开发授权

- 来源：用户2026-11-07当前指令
- 事实：允许连续完成无需官方SDK的统一Harness、CPU模型池、有限HPO、恢复、Docker、CLI、静态报告和模拟正式评测，并可在合法开发段开展必要训练。
- 边界：原密封段锁保持有效；未知官方字段、评分和标签权限不得编造；合成第三任务只能作为工程验收，不能冒充官方或真实轴承数据成绩。

### L-AUTH-003 Release Readiness授权

- 来源：用户2026-11-07当前指令
- 事实：`LOCAL-FORMAL-SIM-001-A2`已通过独立机器验收；允许在`task/core-001`继续完成真实容器、干净依赖、SwanLab与正式SDK接口准备及最终交付审计。
- 边界：不重复代理密封实验，不扩充算法，不重新设计架构，不修改A1 INVALID与A2有效历史，不合并`main`；无法完成的外部依赖必须标记`BLOCKED`。

### L-AUTH-004 正式数据接入授权

- 来源：用户2026-11-10当前指令
- 事实：用户将`C:\Users\Administrator\Desktop\官方`中的Gas、C-MAPSS和XJTU-SY指定为本赛题三个官方公开数据集，并授权开始正式接入；用户允许对与既有数据完全相同的数据复用已有工作，避免无意义重复训练。
- 边界：用户确认可以解除“数据尚未到达”这一事实阻塞，但不能替代缺失的组委会数据清单、官方切分、指标、评分脚本、SDK和许可证证据。

### L-DATA-004 用户指定的三套官方公开数据原件

- 本地路径：`C:\Users\Administrator\Desktop\官方`
- 核验日期：2026-11-10
- 事实：Gas 10批与既有`L-DATA-001`逐文件SHA-256相同；C-MAPSS的FD001-FD004训练、测试、RUL和readme与`L-DATA-002`内层压缩包逐文件SHA-256相同；XJTU-SY六个RAR5分卷完整性测试通过，包含15个轴承、3种工况和9,216个唯一双通道振动CSV。多卷列表的5个跨卷重复项已按路径去重。
- 证据：[source_notes/OFFICIAL_DATA_INTAKE_2026-11-10.md](source_notes/OFFICIAL_DATA_INTAKE_2026-11-10.md)
- 边界：目录没有组委会manifest、比赛任务定义、指标、官方切分或许可证文件；“官方数据”身份目前同时依赖用户确认与原始数据指纹，正式实验协议仍待H-006解决。

### L-DATA-005 新增三套未知任务泛化模拟数据

- 来源：用户2026-11-15放入`C:/Users/Administrator/Desktop/人工智能创新大赛/模拟正式数据集`；本地只读资料，不是赛事官方隐藏数据或正式训练包。
- 电池：NASA Battery Aging Archive六个ZIP，包含多个电池的MAT循环记录；合法监督信号取放电循环`Capacity`，重复电池ID必须按内容来源去重。
- 液压：UCI Condition Monitoring of Hydraulic Systems，2,205个60秒循环、17类传感器文件及`profile.txt`；本实验预注册目标为文档明确较难的液压蓄能器状态分类，输入只来自传感器统计量，不使用其余profile列。
- 铣削：NASA/UC Berkeley Mill数据，167次运行、16个case、六路9,000点传感器；合法回归目标为实测后刀面磨损`VB`，缺失VB记录不得插值后冒充实测标签。
- 边界：三者均缺少赛事父checkpoint、正式任务manifest和评分公式；只能生成明确标记的模拟父模型并作本地泛化复演，不得写成官方成绩。

### L-AUTH-005 正式实验记录阶段边界

- 来源：用户2026-11-11当前指令
- 事实：比赛实验记录指最终完成品中的工程模型正式重新训练记录；当前数据审计和接入准备阶段不需要修改或运行SwanLab。其余平台、任务和记录规范将由比赛平台提供。
- 边界：当前仍保留本地私有审计和已有SwanLab适配代码，但不生成、同步或公开新的SwanLab运行；只有最终工程模型、官方协议和平台规范冻结后才执行正式记录重训。

### L-AUTH-006 XJTU-SY本地训练授权

- 来源：用户2026-11-11当前指令
- 事实：允许暂不等待正式平台，使用新增XJTU-SY数据完成当前阶段的本地模型训练；要求串行安排实验、确认前三个实验轮次正常后让独立后台进程继续运行，并自行处理普通技术问题。
- 边界：本轮不运行或修改SwanLab；结果属于比赛平台接入前的本地开发证据，不能冒充官方评分。原始RAR只读，派生解压、特征缓存和训练产物写入独立运行目录。

### L-AUTH-007 最新官方资料接入与无人值守训练授权

- 来源：用户2026-11-11当前指令
- 事实：用户确认`C:/Users/Administrator/Desktop/人工智能创新大赛/新增`是比赛前全部训练相关官方信息；未补充内容仅涉及展示，可暂不处理。用户授权自动完善既有计划、训练、普通故障处置、汇总分析与后续迭代，并要求任务脱离会话继续运行，只检查前三个串行实验，之后无需持续监控，可约10分钟检查一次。
- 边界：授权不把缺失的平台训练包或初始权重变成已取得事实；当前本地重建检查点必须明确标注，不消耗平台10次试运行配额，不上传或提交作品。

### L-AUTH-008 统一策略优化授权

- 来源：用户2026-11-11当前指令
- 事实：用户要求停止只完成框架，使用Gas、Bearing和Engine三个公开任务共同优化一套共享策略；保留统一EvidenceRouter、ActionPolicy、BudgetLedger和SafetyGate，允许TaskAdapter按任务类型、特征维度和指标方向适配，但禁止按数据集名称、任务身份或测试批次硬编码动作。允许多轮自动实验、共享参数调整、无效机制淘汰和跨任务轮换留出验证，不使用官方十次测试机会。
- 补充：用户指定每个任务采用前期轮次训练、中间轮次调参、最后轮次独立测试。
- 边界：Gas批次8—10和FD001发动机81—100已在历史实验中查看，只能作为对本轮程序隔离的历史暴露末期复核；XJTU三个密封轴承截至授权时仍未进入特征缓存、训练或指标，可在配置冻结后作为真正未见确认集。原始数据、历史冻结实验和RC标签不得修改。

### O-SWANLAB-001 SwanLab官方离线与同步接口

- 来源：SwanLab官方文档`https://docs.swanlab.cn/api/py-init.html`、`https://docs.swanlab.cn/api/cli-swanlab-offline.html`及API索引；检查日期2026-11-07
- 事实：Python SDK支持`mode="offline"`本地记录、`on_online_error="offline"`降级、`public`可见性参数；官方CLI提供`swanlab sync`将本地日志同步到云端或私有部署。
- 边界：比赛要求的字段、公开项目命名、认证注入和无公网评测后的正式同步流程仍属H-004，不由通用SwanLab文档解除。

### O-SWANLAB-002 SwanLab新版记录器版本要求

- 来源：用户2026-11-13提供的SwanLab工作区官方页面截图；页面地址`https://swanlab.cn/space/~`。
- 事实：页面公告要求新实验使用SDK 0.10.0及以上版本；本机冻结环境为SwanLab 0.10.4并已登录工作区`nanmo-max`。
- 边界：该公告只确认通用记录器版本，不确认比赛专用项目名称、必填字段、公开范围或无公网评测后的同步责任，H-004仍保留。

### O-PYTRIO-001 PyTRiO官方训练与推理接口

- 来源：`https://docs.pytrio.com/docs`、`/docs/quick-start`、`/docs/guide/train`、`/docs/guide/sample`、`/docs/advanced/openai`与`/docs/advanced/configuration`；核验日期2026-11-12。
- 事实：官方客户端可通过`pip install pytrio`安装；`ServiceClient`支持查询模型、创建Sampler与LoRA训练客户端；提供`sample`、`forward_backward`、`optim_step`及权重保存/恢复；支持`PYTRIO_API_KEY`、`PYTRIO_BASE_URL`和OpenAI兼容端点。快速开始当前示例列出`Qwen/Qwen3.6-27B`与`Qwen/Qwen3.5-4B`。
- 边界：通用文档不确认比赛环境的Base URL、凭据注入、模型白名单、Token计量或十轮评测事件协议；正式实现必须运行时配置并核验，不写死公开端点或示例模型列表。

### O-PYTRIO-002 当前账户SDK与模型能力实测

- 来源：本机`pytrio 0.2.9`、`trio env show`、登录后的`ServiceClient.get_supported_models()`只读调用，以及官方`SwanHubX/pytrio-skill` v0.2.3；核验日期2026-11-12。
- 事实：本机已登录且未在仓库读取/保存凭据；当前服务实时返回`Qwen/Qwen3.5-4B`和`Qwen/Qwen3.8-27B`两项模型。SDK签名确认LoRA客户端支持`base_model/rank/seed`，`save_weights_for_sampler(name, ttl_seconds=None)`返回用于Sampler的持久化权重结果。
- 边界：模型列表只代表当前账户在核验时可见能力，不等于正式评测容器白名单；只读能力查询不证明账户有可用付费额度，也不证明训练、保存或平台提交已经成功。

### O-PAPER-001 不平衡在线持续学习与类平衡回放

- 来源：Chrysakis & Moens, *Online Continual Learning from Imbalanced Data*, ICML 2020，PMLR 119:1952–1961；PMLR论文与补充材料，核验日期2026-11-12。
- 事实：论文针对时间相关且类别不平衡的在线数据流，提出class-balancing reservoir sampling，并报告其在多数据集/架构上优于所比较的memory population方法。
- 代码与许可证：论文/PMLR页面未给出作者官方代码仓库；当前检索亦未找到可核验官方实现。因此不满足D-037的官方开源代码复现准入，不能作为正式注册插件。
- 本项目使用边界：`PERF-A-REPLAY-001`只独立实现一个确定性class-balanced replay强基线，用于验证问题机制，不声称复现论文数值或代码。

### B-PLATFORM-002 平台模型提交校验答复

- 来源：用户于2026-11-12转述的参赛平台教师答复与已完成校验结果。
- 事实：同一API Key和镜像选择Qwen3.5-4B基础模型可通过提交校验；LoRA Sampler先前校验失败的原因是权重未正确持久化，持久化后已解决；教师确认其余所问事项不存在额外限制。
- 证据等级：平台支持沟通与实际校验结果，高于推测但不替代公开SDK/比赛书面规范。
- 边界：不得在仓库记录API Key或真实凭据；Sampler路径、模型名和服务地址均由运行配置注入。

### B-PLATFORM-003 持久化Sampler重复校验失败

- 来源：用户于2026-11-13在参赛平台再次执行“持久化Sampler微调权重”提交校验后的直接观察。
- 事实：持久化Sampler方案仍显示“未通过”；同平台选择`Qwen3.5-4B`基础模型可通过校验。
- 边界：平台未提供可定位到凭据、权重持久化、Sampler可见性或校验接口的详细错误，因此不得声称已查明Sampler失败的具体根因。该事实只支持将基础模型作为当前可提交路线。

### L-AUTH-009 正式路线锁定与连续执行授权

- 来源：用户2026-11-12当前指令。
- 事实：正式路线锁定为“Qwen3.5-4B PyTRiO Agent + BRACE确定性Harness + 官方A/B/C工业模型 + 经过验证的开源优化方法”；统一Harness工作流，允许三个任务独立模型、参数、动作和历史；授权连续完成文档、P0集成、公开开发优化、论文复现、十轮闭环、对照和交付准备。
- 边界：不修改原始训练包或RC标签，不消耗官方十次试运行进行基础调试；付费、密钥、正式平台权限和缺失接口仍需外部授权或材料。

### L-AUTH-010 PyTRiO有界SFT付费授权

- 来源：用户2026-11-12确认PyTRiO余额已充值10元，并要求节约使用。
- 事实：授权执行已经预注册的`PYTRIO-SFT-001-A1`远程基础评测、Qwen3.5-4B rank 8/3 epoch SFT、持久化Sampler保存和同一留出复评。
- 预算边界：官方主页当日显示Qwen3.5-4B训练/采样4.54元/M token、prefill 1.49元/M token；按每字符一token和采样上限计算的保守估算约0.65元。不得扩展数据、epoch、评测样本或另起A2；若A1失败，先保留证据并重新请求授权。

### L-AUTH-011 PyTRiO连续自主实验授权

- 来源：用户2026-11-12在获知A1失败、修复和预计成本后明确要求继续完成，自动规划和实验，不再逐次确认。
- 事实：授权在原10元总预算内自主执行A2及必要的低成本修复重试、持久化Sampler验证、Harness接入和三任务受控对照；普通技术错误自行诊断、保留失败证据后继续。
- 边界：累计PyTRiO费用不得超过10元；不得使用官方十次评测机会、扩大A/B/C公开验证调参、修改RC2历史或绕过SafetyGate。若余额/累计预算不足、需要平台提交或产生重大路线变化，才重新请求用户。

### L-AUTH-012 提交材料、GitHub与SwanLab最终记录授权

- 来源：用户2026-11-13明确要求继续完善、将仓库上传到`https://github.com/nanmo-max/rengongzhineng.git`并生成SwanLab记录。
- 事实：授权在RC3与参数冻结不变的前提下，制作作品说明书、推送脱敏源码分支、执行一次最终工程训练记录并同步SwanLab。
- 边界：不把API Key、完整Sampler路径、原始数据、模型权重、逐样本标签或可逆特征写入Git/SwanLab；本次重跑只用于记录，不能继续选型、调参或冒充隐藏评测；main是否合并仍需保持既有稳定边界。

### L-AUTH-013 原生竞争候选当日冲刺授权

- 来源：用户2026-11-15明确批准冲刺方案并要求当天完成可提交平台检验的完整成品，包含SwanLab、PyTRiO和镜像。
- 授权：在独立分支执行Native差分等价、冻结日程迁移、train内部Gate修正、最小真实PyTRiO验收、最终SwanLab聚合记录、Docker构建及归档。
- 边界：不改写`0.6.0rc1`、历史证据或原始训练包；不消耗官方试运行进行基础调试；付费调用沿用既有总预算和密钥安全要求，外部服务不可用时不得伪造通过。

### L-AUTH-014 性能优先与成熟方法授权

- 来源：用户2026-11-15在冲刺执行中明确要求性能优先，方法不限于论文，可采用公开认可的成熟方法，并关注参数量与资源。
- 授权：在Native等价门通过后，使用train内部证据选择CPU友好、父checkpoint兼容的损失、权重、调度或Replay机制。
- 边界：不改变官方模型schema或从头训练替代父模型；不以创新包装替代实测提升；不重开公开validation调参。

### L-EVIDENCE-001 完整系统本地模拟证据

- 来源：`LOCAL-FORMAL-SIM-001`，执行提交`ce3e907840ae4652be568d1b1eedc4e547702cec`
- 本地路径：`artifacts/formal_simulation/LOCAL-FORMAL-SIM-001/run-ce3e907/`
- 状态：`INVALID`（2026-11-07最终自审发现真实候选计数缺陷）
- 事实：运行完成且4核/RSS/协议证据有效，但合成任务的4个记录中含2次未实际拟合的注入失败，只有2次真实HPO拟合，不满足每任务至少3次真实候选。
- 边界：`proxy_only`；没有使用已消费密封段；内存仅观测未容器强制；Docker镜像未构建；SwanLab仅本地待同步队列；不是官方成绩。

### L-EVIDENCE-002 修复后完整系统本地模拟证据

- 来源：`LOCAL-FORMAL-SIM-001-A2`，执行提交`7ef3829781a96b9ebef01154063680c8bc65782a`
- 本地路径：`artifacts/formal_simulation/LOCAL-FORMAL-SIM-001/run-7ef3829/`
- 事实：Gas、FD001与合成轴承流均完成4批次；真实训练候选分别4、4、3；独立验收动作计数增量7、回放1、有限HPO3；4核亲和性生效，操作边界RSS 148,017,152字节。
- 验收：`validate_simulation_output(..., minimum_candidates=3)`返回`valid=true`；公开日志白名单、唯一批次提交和稳定模型加载通过。
- 边界：同L-EVIDENCE-001；不使用INVALID A1作成功证据；不是官方成绩或真实轴承性能证据。

### L-EVIDENCE-003 官方训练包本地开发证据

- 来源：`OFFICIAL-PACKAGE-DEV-001`，执行提交`34098bf42be4bb00c9323351f1b7067bb2d85972`
- 本地路径：`D:/brace-msi-official-package/OFFICIAL-PACKAGE-DEV-001/`
- 事实：A/B/C三个Smoke与六个策略作业完成；单次固定低成本续训对照（内部ID`performance_triggered`）与BRACE各任务均10个候选适应决策轮，BRACE每任务3个真实候选；共15个训练候选、15次成功训练器验证加载、33次候选指标计算，机器验收`valid=true`。A/B上BRACE与低成本对照主指标相同但资源更高；C上BRACE公开验证RMSE为51.889566，优于低成本对照52.350178和静态52.868573。
- 资源：15候选累计CPU 64.781秒、候选墙钟69.547秒、峰值RSS 256,630,784字节；运行根约1.19MB。
- 边界：`official_package=true`、`official_scoring_ready=false`；轮次不是真实漂移流；反复公开验证用于门控，结论需隐藏评测确认。未运行SwanLab、平台SDK、外部API或隐藏测试。

### L-EVIDENCE-004 Gas因果持续更新开发证据

- 来源：`PERF-A-REPLAY-001`，执行提交`cb6d1874c01f80e5d23b53086b1f6cd91757300c`。
- 运行根：`D:/brace-msi-performance/PERF-A-REPLAY-001/`；`state.json` SHA-256 `E9E99F42A1B1C3D45F4BE69378F8686270EA48DDB729DC8CF9598A3792383DC3`。
- 事实：Batch 2—5先预测后反馈开发流中，`current_only`平均Macro-F1 0.587581，均匀与类平衡回放均0.580352，未达到相对简单策略+0.005门。Batch 6—7冻结确认上简单策略0.469553，两回放均0.439323。
- 审计：18个预测轮、15个真实候选、5个上线、10个拒绝；累计CPU 10.1875秒、候选墙钟11.326秒、峰值RSS 57,888,768字节；父链、派生切分不交叉和禁止批次审计通过。
- 边界：Batch 6—7在既往代理实验中已暴露，不是真正未见确认；Batch 8—10未加载；官方试运行、PyTRiO与SwanLab使用均0。

### L-EVIDENCE-005 RC2冲刺候选与发布验收

- 来源：`REGRESSION-SPRINT-001`、`SPRINT-HARNESS-001`及`docs/results/RC2_VERIFICATION.json`。
- 事实：B/C有界矩阵均9/9成功并冻结；三任务各完成10轮、3次真实候选和7次no-op，机器复算有效。运行时代码与全新venv均221项测试通过，wheel版本0.2.0rc2，`pip check`与编译检查通过。
- 边界：全部性能指标来自历史暴露公开开发/validation，不是隐藏测试或官方成绩；官方试运行、真实PyTRiO、SwanLab正式记录均为0。镜像仅有静态上下文证据，实际Docker/4核8GB仍BLOCKED。

### L-EVIDENCE-006 A3 PyTRiO Sampler与三任务竞争候选

- 来源：`PYTRIO-SFT-001-A3`与`PYTRIO-COMPETITIVE-001-A1`；执行提交分别基于`9db3035`/`6085c73`及`0b556c0`/`c078c5c`。
- 本地路径：`D:/brace-msi-pytrio/PYTRIO-SFT-001-A3/`、`D:/brace-msi-pytrio/PYTRIO-COMPETITIVE-001-A1/`。
- 事实：A3完成36/36远程步骤并生成持久化Sampler，新留出schema/action/tool/budget/policy均100%；A/B/C真实首轮3/3主动更新。竞争运行三任务各10轮/3候选并逐项`valid=true`，最终A/B/C为0.725695 Macro-F1、637.180224 RMSE和51.635999 RMSE。
- 资源与安全：总输入/输出Token为20,362/2,272；0守卫覆盖、0服务回退；2次预算耗尽后的额外建议在训练前拒绝。A3之后按D-043停止LLM调参。
- 边界：公开验证历史暴露，性能来自已冻结任务参数与门控，不能归因为LLM单独增益；完整Sampler路径和凭据不进入Git；官方试运行和SwanLab使用均0。

### L-EVIDENCE-007 RC3真实容器与干净环境验收

- 来源：`docs/results/RC3_CONTAINER_ACCEPTANCE.json`、`docs/results/RC3_VERIFICATION.json`。
- 事实：`brace-msi:0.3.0rc3`为linux/amd64、240,579,085字节、UID10001；PyTRiO0.2.9可导入，Torch未安装，镜像无数据、模型权重或密钥。4核8GB断网双协议Smoke完成；`docker save`归档240,602,112字节且重载通过。
- 回归：最终代码246项、打包前全新venv243项测试通过，`pip check`和编译通过；发布工具定向15项通过。
- 边界：属于本地Harness交付证据，不是官方隐藏评测或SwanLab正式训练记录。

### L-EVIDENCE-008 最终SwanLab工程记录与GitHub发布

- 来源：`docs/results/SWANLAB-FINAL-001.md`、SwanLab公开API、Git远端`https://github.com/nanmo-max/rengongzhineng.git`；核验日期2026-11-13。
- 事实：A/B/C冻结工作流各完成10轮/3候选且`valid=true`；SwanLab公开项目`nanmo-max/brace-msi-final`包含3个`FINISHED`实验，每项10条聚合记录。`task/core-001`已推送到GitHub，RC3冻结提交标签`brace-msi-v0.3.0-rc3`已推送。
- 边界：结果使用历史暴露公开验证，不是隐藏评测；远端main未合并；仓库尚未由权利人选择项目级许可证。

### P-PAPER-001 Gas漂移知识蒸馏

- 论文：Lin, J.; Zhan, X. *Sensor-Drift Compensation in Electronic-Nose-Based Gas Recognition Using Knowledge Distillation*, Informatics 13(1), 2026, DOI `10.3390/informatics13010015`。
- 作者代码：`https://github.com/abob7/gas-drift`，仓库声明MIT；论文正文明确链接该代码。
- 已核实贡献：UCI Gas Sensor Array Drift上比较KD、DRCA与KD-DRCA，报告KD相对基线最高约15% F1改善。
- 适配风险：仓库README声明在全部批次上拟合全局scaler，不符合本项目因果预处理；只能复现KD核心并改为历史/训练折拟合，不能把修改版冒充逐行原样复现。期刊分区尚无项目内权威JCR证据，不标记为一区。

### P-PAPER-002 C-MAPSS可解释树模型集成

- 论文：Özcan, H. *Interpretable Ensemble Remaining Useful Life Prediction Enables Dynamic Maintenance Scheduling for Aircraft Engines*, Scientific Reports 15, 39795, 2025, DOI `10.1038/s41598-025-23473-2`。
- 作者代码：`https://github.com/hkmtcn/interpretable-rul-maintenance`；README声明代码MIT、图表/派生数据CC BY 4.0，但GitHub页面许可证徽标与README表述需要在复制代码前以实际`LICENSE`文件再次核对。
- 已核实贡献：在C-MAPSS上组合LightGBM、CatBoost与Gradient Boosting，作者声明普通CPU足以运行。
- 适配边界：论文RMSE与本比赛逐行公开validation协议不可直接比较；本轮只复现树模型互补集成思想，使用现有scikit-learn实现，不复制仓库代码。

### P-PAPER-003 Hyperband资源分配

- 论文：Li, L. et al. *Hyperband: A Novel Bandit-Based Approach to Hyperparameter Optimization*, JMLR 18(185), 2018。
- 已核实贡献：以Successive Halving分配迭代/样本等资源并提前停止劣质配置，论文报告在多类问题上相对常见调参方法获得数量级加速。
- 适配边界：本轮实现确定性有限Successive Halving，不复制第三方非作者实现，不扩展为BOHB。

## 待核实假设与冲突

### O-PLATFORM-009 平台原生运行时挂载与不兼容诊断

- 来源：用户转发的2026-11-15平台实际兼容性诊断；尚无独立SDK文档文件，证据等级为平台运行反馈。
- 已确认运行时输入：训练容器只提供`/data`（逐样本`id`、`inputs`、`answer`）、`/previous/checkpoint.npz`、`/workspace`与`/output`。
- 已确认失败原因：`BRACE-MSI-0.5.1rc1`发布入口先要求完整官方包根并执行`baseline-info.json`、`training.json`、源码、公开切分与整包树哈希审计，随后从包内启动`baselines.train`；上述文件不在平台运行时挂载中，因此训练前必然失败。平台结论为接口条件不满足，不是选手违规。
- 已确认修正方向：作品需要直接消费`/data`和`/previous/checkpoint.npz`的原生训练与预测入口；不得要求平台补齐仅用于本地开发审计的包文件。
- 边界：反馈没有给出`/data`的实际文件名、调用命令、进程协议或`describe/start/submit`的精确JSON schema。实现必须支持本地契约模拟并保持字段发现失败关闭，不能把自定字段冒充官方SDK字段。

### H-001 正式批次协议

`predict_then_feedback`、`labeled_train_then_predict`、标签直接提供和标签受限等表述并存。必须由正式SDK解决。
### H-002 平台与模型名称

PyTRiO通用接口、Qwen3.5-4B基础模型平台校验和持久化Sampler路线已确认，模型服务不再构成架构设计阻塞。正式比赛Base URL、凭据注入、运行时白名单与Token计量仍待平台环境确认；实现必须配置化并在启动时核验。

### H-003 评分与迭代计数

最新平台截图已确认35分四项构成、每数据集10轮优化及至少3次完整决策记录，但数学公式、资源计量细则、标签成本和“训练候选/决策轮次”的精确定义仍未发布。

### H-004 SwanLab离线同步

无公网评测环境如何形成公开且被认可的SwanLab记录尚未确认。

### H-005 时间节点

宣讲11月13日、用户先前校内11月16日、统一通知相关高校推荐节点存在差异。内部按最早11月13日准备，但对外不得宣称其为已确认校内截止。

### H-006 官方数据任务定义与切分

任务类型、预测单位、主指标、公开训练/验证切分、参考训练器和初始权重已由O-PLATFORM-001与O-PLATFORM-005确认。仍缺正式SDK/批次协议、隐藏测试、完整评分公式、平台运行资源计量和许可证，因此训练包本地续训仍不能作为官方成绩。

### L-EVIDENCE-009 三个未见工业任务本地正式流程复演

- 类型：本地可核验实验事实，不是官方证据。
- 来源：`D:/brace-msi-unseen/UNSEEN-SIM-001-A3/`、`D:/brace-msi-unseen/UNSEEN-SIM-001-A4/`及`docs/results/UNSEEN-SIM-001.md`。
- 已确认：三任务各10轮、父链和隔离协议通过；A4真实调用`Qwen/Qwen3.5-4B` PyTRiO，取得16次有效响应、15次建议执行和8,100/3,470输入/输出Token。
- 性能边界：Battery/Hydraulic最终退化，Mill持平，严格改善0/3；不得写成官方成绩、隐藏泛化通过或新RC性能证明。

### L-EVIDENCE-010 报告验证选择污染审计与修正

- 类型：本地可核验代码与机器产物，不是官方证据。
- 根因：旧`scripts/simulate_platform_report.py`逐轮读取同一`public/validation.jsonl`并按A Macro-F1最大、B/C RMSE最小选择轮次；训练入口自身仍使用当前批次Update/Gate，没有发现validation进入训练的证据。
- 修正：V2逐轮只复制当轮`metrics_before`、`metrics_candidate`和真实`deployed`；十轮冻结后只评估`round-10/checkpoint.npz`一次。每任务`public_validation_evaluations=1`，不存在`selected_round`/`selected_metrics`。
- 产物：`D:/brace-msi-native-competitive/RC7-OFFICIAL-REPORT-SIM-V2-A2/`；详情见`docs/results/REPORT-EVIDENCE-FIX-001.md`。
- 边界：公开validation已经历史暴露，V2单次结果仍不是独立测试或官方隐藏成绩；旧V1不删除，只降级为界面/协议演示。

### L-EVIDENCE-011 官方流程模拟数据可用性审计

- 类型：本地可核验数据事实与用户当前实现指令，不是正式SDK或隐藏测试证据。
- 已核验：官方A父训练集为Gas Batch 1（445条），本机另有原始Batch 1—10；官方B validation包含3条完整未见轴承；官方C validation包含106个未见unit。现有`platform_simulation.py`确实按JSONL行数均切十段并在预测前向训练入口提供标签。
- 实现边界：正式隐藏数据尚未开始、不可见；只能模拟协议、数据可见性和任务自然规律，不能承诺数值与正式隐藏评测一致。Gas/Bearing/Engine本地确认集只作一次性本地证据，不是官方隐藏指标。
- 数据位置：`C:/Users/Administrator/Desktop/官方/Dataset/batch1.dat`至`batch10.dat`；`C:/Users/Administrator/Desktop/人工智能创新大赛/训练包/cpu-{a,b,c}-*/public/*.jsonl`。原始文件保持只读。
- 实现结果：`OFFICIAL-FLOW-SIM-001`三任务各10轮、父链、自然分组、预测封存和一次本地确认通过；A2为混合/负性能证据，正式隐藏状态仍为未开始/不可用。机器摘要与边界见`results/OFFICIAL-FLOW-SIM-001.md`。

### L-AUTH-015 序贯到达证据与延迟收益完整训练授权

- 类型：用户研究语义与本地执行授权，不是正式SDK事实。
- 来源：用户2026-11-16明确要求按“旧模型先评价第t批、当前批适应、第t+1批结算上一轮真实收益”重新完成三任务训练、测试和报告。
- 已锁定：`arrival_metric_t`允许进入决策；`candidate_gate_metric_t`只作上线安全证据；`delayed_gain_t+1`必须使用同批样本配对比较直接前任。
- 未确认：平台每轮是否先预测后开放标签、历史workspace/Replay是否可用、Bearing正式十轮切法及公开验证指标映射。实现必须保留`proxy_protocol`标记。

### L-EVIDENCE-012 序贯延迟收益与直接前任回滚本地证据

- 类型：本地可核验代码、运行收据和机器报告，不是官方SDK或隐藏成绩。
- 来源：`D:/brace-msi-delayed-gain/DELAYED-GAIN-SIM-001-A2/`、`DELAYED-GAIN-SIM-001-A3/`及`docs/results/DELAYED-GAIN-SIM-001.md`。
- 已确认：A/B/C各完成10轮；到达指标进入策略；上一轮部署只在下一批同样本影子比较结算。A2中B负延迟收益后缺少回滚导致确认RMSE 993.202677；A3第10轮回滚直接前任后为241.980799。
- 边界：确认集历史暴露指数5；A/C没有新部署收益；A3确定性Token为0；正式平台是否保留直接前任、是否允许影子推理及真实十轮生命周期仍由H-001约束。

### L-AUTH-016 多方法自主性能优化授权

- 类型：用户执行授权与研究目标，不是官方规则。
- 来源：用户2026-11-16要求技术合作者主动提出、实现、训练和比较多种成熟或大胆候选，不预先确认单一方法；先看跨批趋势，明显有效再完整工程化。
- 约束：性能优先但必须保留稳定最佳方案；普通错误自主解决；不得用已第5次暴露的确认集调参；冻结RC与历史证据不覆盖。

### O-PLATFORM-013 平台模型调用桥接拒绝

- 类型：平台本次校验原始错误，优先级高于本地接口假设。
- 来源：用户2026-11-16粘贴的平台失败详情。
- 已确认：平台桥接只提供Chat Completions风格的`workspace_io.model_transport`；0.8.2原生训练入口唯一LLM路径是PyTRiO私有`ServiceClient`/Sampler协议，平台判定两者无法在不语义重写的情况下忠实桥接；确定性或PyTRiO失败路径会产生零模型调用，不满足`stage_contract model_calls_required`。
- 未确认：平台`model_transport`实际Python调用签名、真实返回附加字段、服务错误类型及Token结算细节。0.8.3只声明并实现标准OpenAI Chat Completions对象边界；真实平台兼容性仍须上传校验。

### O-PLATFORM-014 官方 Harness SDK 1.0.2

- 类型：官方可运行SDK、协议说明与回归测试；优先级高于O-PLATFORM-009至013中的草稿桥接与平台反馈推断。
- 来源：用户2026-11-17新增`C:/Users/Administrator/Desktop/人工智能创新大赛/新增/contest-harness-sdk-1.0.2.tar.gz`与同名`.txt`。
- SHA-256：归档`C676C8BEEEF69CECE9CBEC5A633D05DBB9832EB22B6F761913F2315BD1F85133`；说明文本`0433A8A3C7B6641985B1ABF90C9CE5DE349B1B3EFDAD1C6494ED6680C9EBC99C`。
- 已确认协议：`contest_harness` 1.0.2、`contest.harness.workspace.v2`、提示版本`industrial-workspace-flexible-v3`；固定入口为`python3 /app/harness.py describe|train|predict`，选手模块默认`/app/contest_submission.py`。
- 已确认模型访问：每轮必须经`rnd.model()`或`rnd.transport()`调用宿主管理的模型网关；平台持有真实端点、密钥和计费；`finish`必须引用本轮真实且非空的`model_call_ids`。正式镜像不需要也不应内置PyTRiO密钥或私有`ServiceClient`协议。
- 已确认数据/产物：训练容器只读挂载`/data/train.jsonl`、`/data/validation.jsonl`、`/previous`、可选`/state`，可写`/workspace`；预测挂载`/model`并以`CONTEST_ARTIFACT_PATH`指向确切checkpoint。候选最多64文件、合计64MiB，至少声明一个checkpoint；父文件只能通过清单和摘要校验后的`rnd.parent.path()`读取。
- 已确认轮事务：SDK提供公开训练/验证行、父产物、历史、状态复制/保存、候选提交及平台公开验证摘要；最终可选择本轮候选、父产物或已声明历史产物。隐藏数据不在训练容器挂载。
- 已确认预测契约：逐行读取后必须在读取下一行前输出并刷新；分类为唯一最高分的`[{label,score}]`，回归为非负有限`{value}`；任务来自合同而不是数据集代号。
- 本地核验：官方15项离线测试在Windows出现1项管道差异；同一原包在Linux、4核8GB、断网容器中`15/15 OK`，因此不修改官方SDK。真实宿主模型调用、平台计量、评分公式和比赛SwanLab规范仍须平台运行验证。

### O-PLATFORM-015 官方运行页四次试运行与两次失败原文

- 类型：用户登录后的官方平台运行记录，2026-11-17只读核验。
- 已确认：平台当前显示试运行共4条，正式评测0/2；2026-11-13 12:50:58和2026-11-15 12:45:25完成，2026-11-16 18:07:30和2026-11-17 12:49:50失败。
- 首次成功：A/B/C各10/10轮、预测14,773条、Token 0；隐藏主指标为A Macro-F1 0.413368、B RMSE 691.660970、C RMSE 56.220512，最终均采用第1轮模型。第二次成功的逐轮和隐藏指标完全相同。
- 11月16日失败原文：原生入口只存在PyTRiO私有Sampler路径，无法忠实桥接宿主Chat Completions；确定性或服务失败路径产生零模型调用，不满足`model_calls_required`。
- 11月17日失败原文：平台代入测试认为训练入口未产生真实模型调用；固定`/workspace/state`和`candidate`目录导致第二轮不满足新state目录/空输出约束；并质疑预测命令。预测命令质疑与O-PLATFORM-014官方示例冲突，因此该小项以官方SDK为准并保留平台反馈，不删除。
- 当前次数：平台运行页显示共4次试运行；旧SSOT中的“已用1/10”已过期，剩余次数应以平台页面实时显示为准。

### O-PLATFORM-016 历史成功运行的Token事实与正式模型调用边界

- 类型：用户登录后的官方运行报告与PyTRiO用量页只读核验，2026-11-17。
- 已确认：2026-11-13和2026-11-15两次完成的官方试运行报告均显示输入Token 0、输出Token 0、合计Token 0；因此这两次“完成”不能作为PyTRiO、Sampler或Agent实际参与的证据。
- 已确认：PyTRiO账号用量页存在历史训练/采样消耗和已保存Sampler，但这些是账号级远程实验产物，不能证明某次官方Harness运行调用了它们。
- 已确认：O-PLATFORM-014规定正式镜像经宿主`rnd.model()`/`rnd.transport()`访问平台模型；端点、凭据、计量与模型绑定由宿主负责。正式镜像不应内置私有PyTRiO SDK、API Key、Sampler权重或在线保存权重流程。
- 结论边界：下一次受控试运行必须以平台训练报告的非零Token、真实`model_call_ids`和十轮完成记录共同确认Agent生效；本地替身调用与PyTRiO账号历史用量都不能替代该证据。

### O-PLATFORM-017 0.10.3rc1正式宿主调用成功但提案全失效

- 类型：用户导出的官方平台完整试运行报告；正式平台事实。
- 来源：`C:/Users/Administrator/.codex/attachments/a9df0453-01de-43dd-b2aa-b4bd071e4a5e/Pasted text.txt`，2026-11-18提供。
- 已确认：工业模型优化流程完成，A/B/C各10/10轮，预测14,773条；输入14,289 Token、输出7,680 Token、合计21,969 Token，证明正式`rnd.model()`宿主调用和计量链路已工作。
- 已确认：30轮全部选择“未训练，保留父模型”，每轮原因为`retain because the host proposal was invalid; outcome=retained_by_agent`，候选数全部为0，最终三任务均采用起始模型。
- 已确认隐藏结果：A Accuracy 0.495907、Macro-F1 0.406823；B MAE 518.721020、RMSE 720.065935；C MAE 41.286567、RMSE 56.225925、NASA 42,594,777,435.81238。它们是本次试运行结果，不得与其他RC成绩混用。
- 根因证据：输出Token 7,680恰等于30轮乘以源码固定上限256；当前解析器仅接受整段JSON或完整围栏JSON。因此“模型未调用”已被排除，故障范围缩小到输出截断/格式与严格解析契约。尚无原始回复文本，截断与冗余前缀的相对占比仍待本地契约测试，不能臆造。

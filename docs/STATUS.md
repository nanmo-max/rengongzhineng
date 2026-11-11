# 当前状态

- 最近同步：2026-11-11（Asia/Shanghai）
- 项目阶段：冻结`BRACE-MSI-0.1.0rc1`不变；官方包设计与计划已批准，当前执行`OFFICIAL-PKG-001`本地适配与候选适应续训 `[D-028]` `[D-029]` `[D-030]`
- 方案版本：BRACE-MSI V4.1，已锁定研究方向 `[D-001]`
- 正式训练：`OFFICIAL-PACKAGE-DEV-001`已预注册但尚未启动；下一步从干净提交执行A/B/C Smoke，资源复核通过后恢复同一运行根完成后台队列
- 正式实验：0 次；本地代理/开发/工程验收8项、43个训练运行已登记，见 [EXPERIMENTS.md](EXPERIMENTS.md)
- 当前正式数据候选：Gas Sensor Array Drift、NASA C-MAPSS、XJTU-SY轴承数据 `[L-AUTH-004]` `[L-DATA-004]`
- 重复结论：Gas与C-MAPSS原件和既有代理数据逐文件一致，可复用加载器与指纹；旧代理结果仍不得改名为官方成绩
- 官方平台/SDK：A/B/C训练包、公开切分与初始权重已取得并审计 `[O-PLATFORM-005]`；正式SDK/批次协议仍未取得 `[H-001]`

## 当前执行入口

`OFFICIAL-PKG-001`为唯一当前任务。Task 1–4代码与自动测试已完成；`OFFICIAL-PACKAGE-DEV-001`预注册位于`EXPERIMENTS.md`，必须从干净提交启动。外部SDK/许可证等缺口不阻塞本地路径。
全新环境安装的wheel通过`pip check`、95项测试、两协议CLI Smoke及真实SwanLab 0.10.4离线导出。
`RR-001`因本机无容器运行时且相关Windows功能均未启用而`BLOCKED`；不得用静态审计替代真实镜像证据。
A1`ce3e907`保留为INVALID负证据，A2`7ef3829`保留为本地代理工程验收成功证据，合成轴承只标记`protocol_only`。

已完成证据：

1. 实现提交`512d477`；报告生成提交`9c7bdba`；完整回归116项通过；
2. `D:/brace-msi-official-dev/OFFICIAL-RULES-ALIGNED-DEV-001/validation.json`为`valid=true`，前三实验健康检查有效，后台PID 6084已正常退出；
3. Gas与Engine的BRACE本地指标优于静态，Bearing退化；按D-027不在同一开发流继续调参，Bearing冻结静态安全默认；
4. 结果与失败分析见`docs/results/OFFICIAL-RULES-ALIGNED-DEV-001.md`。

## 当前阻塞

- 正式SDK批次事件、标签反馈和提交字段仍未知 `[H-001]`；本地开发继续使用已测试的predict-then-feedback协议。
- 官方模型服务的准确平台名、模型ID、API形式和费用口径未知 `[H-002]`。
- 客观评分完整公式、三次迭代计数规则未知 `[H-003]`。
- SwanLab在离线评测环境中的正式同步机制未知 `[H-004]`。
- 三任务训练包、初始权重和公开切分已取得；正式SDK/批次协议、隐藏测试、完整评分公式、平台资源计量和许可证仍未取得 `[H-006]`。
- 学校实际推荐截止日期存在11月13日、11月16日和统一通知节点的冲突 `[H-005]`。
- 本机未找到Docker或Podman运行时，实际镜像构建与容器限额验收阻塞；静态上下文检查不能替代该证据。
- 开发机全局Anaconda环境的`pip check`存在三个与候选锁文件无关的包冲突；候选干净环境依赖复验并入`PKG-RUNTIME-001`。

## 近期不做

- 不在`OFFICIAL-RULES-ALIGNED-DEV-001`同一开发流上继续调门控阈值或重跑；
- 平台训练包到达前不把本地规则对齐训练称为正式平台检查点训练或排行榜实验。
- 最终工程模型与平台记录规范冻结前，不运行、修改或同步SwanLab。
- 不接入大模型服务。
- 不复现论文代码。
- 不制作Streamlit界面。
- 不声称任何模型性能或获奖概率。

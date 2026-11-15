# OFFICIAL-FLOW-SIM-001 设计规格

## 目标与非目标

新增一个不修改冻结RC的本地官方生命周期模拟器。它验证协议、可见性、父链、任务自然分组和报告语义；不声称知道正式隐藏数据、完整SDK调用生命周期或评分公式，不用本地确认结果反向选参。

## 双层数据流

每轮固定执行：稳定父模型读取无标签视图并预测；预测原子写入并由`ScoreVault`封存哈希；随后才开放同批标签，外部计分器计算Prequential指标；任务流计划给出互斥Update/Gate，Harness只用Gate作候选部署证据；部署或保留后原子提交父链。Prequential指标只进入外部报告，不传给动作策略。

最终确认集由`StreamPlan`预先冻结，十轮结束后只打开一次。最终模型就是真实部署链的末端，不按确认指标回选轮次。

## StreamPlan与任务构造

- Gas：父模型训练ID限定为Batch 1；Batch 2—9按`source_batch`和类内`source_index`构成十轮，必要时只在同一自然批次内按时间分片；Batch 10完整保留为最终确认。每轮Update/Gate按类别和时间分层，任何Batch 10样本都不物化到训练工作区。
- Bearing：validation中的未见轴承按完整bearing隔离；以确定性、与指标无关的规则留一条完整轴承作最终确认，其余轴承按各自归一化寿命进度映射到十轮。未来snapshot只在所属轮反馈后可进入历史；同轮Update/Gate按完整bearing组分开并轮换，记录小样本低置信度。
- Engine：validation中的完整`source_subset+unit`先确定性划分流与最终确认；流unit再确定性分配到十轮，同一unit只属于一轮；每轮Update/Gate按完整unit分开。

构造结果写入只读、带源文件哈希、父训练ID哈希、每轮ID/组/用途和最终确认ID的`StreamPlan`。文件名和JSONL输入顺序不得影响计划。

## Runtime与ScoreVault

`start_round`新增可选的独立Gate输入，默认旧入口行为不变。传入独立Gate时，训练集合只能来自Update及已有Replay；当前Gate不进入预处理、Anchor或Replay。`ScoreVault`只接受已封存预测和之后开放的标签，输出外部指标与收据，禁止向Runtime/Advisor提供读取接口。

## 硬门

父训练、十轮流和最终确认的ID与特征哈希零交叉；Update/Gate互斥；Gas批次顺序、Bearing snapshot进度、Engine unit边界可复算；预测封存时间早于反馈；最终确认只读一次；任何不满足项失败关闭。

## 证据等级

逐轮`prequential_metrics`最接近正式“先预测后反馈”过程；`candidate_gate_metrics`只说明候选门控；`local_final_confirmation`只说明本地冻结确认。三者均不是尚未开始的官方隐藏测试成绩。

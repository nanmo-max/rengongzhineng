"""Create the submission PDF for the verified image14 Debian variant."""
from pathlib import Path
import importlib.util
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('layout',ROOT/'scripts/build_image14_submission.py')
layout=importlib.util.module_from_spec(spec)
spec.loader.exec_module(layout)
OUT=ROOT/'output/pdf/BRACE-MSI-0.10.6rc1-debian1-作品文档.pdf'
OUT.parent.mkdir(parents=True,exist_ok=True)
s=layout.pdf_styles()
story=[]
def p(text,style='body'):
    story.append(Paragraph(text,s[style]))
def h(text): p(text,'h1')
def table(headers,rows,widths):
    t=layout.pdf_table(s,headers,rows,widths)
    header=ParagraphStyle('header-white',parent=s['small'],textColor=colors.white,fontName='MSYH-Bold')
    t._cellvalues[0]=[Paragraph(x,header) for x in headers]
    story.append(t)
def bullets(items): layout.pdf_bullets(story,s,items)
def page(): story.append(PageBreak())

p('BRACE-MSI 智训引擎','title')
p('工业制造场景下的模型训练与超参数优化','subtitle')
p('参赛作品文档 | Debian兼容候选 | 2026年11月25日','subtitle')
h('一、作品概述与提交身份')
p('BRACE-MSI将Qwen实验决策、父检查点续训、模型评估和运行审计连接为无人干预的工业模型优化流程。Agent通过官方模型网关分析当前任务及历史实验，选择受控训练Recipe；Harness执行CPU训练与本地评估，并保存部署、保留或回滚结果。')
table(['项目','本次提交配置'],[
['Harness标签','brace-msi:0.10.6rc1-debian1'],
['版本继承','继承平台镜像14的0.10.6rc1业务代码；本次迁移Debian运行环境'],
['Agent模型','Qwen/Qwen3.8-27B基础模型，通过官方SDK宿主rnd.model()调用'],
['工业模型','平台提供的checkpoint.npz父模型，NumPy/Adam CPU续训'],
['运行环境','linux/amd64；Debian12 Bookworm Slim；Python3.12.16；NumPy1.26.4'],
['资源验证','4核CPU、4GiB内存、断网、只读根目录、非root用户10001:10001'],
['验收结论','LOCAL_READY_PENDING_PLATFORM：本地通过，待平台验证'],
],[3.0,13.4])
h('二、工业场景价值')
p('传感器老化、工况变化和设备退化会改变输入分布与预测误差。持续人工调参难以形成一致、可追踪的更新过程。本作品把训练参数、父子模型、指标和选择理由统一记录，使实验失败能够保留证据、模型更新能够追溯，并在有限CPU条件下保持可复现运行。')
p('提交范围：当前候选只迁移运行环境，不宣称因此取得新的模型性能提升；旧镜像14的平台试运行与本次Debian本地验证分别报告。')
page()

h('三、系统架构与职责')
table(['组件','职责与数据流'],[
['官方SDK边界','contest.harness.workspace.v2 / contest_harness 1.0.2；消费平台轮次帧、当前合法数据、父产物和历史状态'],
['Qwen决策','读取任务合同、历史和训练选项；提出Recipe；评估后提出deploy / retain / rollback'],
['Harness执行','校验结构化提案、执行真实续训、评估父模型和候选、记录资源和模型身份'],
['工业模型','固定schema的两层MLP；保留父权重、Adam状态、预处理统计及训练计数'],
['硬安全检查','父链/任务schema、产物可加载、指标有限值、64MiB产物限制'],
['记录与交付','轮次收据、训练参数、指标、模型调用ID、选择理由、状态摘要及独立预测入口'],
],[3.0,13.4])
h('四、每轮自主实验流程')
bullets(['读取平台本轮数据、父checkpoint及已开放历史。','第一次Qwen调用：分析历史并选择注册Recipe，输出结构化训练方案。','Harness从父checkpoint执行候选训练，并计算父/候选的同作用域指标。','第二次Qwen调用：结合主辅指标、资源和历史提出部署、保留或回滚。','硬安全检查通过后提交选中产物、模型调用ID和实验记录，持久化下一轮状态。'])
p('本候选每轮执行真实候选训练；retain表示训练和评估后保留父模型。平台负责输入、模型网关与外部评分，内部选择依赖Harness自行计算的合法指标。')
h('五、数据变化与诊断边界')
p('本版本通过本轮性能、历史记录及父/候选比较支持实验分析。统计分布变化不等同设备故障；Qwen解释也不视为因果诊断。后续研究中的P5统计漂移模块未加入镜像14，本文不宣称该候选已完成独立验证的特征级漂移监测或故障定位。')
page()

h('六、训练方法与超参数')
p('工业模型保持官方父checkpoint的网络结构和字段契约。分类采用Softmax交叉熵；回归使用标准化目标上的平方误差，并按父模型目标尺度恢复原始单位。训练采用Adam，保存一、二阶矩、epochs与steps，避免从头训练另一套模型替代baseline。')
table(['受控Recipe','训练设置'],[
['e1_lr1','1 epoch，父学习率的1倍'],
['e3_lr3','3 epochs，父学习率的3倍'],
['soup_e3_alpha0.25','3 epochs，父学习率1倍；训练后使用0.75父权重+0.25候选权重'],
],[4.0,12.4])
p('Batch size、优化器种子、归一化及模型维度继承父checkpoint。训练参数与实际执行结果进入轮收据；Qwen只能选择已注册机制，不能直接改动SDK、数据边界或安全检查代码。')
h('七、评估、选择与回滚')
table(['任务','主辅指标与解释'],[
['Gas分类','Macro-F1、Accuracy；越高越好'],
['Bearing RUL','RMSE、MAE；越低越好，使用原始寿命单位'],
['Engine RUL','RMSE、MAE及NASA非对称误差惩罚；按官方口径记录，惩罚值越低越好'],
],[3.0,13.4])
p('候选与父模型在合法本地验证作用域上比较。Qwen给出选择，Harness处理不可违反的硬条件；拒绝候选时保留稳定父模型。相同验证数据反复使用会带来选择偏差，公开validation历史已暴露，不再包装为独立确认集。')
p('已知限制：镜像14历史试运行存在个别数值理由与结构化选择不一致，本次兼容性迁移保留原有业务行为，没有把后续选择器修复混入该版本；尚未证明Qwen优于同预算Random/TPE。')
page()

h('八、同口径公开开发结果')
p('以下为镜像14本地描述性验证，数据来自已暴露公开validation，不是独立测试或官方隐藏成绩。本次Debian迁移不据此重新选参数或模型。')
table(['任务与指标','官方父模型','本地稳定模型'],[
['Gas Macro-F1','0.714030','0.725695'],['Gas Accuracy','0.878617','0.885852'],
['Bearing RMSE','681.159833','656.351785'],['Bearing MAE','563.105841','545.860566'],
['Engine RMSE','52.868573','52.350178'],['Engine MAE','38.899830','38.812042'],
],[6.0,5.2,5.2])
h('九、历史镜像14官方平台试运行')
p('官方报告记录A/B/C各10轮、14,773条最终隐藏预测；输入Token72,038，输出Token2,380，合计74,418。试运行不计正式成绩。以下属于旧镜像14的平台运行证据，不是Debian候选新取得的隐藏结果。')
table(['任务','隐藏试运行最终指标','CPU / 墙钟秒'],[
['Gas','Accuracy 0.866558；Macro-F1 0.861027','194.07 / 3360.17'],
['Bearing','MAE 230.506729；RMSE 354.669933','139.10 / 3024.99'],
['Engine','MAE 41.087548；RMSE 56.187077；NASA 5.955645948×10^10','1358.92 / 4056.78'],
],[2.1,10.1,4.2])
p('公开开发与平台隐藏口径不同，不能跨表计算相对提升。平台各轮展示值也不能在事后用于重选最终模型。Engine误差和NASA惩罚仍是明显短板，本文保留负结果。')
page()

h('十、Debian候选本地验收')
table(['验收项','实际结果'],[
['完整Linux回归','470 passed，1 skipped，0 failed；157.25秒。跳过项依赖未挂载Gas原始研究数据。'],
['三任务容器链','A/B/C各10轮；30个真实候选训练；60次本地宿主协议调用；15行独立预测通过。'],
['模型服务边界','协议替身检验请求、响应和调用ID；未冒充真实远程Qwen连续决策。'],
['隔离与资源','4核/4GiB；断网、只读根、非root；本地完整协议运行114.86秒。'],
['代码与依赖','19个正式运行文件与镜像14固定源码一致；NumPy1.26.4锁定依赖及pip check通过。'],
['启动与归档','空操作、Shell、Python、默认帮助、describe通过；docker save/load及重载启动通过。'],
],[3.4,13.0])
table(['单轮资源Smoke','墙钟秒','cgroup峰值内存'],[
['Gas','0.877','28,815,360字节'],['Bearing','1.710','53,653,504字节'],['Engine','8.288','244,559,872字节'],
],[5.0,4.0,7.4])
p('资源Smoke包括容器和本地协议开销，不等同平台完整评测时间。镜像大小66,900,098字节，归档66,918,400字节（约63.8MiB），小于2GiB。')
h('十一、兼容性修正与尚待确认项')
p('基础镜像由Azure Linux改为Docker Official Python3.12 Bookworm Slim，并固定digest。Bookworm为Debian12 oldstable LTS；amd64支持至2028年6月。运行时没有额外安装Git、编译器、Torch或论文仓库。')
p('官方“预检命令执行前退出”未在本机复现，不能据此确定Azure就是根因。Debian本地启动已通过，实际平台OCI启动、PyTRiO宿主鉴权和云端同步仍待平台检验。本次未上传或消耗官方测试次数。')
page()

h('十二、系统运行与复现说明')
table(['项目','配置'],[
['系统/依赖','linux/amd64；Python3.12.16；NumPy1.26.4；官方SDK1.0.2'],
['工作目录/用户','/app；10001:10001；固定ENTRYPOINT为python3 /app/harness.py'],
['平台入口','python3 /app/harness.py describe；train；predict'],
['输入','平台轮次帧、当前合法数据、父checkpoint、历史状态和宿主模型RPC'],
['输出','候选及选中checkpoint.npz、状态、调用ID、轮次实验记录；预测为逐行id/outputs'],
['文件权限','当前输入和父产物只读；/workspace及平台规定输出位置应具有运行用户写权限'],
],[3.2,13.2])
bullets(['加载归档：docker load -i harness-debian.tar。','检查入口：docker run --rm --network none --read-only brace-msi:0.10.6rc1-debian1 describe。','平台使用官方SDK启动train/predict并传入完整帧和挂载；不能用空数据目录声称完成基线预测。','复建：解压source-debian.zip，在其根目录执行 docker build --platform linux/amd64 -f Dockerfile.formal -t brace-msi:0.10.6rc1-debian1 .。'])
h('十三、异常处理与安全边界')
bullets(['保留输入、父产物和状态身份；父链、schema、可加载性、有限值或64MiB产物硬门失败时拒绝候选。','模型服务失败、无效结构化输出或运行错误写入收据；不得补造模型调用、训练或云端成功记录。','缺数据、父checkpoint或workspace写权限时，应由运行环境补齐；不会通过打入本地数据或权重规避接口。','API Key仅填写平台受保护字段；镜像、文档、源码、公开日志均不包含密钥和隐藏标签。'])
p('镜像中不安装PyTRiO私有SDK或SwanLab。正式模型访问由官方宿主网关承载；SwanLab属于镜像外实验观测。本次镜像外离线记录接口在UTF-8环境已验证，尚未同步为新云端训练记录。')
page()

h('十四、交付身份与实验记录')
table(['项目','固定身份'],[
['镜像标签','brace-msi:0.10.6rc1-debian1'],
['镜像14源码基线','c653e0e04297b655b93e28a90abd9f36e2ff761d'],
['Debian工程提交','6091a65；包含独立Dockerfile、复现工具和验收报告'],
['归档SHA-256','3C8F01CD7D84A3F226111BF81AABE02E1DDC9CD53426997D16A6704FA0837F7C'],
['源码/证据入口','https://github.com/nanmo-max/rengongzhineng/tree/6091a65'],
['历史研发SwanLab','https://swanlab.cn/@nanmo-max/brace-msi-final'],
],[3.8,12.6])
p('SwanLab链接用于历史研发查询，不声称其由本次Debian容器同步生成。精确本地验收见源码仓库docs/results/IMAGE14-DEBIAN-001.md及对应JSON；原始详细收据、依赖清单和最终测试日志包含在独立验收包中。')
h('十五、方法与第三方来源声明')
bullets(['Adam：Kingma、Ba，Adam: A Method for Stochastic Optimization，ICLR2015；arXiv:1412.6980。正式训练为兼容官方MLP契约的NumPy实现。','权重平均参考：Wortsman等，Model Soups，ICML2022，PMLR162:23965-23998；https://proceedings.mlr.press/v162/wortsman22a.html。','作者仓库：https://github.com/mlfoundations/model-soups，MIT许可证。本作品只实现父/候选简化插值，未完整移植作者训练仓库或复现其论文成绩。','NumPy1.26.4采用BSD-3-Clause；Python官方镜像及Debian系统组件分别保留各自许可证。官方SDK遵守赛事分发与使用条款。','项目自主代码、官方代码与第三方依赖分别声明来源；不擅自授予未获授权的项目MIT/Apache许可。镜像不携带公开或隐藏数据、父模型、大模型权重、Sampler或密钥。'])
p('结论：本候选已完成本地Debian兼容性、CPU续训与预测链验收。正式平台可运行性、最终成绩及在线服务状态以平台后续回执为准；现阶段不作获奖或隐藏性能保证。')

doc=SimpleDocTemplate(str(OUT),pagesize=A4,rightMargin=2.0*cm,leftMargin=2.0*cm,topMargin=1.7*cm,bottomMargin=1.7*cm,title='BRACE-MSI Debian兼容候选作品文档',author='BRACE-MSI团队')
footer=lambda c,d: layout.pdf_footer(c,d,'BRACE-MSI 0.10.6rc1-debian1 | 2026-11-25')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
print(OUT)

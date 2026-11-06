# 初始文件审计

- 审计时间：2026-11-06（Asia/Shanghai）
- 审计性质：只读；未移动、删除或覆盖任何原始文件
- 审计前状态：目录不是Git仓库

## 根目录资料

| 文件 | 字节 | SHA256 | 判定 |
|---|---:|---|---|
| `“智训引擎”-工业制造场景下的模型训练与超参数优化-赛题规则(1)(1).pdf` | 1,609,625 | `DFE2972ECFEEE3845ADB917145F9F57477F9EC363B526524CB6A714BF961D3BE` | 官方规则本地副本 |
| `1304cc564273d02fc101e5316e4423fe.jpg` | 131,987 | `91E1DC3157878E7B4CAA8D86170DE8FFA44DBE2F9B9385E475D5919D5694B318` | 宣讲闭环截图 |
| `88127795c878a57dc63dbddfeb31af15.jpg` | 152,276 | `38BAFAD693BCF4F7AB518A4D43DE68A8BC038C48C2AF8E38B618A80921837207` | 宣讲背景截图 |
| `ba80dbeca694b0030c8c4d042357407b.jpg` | 135,867 | `A68D5E88DFCF1337F6A69FC58A84C6E1F338FD584E6189EC3C45B21B75D4D5DF` | 宣讲评分截图 |

## 代理数据

### Gas Sensor Array Drift

- 压缩包：9,989,262字节；SHA256 `91E8F466F202E7A093D657673CE47311C3E90416F7DF3057966058961C351FE4`。
- 已解压`batch1.dat`至`batch10.dat`。
- 行数依次为445、1244、1586、161、197、2300、3613、294、470、3600，总计13,910。
- 只做文件统计，未解析特征、未切分、未训练。

### NASA C-MAPSS

- 外层压缩包：12,429,152字节；SHA256 `C9C5DEC12A945A82E8BB4446589D7FB3CC057B5E5D81FA1A12E25EE9912AD3B2`。
- 内层`CMAPSSData.zip`包含FD001-FD004的训练、测试、RUL文件、readme和论文PDF。
- 内层数据尚未进一步解压，未训练。

### 轴承退化

- 未发现对应文件。

## 历史Markdown

- `plans/_draft/grill-notes-zhixun-engine-competition-strategy.md`
- `plans/_draft/grill-round1-questionnaire.md`

文件保留原位，内容反映早期需求收集，包含已被替代的优先级、日期和技术路线。不得作为当前执行入口。

## 临时文件

`tmp/pdfs/contest-rules/page-1.jpg`至`page-5.jpg`是官方PDF渲染副本，用于视觉核验。`tmp/`被视为可再生成目录，不是证据原件。

## 未发现

- 源代码；
- 依赖配置；
- Docker文件；
- SwanLab运行记录；
- 模型、检查点或正式实验输出；
- Git历史。

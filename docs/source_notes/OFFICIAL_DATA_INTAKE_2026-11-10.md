# 官方数据到货只读审计（2026-11-10）

## 证据边界

- 用户将 `C:\Users\Administrator\Desktop\官方` 指定为本赛题三个官方公开数据集的本地目录，并授权开始正式接入。
- 目录中没有组委会清单、SDK、评分脚本、任务指标或比赛专用许可证文件。因此本报告能确认本地文件身份与结构，不能仅凭目录名确认官方切分、指标和批次协议。
- 审计全程只读；没有解压覆盖、改写原始文件或运行模型训练。

## 结论

1. Gas Sensor Array Drift 的 10 个 `.dat` 文件与既有代理数据逐文件 SHA-256 完全一致。
2. NASA C-MAPSS 的 `readme.txt`、FD001-FD004 训练、测试和 RUL 文件与既有代理压缩包内容逐文件 SHA-256 完全一致。
3. 两套重复数据可以复用已有解析器、格式审计和数据指纹，不需重新下载或重新实现加载器。
4. 既有代理实验使用自定切分和指标，不能改名为官方成绩；正式实验是否需要重跑取决于后续官方切分、评测脚本和流协议。
5. XJTU-SY 是新增的完整原始轴承数据：6 个 RAR5 分卷完整性测试通过，共 15 个轴承、3 种工况、9,221 个双通道振动 CSV，归档解压总大小约 12.22 GB。
6. XJTU-SY 文件本身没有定义本赛题要做分类、健康指数还是 RUL，也没有官方开发/测试切分。该任务定义明确前不得启动确认性训练。

## Gas逐文件指纹

| 文件 | 字节 | SHA-256 |
|---|---:|---|
| `batch1.dat` | 752,726 | `F346BEEE8E0C5E31AC5961845B6D96A70DC1CCF799481592FB2F0D96A81952E6` |
| `batch2.dat` | 2,119,601 | `07F7E94A9BF4377240F9B230D20C750932FC785D4766B6A4B7FC370A035C825A` |
| `batch3.dat` | 2,706,554 | `A4C7A1A6744DF32F0CA139C75C3B4DADE7CC99F57A7785D28CB0F62577DD2061` |
| `batch4.dat` | 276,473 | `BD76F86BE34FFE89F46A27C6FC2B5B8C6EBFCF984DFF4B3E5BEFC76D98034B7F` |
| `batch5.dat` | 339,035 | `3F95CB6E4A39A94BBACD2F1984F1754C9FB5EB3221812975AD70EDBCEA7ABAEC` |
| `batch6.dat` | 3,902,170 | `83348C504105A5AA5264D1209F2A5D7BA7D9C8BCAE60290395F201AC4708FF95` |
| `batch7.dat` | 6,117,334 | `3168CB56D5C9BC29C36184E2E73C9F3474ADB3C4A893B1CE0D88B6C47698CFDB` |
| `batch8.dat` | 491,904 | `296346B932893EA18C513E23AC5B660F35E1C499FDE8254D4804A2CE8A1B4CA7` |
| `batch9.dat` | 785,870 | `E019F11F4FA8336AB1F41F7503EB456B3679DA0A84EB8032FE6CEF90F0547826` |
| `batch10.dat` | 6,045,679 | `30011067C7C05C2B01038F84C73AF0C6F1820B622FA2B0AD89111CB4C649F791` |

## C-MAPSS逐文件同一性

下列 13 个数据文件及 `readme.txt` 均与既有 `CMAPSSData.zip` 内容逐字节一致：

- `train_FD001.txt` 至 `train_FD004.txt`
- `test_FD001.txt` 至 `test_FD004.txt`
- `RUL_FD001.txt` 至 `RUL_FD004.txt`
- `readme.txt`

详细文件哈希可由审计命令重新生成；本次比较全部返回 `Same=True`。

## XJTU-SY结构与指纹

RAR完整性命令：

```powershell
& 'C:\Program Files\WinRAR\Rar.exe' t -idq -c- -y -- `
  'C:\Users\Administrator\Desktop\官方\极速下载好的文件\12355\XJTU-SY_Bearing_Datasets\XJTU-SY_Bearing_Datasets\Data\XJTU-SY_Bearing_Datasets.part01.rar'
```

返回码为 `0`。

| 分卷 | 字节 | SHA-256 |
|---|---:|---|
| `part01.rar` | 744,488,960 | `C500657353F089A4AB50212FF4DDFC7B982729E92E2B127440C8AD881D80B968` |
| `part02.rar` | 744,488,960 | `4DFA6286A8E9C7CEC1E925B347642349F36E27AB3F703C90D1D08977B7B4F61F` |
| `part03.rar` | 744,488,960 | `6929F531284F79E0209246B4EE23B23DD8D4FAAC1C0C3FF8FB131CDA4A18BD3A` |
| `part04.rar` | 744,488,960 | `2245825ACD29BED3B95E7A77879A3FBADF20F4AD4F99486384C714174621597D` |
| `part05.rar` | 744,488,960 | `E1B0A41A32B865E48EA7981C56F952A960D94335F3496B72EB4A65932F1671BD` |
| `part06.rar` | 722,155,640 | `DF1854821A9D481104476379F7BC045EA1E101427C6E36145CD7677DC7C4A684` |

每个 CSV 首行为：

```text
Horizontal_vibration_signals,Vertical_vibration_signals
```

文件数：

| 工况/轴承 | CSV数 |
|---|---:|
| 35Hz12kN / Bearing1_1..1_5 | 123 / 161 / 158 / 122 / 52 |
| 37.5Hz11kN / Bearing2_1..2_5 | 491 / 161 / 534 / 42 / 339 |
| 40Hz10kN / Bearing3_1..3_5 | 2540 / 2497 / 371 / 1516 / 114 |

## 未解除的阻塞

- 三个任务的官方主指标与评分方向；
- 公开训练、验证、开发流和隐藏流的身份；
- XJTU-SY在赛题中的目标定义与标签构造；
- 批次事件、标签可见性和提交协议；
- 数据许可证或主办方允许使用声明；
- 官方静态基线配置与评分脚本。

在上述信息到达前，允许继续做只读数据审计和接口准备，不允许把任何新训练称为正式成绩。

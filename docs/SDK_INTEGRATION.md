# 正式SDK接入说明

## 已冻结的内部边界

正式适配器只需实现`brace_msi.protocol.EventProtocolAdapter`，把官方事件映射为：

- 打开任务；
- 提供有标签训练批次（如协议允许）；
- 请求与提交预测；
- 提供预测后反馈（如协议允许）；
- 提交批次；
- 结束任务。

训练、预算、证据、门控、注册和恢复逻辑不得读取官方SDK私有字段。样本标识在内部只作
不透明字符串使用。

## SDK到达后的核验顺序

1. 登记SDK文件、版本与哈希到`SOURCE_REGISTRY.md`。
2. 核实批次顺序、训练集与评分集身份、标签权限、输出格式和错误语义。
3. 在新适配器中完成字段映射，不修改状态守卫。
4. 使用官方提供的小样例跑两类合法序列及全部非法顺序回归测试。
5. 核实三次迭代计数、资源计量和SwanLab同步后再更新正式配置。

截至2026-11-07，官方字段、评分公式和离线SwanLab机制仍未知；本文不对其作假设。

## 已准备的插件加载边界

`brace_msi.official_sdk`只接受四个清单字段：

- `module`：安装后的官方适配插件Python模块；
- `factory`：无副作用的工厂函数名，签名为`factory(ProtocolMode) -> EventProtocolAdapter`；
- `sdk_version`：实际取得的SDK版本；
- `sdk_sha256`：SDK原始文件或发布包的64位SHA-256。

清单拒绝任何额外字段，尤其不能存放API Key、Token、主机地址或数据字段映射。工厂返回对象必须
完整实现内部`EventProtocolAdapter`；缺模块、缺方法或无效哈希均显式失败，不会自动退回模拟SDK。

正式SDK到达后，复制 [OFFICIAL_SDK_SPEC.json.example](templates/OFFICIAL_SDK_SPEC.json.example)
到不含密钥的运行配置目录，替换四个占位值，然后执行：

```powershell
python -m brace_msi sdk-contract-check --spec path/to/official-sdk.json
```

该命令只验证插件可加载及两种内部协议的接口契约。插件工厂必须保持无网络、无任务消费、无状态
变更；真实小样例接入仍按上文核验顺序单独进行。

## 尚未实现且不得伪造的部分

- 官方事件和数据对象到`TaskStream`的字段映射；
- 预测值、下线判断和批次完成信号的实际提交方法；
- 标签何时可见、错误重试语义和幂等键；
- 官方资源计量、模型服务认证与迭代计数。

这些部分只有在SDK、样例和书面规则到达后才能进入`SDK-001`。当前插件加载器只缩短接入路径，
不代表正式平台接入已通过。

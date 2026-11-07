# 开源依赖与合规清单

当前候选镜像的直接Python依赖如下，版本以`requirements.lock`为准：

| 依赖 | 当前锁定版本 | 上游许可证口径 | 用途 |
|---|---:|---|---|
| NumPy | 1.26.4 | BSD-3-Clause | 数组计算 |
| SciPy | 1.13.1 | BSD-3-Clause | 统计与scikit-learn依赖 |
| scikit-learn | 1.5.1 | BSD-3-Clause | CPU模型与指标 |
| psutil | 5.9.0 | BSD-3-Clause | 进程资源计量 |

提交前必须从最终镜像中导出完整传递依赖及许可证文本重新核验。本表不授权打包任何数据、
预训练权重或第三方密钥；Docker上下文审计会拒绝常见权重与密钥后缀。

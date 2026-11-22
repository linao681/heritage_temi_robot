# 阶段 2.8 归档策略

- 高频原始实验、压缩包和体积较大的离线回放放在 `artifacts/phase2_8/` 下的 `raw/`、`archive/`、`replays/`；这些目录由 `.gitignore` 忽略。
- `docs/phase2_8/` 保留 manifest、摘要、逐项SHA256、分析报告、测试结果和恢复说明；源码与小型审查证据不忽略。
- 只归档已结束的run；按manifest比对每个文件大小和SHA256，并复验tar成员。失败轮次保留，重复归档不覆盖，原始目录不删除。
- 回放导出必须校验归档、来源文件与manifest；生成独立 `.sha256` sidecar。播放器本地复验sidecar、来源manifest和内嵌图像哈希。
- 不在归档或测试证据中保存凭据、用户数据或不必要的环境秘密。历史日志保持原样，除非有独立授权和可恢复备份。
- 解压说明：按归档manifest的 `archive_path` 执行 `tar -xzf <archive> -C <restore-root>`；解压后再次用manifest校验源文件SHA256。

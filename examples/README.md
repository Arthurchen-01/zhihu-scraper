# Examples / 示例

此目录用于说明示例抓取结果的定位。实际导出文件不再进入版本库，避免仓库被图片和长文样例撑大。

This directory documents example exports. Generated outputs are no longer committed so the repository stays small.

## 使用方式

运行抓取命令后，把本地输出保存在默认的 `data/entries/`，或临时放到 `examples/outputs/` 做人工检查。`examples/outputs/` 会被 Git 忽略。

如果需要长期保留某个示例，只保留经过裁剪的最小 Markdown 片段，并确保不包含 Cookie、数据库、监控状态或真实私密内容。

## Boundary Rules / 边界规则

- `examples/outputs/` 是本地临时展示区，不进入版本管理
- 不要放真实 Cookie、数据库、监控状态或临时调试产物
- 本地临时导出结果放回 `data/`
- 仓库级目录约定以 [AGENTS.md](../AGENTS.md) 与 [目标架构](../docs/ARCHITECTURE.md) 为准

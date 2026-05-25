# AGENTS.md

本文件是本仓库的共享 cross-agent 运行手册。
`CONSTITUTION.md` 是最高治理文件；后续任何代码代理或自动化协作者进入仓库后，应先读 `CONSTITUTION.md`，再读本文件，然后再执行具体任务。

## 1. 默认执行流程

所有代理在开始本仓库任务前，必须先阅读并遵守 `CONSTITUTION.md` 与 `AGENTS.md`。除非任务明确说明，否则不得跳过。

默认执行顺序如下：

1. 先阅读 `CONSTITUTION.md`
2. 再阅读 `AGENTS.md`
3. 再检查与本次任务相关的：
   - `README.md`
   - `pyproject.toml`
   - 相关代码与测试
4. 再实施修改
5. 如果本次任务形成了新的相关 Git commits，则在汇报中明确说明 commit情况

说明：

- 后续在本仓库执行任务时，默认先读 `CONSTITUTION.md` 与本文件，不再依赖用户重复提醒
- 如果任务范围只涉及文档、测试或配置，也不跳过这个流程

## 2. 项目目标

本项目的目标是维护一个**本地优先**的知乎抓取与归档工具，核心交付包括：

- 稳定的 CLI 与 TUI 入口
- Markdown + 图片 + SQLite 的本地输出
- 可维护的配置系统
- 明确的模块边界与 typed contracts
- 可复现的测试、安装和文档入口

默认优先级：

1. 保持现有功能可用
2. 减少结构混乱与文档漂移
3. 在不破坏兼容性的前提下推进重构

`v3.0.1-final` 之后，默认不再主动推进大重构或扩展抓取面。后续任务优先处理安装、文档、最小验证、本地数据可读性和现有命令面的明确 bug。

## 3. 修改原则

- 先检查现状，再修改，不先假设
- 优先最小闭环修改，不做顺手大重构
- 能抽边界时抽边界，但不要制造空壳模块
- 新增模块必须有明确职责，避免“helper.py / misc.py / temp.py”这类无语义文件
- 已经形成的模块边界优先保留：
  - `cli/` 负责入口与编排
  - `core/` 负责抓取、配置、转换、数据库与运行时能力

## 4. 依赖管理规则

- `pyproject.toml` 是主项目依赖的唯一事实来源
- 不要为主项目再新增根目录 `requirements*.txt`
- 如果仓库内存在其他目录下的 `requirements*.txt`，先判断是否属于独立子项目或外部参考材料，不要静默删除
- 新依赖必须满足：
  - 有明确用途
  - 代码里确实使用
  - 文档中有落点
  - 测试或安装链路能覆盖

## 5. 文档同步规则

文档职责固定如下：

- `CONSTITUTION.md`
  最高治理文件。定义项目身份、不变量、架构守卫、质量门禁与高风险漂移。
- `README.md`
  对外介绍、快速安装、最小运行方式、功能概览、基本目录说明
- `AGENTS.md`
  面向代码代理的执行规范

修改代码时，优先检查以下内容是否需要同步：

- `CONSTITUTION.md`
- `README.md`
- `README_EN.md`

当前直接守卫文档同步与入口语义漂移的测试包括：

- `tests.test_docs_sync`
- `tests.test_command_surface`
- `tests.test_install_contract`

## 6. 测试与校验要求

默认最小校验集：

- `./.venv/bin/python -m unittest -q ...` 运行当前验证矩阵
- 命令面 smoke：
  - `python cli/app.py --help`
  - `python cli/app.py fetch --help`
  - `python cli/app.py interactive --help`
  - `python cli/app.py config --help`
  - `python cli/app.py check --help`

如果改动涉及以下范围，还应补对应验证：

- 文档/命令面：`tests.test_docs_sync`、`tests.test_command_surface`
- 配置层：`tests.test_config_schema`、`tests.test_config_runtime`
- 保存链路：`tests.test_save_pipeline`、`tests.test_save_contracts`
- scraper contract：`tests.test_scraper_payloads`、`tests.test_scraper_contracts`
- 安装/平台边界：`tests.test_install_contract`

## 7. 任务完成后的汇报要求

完成任务后，汇报应尽量包含：

1. 仓库原状
2. 新建文件
3. 修改文件
4. 每个文件修改目的
5. 已验证内容
6. 未验证内容
7. 风险、歧义与后续建议

如果任务与 Git 提交相关，还应明确说明：

1. 是否形成了新的相关 commits

如果存在未解决问题，不要装作已经完成。

## 8. 禁止事项

- 不要先假设文件不存在
- 不要静默删除可能仍有价值的旧文档或旧文件
- 不要在未确认职责的情况下新增重复文档
- 不要把 README 再次写成“内部说明书全集”
- 不要新增与任务无关的依赖
- 不要把测试失败当成“只是 CI 问题”略过
- 不要在未经说明的情况下修改 `references/external/` 下的独立/参考目录

## 9. 遇到歧义时的处理原则

如果出现以下情况：

- 文件职责重叠
- 文档命名不统一
- 旧内容仍有价值但明显过时
- 代码边界暂时无法彻底理顺

默认策略是：

1. 优先最小改动
2. 优先保留有价值内容
3. 优先通过新增标准入口解决混乱
4. 无法彻底解决时，把歧义明确记录在任务报告或提交信息中

## 10. 长期维护约定

- 后续任务开始时，先读 `CONSTITUTION.md`
- 再读本文件
- 再检查相关代码与测试

如果仓库结构发生重大变化，应同步更新：

- `CONSTITUTION.md`
- `AGENTS.md`
- `README.md`

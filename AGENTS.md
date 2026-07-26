# AGENTS.md

本文件是本仓库唯一的项目内代理运行手册。当前用户指令决定本轮目标和优先级；仓库文档用于补充背景，不设置额外的“最高治理文件”。

## 开始任务

1. 阅读本文件。
2. 检查 `git status`，保留无关的用户改动。
3. 按任务读取：
   - `README.md` 与 `README_EN.md`：对外功能和安装入口
   - `pyproject.toml`：依赖与命令入口
   - `docs/ARCHITECTURE.md`：目标架构和稳定模块 seam
   - `docs/FEATURE_TODO.md`：已确认范围与延期功能
   - 相关代码和测试

## 当前方向

- 在本仓库中受控重建，不维护旧接口兼容层。
- 每次迁移一个可运行能力；新实现通过测试后，再删除对应旧实现。
- 第一阶段主流程：

  ```text
  知乎数据
    → 归一化内容模型
    → Markdown 渲染器 / HTML 渲染器 / SQLite 保存器
  ```

- 第一阶段支持 Windows、macOS、Linux，但平台差异只能出现在运行平台 Adapter 中。
- 关键词搜索、语义搜索和知识图谱属于后续待办，不提前进入第一阶段实现。

## 修改规则

- 先观察现状，再修改。
- 采用小型纵向闭环：一个行为测试、最小实现、通过测试、再提交。
- 测试公共 interface 的行为，不锁定内部实现细节。
- 模块应具有小 interface 和足够深的实现；避免只转发调用的空壳层。
- 不新增 `helper.py`、`misc.py`、`temp.py` 等无明确职责的模块。
- `pyproject.toml` 是主项目依赖的唯一声明来源；不新增根目录 `requirements*.txt`。
- 不修改 `references/external/` 中的参考仓库。
- README 暂不重写；只有在当前任务明确要求或需要修复断链时才做最小同步。

## 文档职责

- `README.md` / `README_EN.md`：对外介绍、安装和最小使用方式
- `docs/ARCHITECTURE.md`：已经对齐的架构、目录和模块 seam
- `docs/FEATURE_TODO.md`：功能路线、默认值和延期范围
- `AGENTS.md`：代理执行规则

不在仓库中维护项目内 Agent Skills，也不再引入 Constitution 类治理文件。

## 验证与提交

- 每次改动至少运行最相关的单元测试。
- 修改命令面时运行相应 `--help` smoke。
- 修改安装或平台逻辑时覆盖 Windows、macOS、Linux 的可验证行为。
- 不把失败测试归因于“只是 CI”；记录并解决或明确报告。
- 当前重建阶段按用户授权直接提交到 `main`。
- 只暂存当前闭环涉及的文件，使用简短、可解释的 commit message，并在完成后推送。

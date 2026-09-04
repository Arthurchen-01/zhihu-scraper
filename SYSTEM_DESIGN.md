# 知乎负面证据全量取证与可疑人员穿透系统设计文档 (System Design)

---

## 1. 核心业务目标

针对特定品牌（如“清一武道馆”），通过知乎全网检索、深度正文抓取、评论区/楼中楼穿透以及大模型（LLM）语义负面判定，完成**一次性历史负面证据全量回溯**；并对发表攻击/避雷/投诉言论的可疑用户，进行**个人主页全量历史动态穿透**，形成完整的法律/公关证据卷宗与人员关联图谱。

---

## 2. 系统全流程工作流 (Pipeline Workflow)

```text
[ 输入: 品牌名 + 负面词库 + 知乎 Cookie ]
                     │
                     ▼
┌──────────────────────────────────────────────────────────┐
│  阶段 1: 种子全网检索 (多渠道广度召回)                      │
│  - 站内按“最新发布时间”检索问答、文章、想法                │
│  - 外部搜索引擎 (site:zhihu.com) 兜底补充冷门/长尾收录     │
│  - 输出: 候选【问题/回答/专栏/想法】URL 清单                │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│  阶段 2: 深度全量采集与评论区穿透 (正文 + 楼中楼)           │
│  - 抓取主帖与回答正文 (Markdown / Plain Text)            │
│  - 深度遍历每个回答/文章的【全部一级评论 + 二级子评论】   │
│  - 提取发帖人 UID、发布时间、点赞数、评论层级上下文        │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│  阶段 3: LLM 智能语义识别与初筛 (负面分类)                 │
│  - 逐条判别是否包含负面/维权/避雷倾向 (无需出现“骗子”原词)  │
│  - 提取: 负面指控维度 (退费/师资/虚假宣传) + 核心实锤原句 │
│  - 筛选并标记: 【重点可疑用户 UID 清单 (Suspect List)】   │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│  阶段 4: 重点可疑人员主页全量穿透 (全网历史发言挖掘)        │
│  - 自动定位可疑人员主页 (/people/{person_id})            │
│  - 穿透抓取其历史【所有回答、文章、专栏、想法】           │
│  - 交叉核验: 排查是否为职业黑号/同行马甲/多帖连环攻击    │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│  阶段 5: 结构化证据卷宗与图谱导出                           │
│  - 1. Excel 证据明细总表 (言论、发帖人、链接、风险等级)    │
│  - 2. 重点可疑人员画像表 (账号特征、全网历史负面发言汇总)  │
│  - 3. Markdown 快照与完整上下文归档                      │
└──────────────────────────────────────────────────────────┘
```

---

## 3. 知乎核心 API 协议清单 (已验证)

系统只需传入用户日常登录的 **知乎 Cookie**，即可调用以下全部已验证接口：

### 3.1 搜索与线索发现接口
* **站内综合/问答/文章搜索**：
  * `GET https://www.zhihu.com/api/v4/search_v3`
  * 参数：`t=general&q={keyword}&correction=1&offset={offset}&limit=20&sort=created_time`
* **外部搜索引擎兜底指令**：
  * `site:zhihu.com "清一武道馆" (避雷 OR 骗 OR 坑 OR 退费 OR 差评)`

### 3.2 评论区全层级穿透接口（知乎 v5 协议）
* **文章主评论 (Root Comments)**：
  * `GET https://www.zhihu.com/api/v4/comment_v5/articles/{article_id}/root_comment?limit=20&offset={offset}`
* **回答主评论 (Root Comments)**：
  * `GET https://www.zhihu.com/api/v4/comment_v5/answers/{answer_id}/root_comment?limit=20&offset={offset}`
* **评论区楼中楼 (Child Comments / 子评论回复)**：
  * `GET https://www.zhihu.com/api/v4/comment_v5/comment/{root_comment_id}/child_comment?limit=20&offset={offset}`

### 3.3 正文详情与文章列表接口
* **单回答正文**：`GET https://www.zhihu.com/api/v4/answers/{answer_id}?include=content,voteup_count,comment_count,author`
* **单文章正文**：`GET https://www.zhihu.com/api/v4/articles/{article_id}`
* **专栏文章列表**：`GET https://www.zhihu.com/api/v4/columns/{column_id}/items`

### 3.4 可疑人员主页全量穿透接口
* **用户发表的全部文章**：`GET https://www.zhihu.com/api/v4/members/{person_id}/articles`
* **用户发表的全部回答**：`GET https://www.zhihu.com/api/v4/members/{person_id}/answers`
* **用户发表的全部想法**：`GET https://www.zhihu.com/api/v4/members/{person_id}/pins`
* **用户参与的全部专栏**：`GET https://www.zhihu.com/api/v4/members/{person_id}/column-contributions`

---

## 4. LLM 负面语义识别模型定义

针对不带“骗子”字眼但具有负面攻击/维权性质的内容，LLM Prompt 规范如下：

```json
{
  "is_negative": true,
  "sentiment_score": 0.92,
  "risk_level": "HIGH",
  "complaint_category": ["退费困难", "虚假宣传", "教练水平"],
  "summary": "学员反映交费后无法退款，销售态度恶劣且推诿",
  "quoted_evidence": "报名时说随时能退，现在退卡扣80%违约金还一直拖着"
}
```

---

## 5. 项目模块工程分工

* `config.py`：品牌配置、负面关键词矩阵、Cookie 读取、LLM API 配置。
* `zhihu_client.py`：基于 `requests`/`curl_cffi` 的底层会话管理（含重试、退避与防风控限速）。
* `search_engine.py`：站内搜索与种子 URL 召回。
* `comment_fetcher.py`：问答与文章的评论区/楼中楼递归抓取。
* `llm_evaluator.py`：大模型语义分类与负面证据提取。
* `author_tracer.py`：可疑人员主页动态穿透与历史发言深挖（基于 `archive_author.py` 升级）。
* `reporter.py`：Excel 证据清单与 Markdown 证据卷宗生成。
* `run_evidence_pipeline.py`：一键执行主程序。

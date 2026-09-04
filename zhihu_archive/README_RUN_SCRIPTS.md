# Zhihu Archive 工具箱

知乎内容批量归档工具。给一个知乎用户主页链接，就能抓取其全部文章、回答、想法。

## 目录结构

```
zhihu_archive/
├── README.md                          # 本文件
│
├── [脚本区]                           # 所有工具脚本
│   ├── fetch_zhihu_article_links.py   # 1. 抓文章目录（链接+元数据）
│   ├── fetch_zhihu_answers.py         # 2. 抓回答目录（链接+元数据）
│   ├── fetch_zhihu_pins.py            # 3. 抓想法目录（链接+元数据）
│   ├── fetch_zhihu_content.py         # 4. 批量下载正文（文章/回答/想法）
│   └── download_column.py             # 5. 下载专栏正文
│
├── [输出区]
│   └── outputs/
│       └── <person-id>/               # 按作者组织
│           ├── articles/              # 文章目录索引
│           │   ├── articles_index.json
│           │   ├── article_links.txt
│           │   └── run_log.json
│           ├── answers/               # 回答目录索引
│           │   ├── answers_index.json
│           │   ├── answer_links.txt
│           │   └── run_log.json
│           ├── pins/                  # 想法目录索引
│           │   ├── pins_index.json
│           │   ├── pin_links.txt
│           │   └── run_log.json
│           ├── content/               # 正文下载（md+txt）
│           │   ├── 0001_文章标题.md
│           │   ├── 0001_文章标题.txt
│           │   └── download_summary.json
│           └── analysis/              # 分析报告
│               └── *.md
```

## 从知乎链接获取 person-id

```
https://www.zhihu.com/people/shan-chang-qing-yi/posts
                    ↑
              person-id = shan-chang-qing-yi
```

## 使用方式

### 第一步：抓目录（文章+回答+想法）

```powershell
# 设置 cookie（一次性）
$env:ZHIHU_COOKIE = "你的完整cookie"

# 进入目录
cd C:\Users\25472\Desktop\AI brain storming\工具栏\zhihu_archive

# 抓文章目录
python .\fetch_zhihu_article_links.py --person-id shan-chang-qing-yi --cookie $env:ZHIHU_COOKIE --output-dir .\outputs\shan-chang-qing-yi\articles

# 抓回答目录
python .\fetch_zhihu_answers.py --person-id shan-chang-qing-yi --cookie $env:ZHIHU_COOKIE --output-dir .\outputs\shan-chang-qing-yi\answers

# 抓想法目录
python .\fetch_zhihu_pins.py --person-id shan-chang-qing-yi --cookie $env:ZHIHU_COOKIE --output-dir .\outputs\shan-chang-qing-yi\pins
```

### 第二步：下载正文（可选）

```powershell
# 下载文章正文
python .\fetch_zhihu_content.py --type articles --index-file .\outputs\shan-chang-qing-yi\articles\articles_index.json --cookie $env:ZHIHU_COOKIE --output-dir .\outputs\shan-chang-qing-yi\content\articles

# 下载回答正文
python .\fetch_zhihu_content.py --type answers --index-file .\outputs\shan-chang-qing-yi\answers\answers_index.json --cookie $env:ZHIHU_COOKIE --output-dir .\outputs\shan-chang-qing-yi\content\answers

# 下载想法正文
python .\fetch_zhihu_content.py --type pins --index-file .\outputs\shan-chang-qing-yi\pins\pins_index.json --cookie $env:ZHIHU_COOKIE --output-dir .\outputs\shan-chang-qing-yi\content\pins

# 只下载前10篇测试
python .\fetch_zhihu_content.py --type articles --index-file .\outputs\shan-chang-qing-yi\articles\articles_index.json --cookie $env:ZHIHU_COOKIE --limit 10
```

### 下载专栏

```powershell
python .\download_column.py --column-url https://www.zhihu.com/column/c_1993097680050747067 --cookie $env:ZHIHU_COOKIE
```

## 可选参数

| 脚本 | 参数 | 默认值 | 说明 |
|------|------|--------|------|
| 所有 | `--cookie` | (必填) | 知乎 cookie |
| 所有 | `--person-id` | (必填) | 用户 ID |
| 目录脚本 | `--limit` | 20 | 每页请求数 |
| 目录脚本 | `--pause` | 0.5-0.6 | 请求间隔(秒) |
| 正文脚本 | `--pause` | 1.0 | 请求间隔(秒) |
| 正文脚本 | `--limit` | 0(全部) | 最大下载数 |

## 运行前检查

1. Python 可用，`pip install requests beautifulsoup4 lxml`
2. cookie 是刚从浏览器复制的（登录状态有效）
3. person-id 是知乎链接 `/people/xxx/...` 中的 `xxx` 部分

## 常见问题

### 401/403 未登录
cookie 过期或复制不完整，重新复制。

### 连接中止/SSL EOF
知乎风控，增大 `--pause` 间隔，或换 cookie。

### 数量不一致
知乎接口有时总数提示和实际枚举数不同，不一定是脚本问题。先看 run_log.json。

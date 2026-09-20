# 先读这一页 · START HERE

> 这份仓库是「**清一新教育文章修改工作台**」的全部家当。
> 不管你换了电脑、换了对话窗口、还是换了助手 —— **把下面那段话粘进去，就能一把接回来。**

---

## 一、把这段话粘给任何新助手（换设备 / 换对话窗口都行）

```text
请接手「清一新教育文章修改工作台」这个项目。

1) 把仓库拿到本地（私有仓库，用 GitHub 账号 Arthurchen-01 登录即可）：
   git clone https://github.com/Arthurchen-01/zhihu-scraper.git
2) 完整读一遍仓库根目录的：
   清一新教育文章修改工作台_总控与需求交接.md
3) 再读 qingyi-workbench/README.md，
   并打开 qingyi-workbench/验收报告.html 看交付现状（每轮一张卡，截图+文本证据）
4) 然后 ssh server3（103.52.152.37），cd /opt/zhihu-scraper，
   看 git log --oneline -8 与 git status
5) 最后汇报：现在做到哪一步、线上什么状态、下一步该干什么。

动手改任何东西之前，先看总控文件的 §2（用户的判定标准）、
§4（三条架构不变量）、§12（已知的坑）—— 这三节是雷区地图。
```

**如果你已经在这台电脑上、只是换了个对话窗口**：第 1 步不用 clone，
把工作目录指向 `C:\Users\s990uma\WorkBuddy\2026-09-19-18-08-35\qy_local\` 即可。

---

## 二、读哪几份就够接活

| 文件 | 一句话 |
| --- | --- |
| `清一新教育文章修改工作台_总控与需求交接.md` | **唯一需求总控** —— 要做什么、做到哪、为什么这么设计、坑在哪 |
| `qingyi-workbench/README.md` | 交付物索引 + 界面设计系统 + 怎么重建 |
| `qingyi-workbench/验收报告.html` | 可视化验收报告（用浏览器直接打开） |
| `AGENTS.md` | 仓库的代理执行规则 |
| `README.md` | 对外功能与安装入口 |

**只读第一行那一份，就够接活了。** 其余是取证用的。

---

## 三、关键事实速查

| 项目 | 值 |
| --- | --- |
| 品牌词 | 标题前置 `【清一新教育】`（固定 1 处）；正文括注 `（清一新教育）`（1~5 处可选，默认 1） |
| 线上工作台 | <https://zh.samuraiguan.cloud/api/qy/console> |
| 部署机 | `server3` = `103.52.152.37`，目录 `/opt/zhihu-scraper` |
| 服务 | `zhihu-scraper.service`（systemd），端口 **8775** |
| **改完 `qingyi_*.py` 必须** | `systemctl restart zhihu-scraper`（页面是模块级常量，不重启不生效） |
| 客户端入口源码 | `clients/qingyi_deploy.py`（六道闸门 + 一次回车确认） |

---

## 四、⚠️ 这个仓库是私有的，原因写在这

仓库里含**站点访问密钥**、**服务器 IP**、品牌与对接人信息。
所以 **不要把它改成公开仓库**，除非先把这些信息清出去。

- 换新设备：用 `Arthurchen-01` 账号登录 GitHub，即可 `git clone`；
  或者生成一个**只读** Personal Access Token 交给助手。
- 仓库根的文档与代码可以随便传；**真实凭证（知乎 Cookie 等）一律不进仓库**，
  这条规矩必须继续守（见 `.gitignore` 与总控文件 §9）。

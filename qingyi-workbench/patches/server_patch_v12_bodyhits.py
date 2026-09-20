# -*- coding: utf-8 -*-
"""v12 补丁：让「正文植入几处」真正可选 + AI 按需推荐。

背景（查证结果）：
  用户要求「文章内容也要添加，可以选择往里加几个，也可以 ai 推荐」。
  实际查下来：
    · 标题 1 处 + 正文 1 处 —— 实现过；
    · AI 推荐（逐篇挑加在哪）—— 实现过（_ai_review_one）；
    · **「正文加几处」从没实现** —— 请求模型有 body_hits 字段、引擎也有 body_hits
      形参，但 `qy_content._MAX_BODY_HITS = 1` 把它夹死成 1，
      前端还额外写死 `body_hits: 1`，`/scan-scenes` 也无视传入的 hits。
  本补丁把这条链路打通，并保留"默认 1 处、上限 5 处"的安全姿态。
"""
import io
import sys

CONTENT = "/opt/zhihu-scraper/zhihu_scraper/qy_content.py"
API = "/opt/zhihu-scraper/zhihu_scraper/app/qingyi_api.py"
PAGE = "/opt/zhihu-scraper/zhihu_scraper/app/qingyi_page.py"

EDITS = []          # (文件, 旧, 新, 说明)
EDITS.append((CONTENT, '''# 硬上限：每篇正文最多植入 1 处。
# 标题 1 处 + 正文 1 处 = 全篇 2 处，是达成"检索可达"的最小充分量；
# 再多既无收益，又会显著提高被判定为关键词堆砌的风险。
_MAX_BODY_HITS = 1''', '''# 正文植入处数的硬上限（调用方可在 1.._MAX_BODY_HITS 之间自选）。
# 默认 1 处：标题 1 + 正文 1 = 全篇 2 处，是达成"检索可达"的最小充分量。
# 放宽到 5，是因为用户明确要求「正文可以自己选加几处」；
# 但必须记住：同一篇里重复堆同一个词，是平台判定"内容注水 / 关键词堆砌"的
# 典型特征 —— 处数越多风险越高。**这是上限，不是推荐值。**
_MAX_BODY_HITS = 5''', "抬高处数上限"))

EDITS.append((CONTENT, '''    """从前往后扫描，挑出最自然的前 N 个可植入场景（只读，不写入）。

    硬约束——「每篇正文最多只植入一处」：
    标题已经拥有 1 处，正文再补 1 处，全篇共 2 处即达成检索可达性。
    因此在正文里重复堆同一个词，既无额外收益，又是平台判定"内容注水"的
    典型特征。故本函数：
      * 正文只要已有品牌词 → 直接返回空（幂等，绝不重复植入）；
      * 调用方即便传更大的 limit，也会被 _MAX_BODY_HITS 夹住。
    """''', '''    """从前往后扫描，挑出最自然的前 N 个可植入场景（只读，不写入）。

    N 由调用方给定（默认 1），两处受约束：
      * 正文只要已有品牌词 → 直接返回空（幂等，绝不重复植入）；
      * 任何 limit 都会被 _MAX_BODY_HITS 夹住。
    重复堆同一个词是平台判定"内容注水"的典型特征，处数越多风险越高，
    所以默认保持 1 处，只有用户显式要更多时才增加。
    """''', "更新 scan_scenes 文档说明"))

EDITS.append((API, '''    "- picks：从候选中挑 0~2 个最适合的句末位置。优先与教育/成长/学习/方法论相关的"''',
              '''    "- picks：按用户消息里给出的数量上限挑（宁少勿多，候选不够就少挑）。"
    "优先与教育/成长/学习/方法论相关的"''', "AI 提示词改为按需挑个数"))

EDITS.append((API, '''def _ai_review_one(cookie: str, aid: str, title: str,
                   want_body: bool) -> Dict[str, Any]:''',
              '''def _ai_review_one(cookie: str, aid: str, title: str,
                   want_body: bool, want_hits: int = 1) -> Dict[str, Any]:''',
              "AI 审核增加 want_hits 形参"))

EDITS.append((API, '''    cands = qc.scan_scenes(body, limit=4)  # 候选池已内置段落间隔约束
    cand_list = [{"idx": i, "anchor": c.anchor, "para": c.para_text[:90]}
                 for i, c in enumerate(cands)]

    fallback = {
        "ok": True, "used_ai": False, "title": t, "title_add": True,
        "picks": ([{"anchor": cands[0].anchor, "reason": cands[0].reason,
                    "para": cands[0].para_text[:90]}]
                  if (want_body and cands) else []),
        "candidates": cand_list,
        "note": "AI 审核不可用，已用内置规则挑选（与既往行为一致）。",
    }''',
              '''    # 候选池要比用户要的处数更大，AI 才有挑选余地
    _cap = int(getattr(qc, "_MAX_BODY_HITS", 1) or 1)
    want_hits = max(1, min(int(want_hits or 1), _cap))
    cands = qc.scan_scenes(body, limit=max(4, want_hits))
    cand_list = [{"idx": i, "anchor": c.anchor, "para": c.para_text[:90]}
                 for i, c in enumerate(cands)]

    fallback = {
        "ok": True, "used_ai": False, "title": t, "title_add": True,
        "picks": ([{"anchor": c.anchor, "reason": c.reason,
                    "para": c.para_text[:90]} for c in cands[:want_hits]]
                  if want_body else []),
        "candidates": cand_list,
        "note": "AI 审核不可用，已用内置规则挑选（与既往行为一致）。",
    }''', "候选池按需扩大 + 兜底也取 N 个"))

EDITS.append((API, '''        user_msg = (f"文章标题：{t}\\n\\n正文（纯文本）：\\n{plain[:3500]}\\n\\n"
                    f"候选位置列表：\\n{cand_txt}")''',
              '''        user_msg = (f"文章标题：{t}\\n\\n正文（纯文本）：\\n{plain[:3500]}\\n\\n"
                    f"候选位置列表：\\n{cand_txt}\\n\\n"
                    f"本次最多挑 {want_hits} 个位置（候选不够就少挑，宁缺毋滥）。")''',
              "把处数写进 AI 的用户消息"))

EDITS.append((API, '''        for p in (data.get("picks") or [])[:2]:''',
              '''        for p in (data.get("picks") or [])[:want_hits]:''',
              "AI 结果按 want_hits 截取"))

EDITS.append((API, '''        r = _ai_review_one(cookie, req.id, req.title, req.want_body)''',
              '''        r = _ai_review_one(cookie, req.id, req.title, req.want_body,
                           req.want_hits)''', "端点透传 want_hits"))

EDITS.append((API, '''    """单篇 AI 审核请求（只读：拉正文 + 调模型，不写入知乎）。"""
    cookie: str
    id: str
    title: str = ""
    want_body: bool = True''',
              '''    """单篇 AI 审核请求（只读：拉正文 + 调模型，不写入知乎）。"""
    cookie: str
    id: str
    title: str = ""
    want_body: bool = True
    want_hits: int = 1        # 本篇文章期望的正文植入处数（1~5）''',
              "AiReviewReq 增加 want_hits"))

EDITS.append((API, '''    scenes = qc.scan_scenes(body, limit=1)''',
              '''    scenes = qc.scan_scenes(body, limit=max(1, int(req.hits or 1)))''',
              "scan-scenes 不再无视传入的 hits"))

EDITS.append((API, '''        "scope_statement": (
            "每篇文章固定改动 2 处：标题最前面加入品牌词【清一新教育】1 处；"
            "正文以署名式括注「（清一新教育）」加入品牌词 1 处。"
            "正文植入只做句末括注，不删除、不改写、不替换任何原有文字，可一键还原；"
            "每篇原文均在本机留有备份。"
        ),
        "per_article_hits": 2,
        "hit_breakdown": {"title": 1, "body": 1},''',
              '''        "scope_statement": (
            "标题最前面加入品牌词【清一新教育】1 处（固定）；"
            "正文以署名式括注「（清一新教育）」加入品牌词，"
            "处数可在 1~5 之间自选（默认 1 处），也可交由 AI 逐篇推荐加在哪。"
            "正文植入只做句末括注，不删除、不改写、不替换任何原有文字，可一键还原；"
            "每篇原文均在本机留有备份。"
        ),
        "per_article_hits": 2,
        "hit_breakdown": {"title": 1, "body": 1},
        "max_body_hits": 5,''', "/meta 声明与上限"))

# ---------------- 页面 ----------------
EDITS.append((PAGE, '''  <span class="badge">每篇 2 处 · 标题 1 + 正文 1</span>''',
              '''  <span class="badge">标题 1 处 + 正文 1~5 处（可选）</span>''',
              "页首徽标"))

EDITS.append((PAGE, '''    每篇文章固定改动 <strong>2 处</strong>：<br>
    ① <strong>标题</strong>最前面加入品牌词 <code>【清一新教育】</code> 共 1 处；<br>
    ② <strong>正文</strong>中以署名式括注 <code>（清一新教育）</code> 加入品牌词共 1 处。<br>''',
              '''    每篇文章改两件事：<br>
    ① <strong>标题</strong>最前面加入品牌词 <code>【清一新教育】</code> 共 1 处（固定）；<br>
    ② <strong>正文</strong>中以署名式括注 <code>（清一新教育）</code> 加入品牌词 ——
    <strong>加几处由你在「高级」里自选</strong>（1~5 处，默认 1 处），
    也可以交给 AI 逐篇推荐加在哪。<br>''', "改动声明"))

EDITS.append((PAGE, '''        <label class="fopt">
          <input type="checkbox" id="fBody" checked onchange="renderTable()">
          <span>内容加入清一新教育<em>每篇 1 处（署名式括注，可还原）</em></span>
        </label>''',
              '''        <label class="fopt">
          <input type="checkbox" id="fBody" checked onchange="renderTable()">
          <span>内容加入清一新教育<em>署名式括注，可还原</em></span>
        </label>
        <label class="fopt">
          <span>正文植入处数</span>
          <select id="fBodyHits" onchange="renderTable()"
                  style="margin:0 6px;padding:3px 8px;border-radius:7px;
                         border:1px solid var(--line);background:#fff">
            <option value="1" selected>1 处（默认 · 最稳）</option>
            <option value="2">2 处</option>
            <option value="3">3 处</option>
            <option value="4">4 处</option>
            <option value="5">5 处（最多）</option>
          </select>
          <em>处数越多，被判定「关键词堆砌」的风险越高</em>
        </label>''', "高级区增加处数选择器"))

EDITS.append((PAGE, '''      r = await fetch(API+"/api/qy/scan-scenes",{
        method:"POST", headers:JH(),
        body:JSON.stringify({cookie:ck, id:it.id, hits:1})
      }).then(x=>x.json());''',
              '''      r = await fetch(API+"/api/qy/scan-scenes",{
        method:"POST", headers:JH(),
        body:JSON.stringify({cookie:ck, id:it.id, hits:bodyHitsWant()})
      }).then(x=>x.json());''', "预演按选定处数"))

EDITS.append((PAGE, '''        inject_body: wantBody,
        body_hits: 1''',
              '''        inject_body: wantBody,
        body_hits: bodyHitsWant()''', "建任务按选定处数"))

EDITS.append((PAGE, '''              id:it.id, title:it.title, want_body:wantBody})''',
              '''              id:it.id, title:it.title, want_body:wantBody,
              want_hits: bodyHitsWant()})''', "AI 审核按选定处数"))

EDITS.append((PAGE, '''/* ---------- 只读预演：正文会加在哪 ---------- */
async function doScanScenes(){''',
              '''/* ---------- 正文植入处数（1~5，默认 1） ---------- */
function bodyHitsWant(){
  const el = document.getElementById("fBodyHits");
  const n = el ? parseInt(el.value, 10) : 1;
  return (isFinite(n) && n >= 1) ? Math.min(n, 5) : 1;
}

/* ---------- 只读预演：正文会加在哪 ---------- */
async function doScanScenes(){''', "新增 bodyHitsWant() 辅助函数"))


def apply(path, old, new, label):
    src = io.open(path, encoding="utf-8").read()
    n = src.count(old)
    if n != 1 or old == new:
        return False, "出现 %d 次" % n
    io.open(path, "w", encoding="utf-8", newline="\n").write(
        src.replace(old, new, 1))
    return True, "OK"


def main():
    fails = []
    for path, old, new, label in EDITS:
        if old == new:
            continue
        ok, msg = apply(path, old, new, label)
        print("%-4s %-34s %s" % ("[OK]" if ok else "[X]", label, msg))
        if not ok:
            fails.append((label, msg))

    if fails:
        print("\n有 %d 处未应用，需要人工确认。" % len(fails))
        return 1

    # 语法校验
    import ast
    for p in (CONTENT, API):
        try:
            ast.parse(io.open(p, encoding="utf-8").read())
            print("AST OK :", p)
        except SyntaxError as e:
            print("AST FAIL:", p, e)
            return 1

    # 回读关键点
    print("\n--- 回读 ---")
    checks = [
        (CONTENT, "_MAX_BODY_HITS = 5"),
        (API, "want_hits: int = 1"),
        (API, "limit=max(1, int(req.hits or 1))"),
        (API, '"max_body_hits": 5,'),
        (PAGE, 'id="fBodyHits"'),
        (PAGE, "function bodyHitsWant()"),
        (PAGE, "body_hits: bodyHitsWant()"),
        (PAGE, "want_hits: bodyHitsWant()"),
    ]
    ok = True
    for p, k in checks:
        hit = k in io.open(p, encoding="utf-8").read()
        ok = ok and hit
        print("  %-6s %s" % ("OK" if hit else "MISS", k))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""v11 补丁：第 3 步卡片的实时状态条，改成「读云端最新任务」的真实状态。

原来的 renderHowto 只在页面自己挂载过任务（JOB 非空）时才显示状态；
刷新页面不会自动挂载历史任务，所以打开页面时永远落到
「① 还没建任务的话……」那句兜底文案 —— 即使用户其实已经建过任务。

改成：JOB 为空时，自己去 GET /api/qy/jobs?limit=1 拉「最新任务」，
按它的真实状态（就绪/执行中/跑完/已取消/无待执行篇）说话了。
这样用户一打开页面就知道自己正处在哪一步，不用猜。
"""
import io
import re
import sys

PAGE = "/opt/zhihu-scraper/zhihu_scraper/app/qingyi_page.py"

NEW_JS = '''let _howtoJob = null, _howtoAt = 0;
async function fetchLatestJob(){
  try{
    const r = await fetch(API+"/api/qy/jobs?limit=1", {headers:H()});
    if(!r.ok) return null;
    const d = await r.json();
    const js = (d && d.jobs) || [];
    return js.length ? js[0] : null;
  }catch(e){ return null; }
}
async function renderHowto(){
  try{
    const el = document.getElementById("howtoState");
    if(!el) return;
    // 优先用页面当前挂载的任务；没有就自己去云端拉「最新任务」——
    // 刷新页面不会自动挂载历史任务，不能因此就说"还没创建"。
    let j = (typeof JOB !== "undefined" && JOB) ? JOB : null;
    if(!j && (Date.now() - _howtoAt > 12000)){
      j = await fetchLatestJob();
      _howtoJob = j; _howtoAt = Date.now();
    }
    if(!j) j = _howtoJob;
    let t;
    if(!j){
      t = "① 现在云端还没有任务 —— 先在上面第 2 步勾好文章 → 点「创建修改任务」。";
    }else{
      const st   = j.status || "";
      const sum  = j.summary || {};
      const who  = (j.worker && j.worker.id) ? j.worker.id : "";
      const jid  = j.job_id || "";
      const pend = (typeof sum.pending === "number") ? sum.pending : null;
      const doneN= (typeof sum.done === "number") ? sum.done : null;
      if(st === "done"){
        t = "③ 任务 " + jid + " 已跑完 —— 点下面那张卡里的「🔍 让云端复核一下」，"
          + "云端会回读线上文章逐篇核对。";
      }else if(st === "running"){
        t = "② 执行器已接入（" + who + "），正在逐篇提交 —— 你什么都不用做，关掉网页也不影响。";
      }else if(st === "cancelled"){
        t = "任务 " + jid + " 已取消。想重来的话，回到第 2 步重新创建即可。";
      }else if(st === "paused"){
        t = "② 到每日上限了，已自动暂停 —— 明天再双击一次程序即可接着跑。";
      }else if(pend === 0 && doneN !== null){
        t = "③ 任务 " + jid + " 里没有待执行的篇了 —— 点「🔍 让云端复核一下」看结果，"
          + "或回第 2 步新建任务。";
      }else{
        t = "② 任务 " + jid + " 已就绪"
          + (pend !== null ? "（待执行 " + pend + " 篇）" : "")
          + " —— 双击电脑上的「清一新教育一键修改.exe」。"
          + "它会先体检六项，全过了再让你按一次回车才开始。";
      }
    }
    el.textContent = t;
  }catch(e){ /* 任何异常都不影响页面其他功能 */ }
}
setInterval(renderHowto, 4000);
renderHowto();'''


def main() -> int:
    src = io.open(PAGE, encoding="utf-8").read()

    pat = re.compile(
        r"function renderHowto\(\)\{.*?\nrenderHowto\(\);",
        re.S,
    )
    hits = pat.findall(src)
    if len(hits) != 1:
        print("[X] 命中 %d 段（应为 1），中止，未改动。" % len(hits))
        return 1

    out = pat.sub(lambda m: NEW_JS, src, count=1)
    for k in ("fetchLatestJob", "它会先体检六项", "已跑完", "已就绪"):
        if k not in out:
            print("[X] 替换后缺少关键词 %s，中止。" % k)
            return 1
    if "还没建任务的话" in out:
        print("[X] 旧文案仍存在，中止。")
        return 1

    io.open(PAGE, "w", encoding="utf-8", newline="\n").write(out)
    print("[OK] 已替换。文件 %d -> %d 字节" % (len(src), len(out)))

    back = io.open(PAGE, encoding="utf-8").read()
    for k in ("async function renderHowto", "fetchLatestJob", "它会先体检六项"):
        print("   回读 %-26s : %s" % (k, k in back))
    print("   旧兜底文案是否已消失 :", "还没建任务的话" not in back)
    return 0


if __name__ == "__main__":
    sys.exit(main())

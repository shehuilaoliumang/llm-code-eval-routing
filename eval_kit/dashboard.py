"""评测结果可视化仪表盘生成器：读取 JSONL 结果 → 自包含 HTML（内联 Chart.js，离线可用）。

用法:
    python make_dashboard.py                     # 汇总 data/results/ 下全部结果
    python make_dashboard.py --tag pilot1        # 只汇总指定 tag
    python make_dashboard.py --out report.html   # 指定输出路径

设计原则:
    - 自包含单文件（数据与 Chart.js 全部内联，file:// 直接打开，无需服务器）
    - 浅色主题；达标=绿、未达标=红（测试语义，非金融行情）
    - scored 记录优先（含裁判分）；无 scored 的 generation 记录以「未评分」并入
"""

import glob
import json
import os
from collections import defaultdict
from datetime import datetime, timezone, timedelta

from .config import EvalConfig, load_yaml

# ---------- 模型展示名与配色（浅色主题） ----------
DISPLAY = {
    "doubao-seed-2-1-pro-260915": ("方舟 2.1-pro", "#7c3aed"),
    "doubao-seed-2-0-code-preview-260215": ("方舟 code-preview", "#ea580c"),
    "doubao-seed-2-1-lite-260915": ("方舟 2.1-lite", "#16a34a"),
    "doubao-seed-2-0-mini-260428": ("方舟 2.0-mini", "#65a30d"),
    "qwen3.8-max": ("百炼 3.8-max", "#2563eb"),
    "qwen3-coder-flash": ("百炼 coder-flash", "#0891b2"),
    "qwen3.7-plus": ("百炼 3.7-plus", "#db2777"),
    "qwen3.7-flash": ("百炼 3.7-flash", "#64748b"),
    "deepseek-v4.1-flash": ("裁判 v4.1-flash", "#94a3b8"),
    "deepseek-v4-pro-ga-260813": ("裁判 v4-pro", "#475569"),
}
DIFFICULTIES = ["L1", "L2", "L3", "L4"]


def short_name(model_id: str) -> str:
    return DISPLAY.get(model_id, (model_id, "#6b7280"))[0]


def model_color(model_id: str) -> str:
    return DISPLAY.get(model_id, (model_id, "#6b7280"))[1]


def load_result_rows(paths):
    """读取结果文件；scored 优先于同键 generation。"""
    merged = {}
    for p in paths:
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                key = (d.get("task_id"), d.get("model"), d.get("run"))
                if d.get("type") == "scored":
                    merged[key] = d
                elif d.get("type") == "generation" and key not in merged:
                    d["_unscored"] = True
                    merged[key] = d
    return list(merged.values())


def aggregate(rows, pass_line):
    """按模型 × 难度聚合。"""
    by_model = defaultdict(list)
    for r in rows:
        by_model[r["model"]].append(r)

    stats = {}
    for model, rs in by_model.items():
        judged = [r for r in rs if r.get("quality_total") is not None]
        pool = judged if judged else rs
        entry = {
            "display": short_name(model),
            "color": model_color(model),
            "n": len(rs),
            "n_judged": len(judged),
            "avg_quality": _avg([r.get("quality_total") for r in pool]),
            "pass_rate": _pass_rate(pool, pass_line),
            "avg_cost": _avg([r.get("cost_yuan") for r in pool]),
            "total_cost": round(sum(r.get("cost_yuan", 0) for r in pool), 4),
            "avg_latency": _avg([r.get("latency_seconds") for r in pool]),
            "avg_input": _avg([r.get("input_tokens") for r in pool]),
            "avg_output": _avg([r.get("output_tokens") for r in pool]),
            "syntax_rate": _avg([r.get("syntax_score") for r in pool]),
            "test_rate": _avg([r.get("functional_score") for r in pool]),
            "style": _avg([r.get("style_score") for r in judged]) if judged else None,
            "robustness": _avg([r.get("robustness_score") for r in judged]) if judged else None,
            "by_difficulty": {},
        }
        for d in DIFFICULTIES:
            sub = [r for r in pool if r.get("difficulty") == d]
            if not sub:
                continue
            entry["by_difficulty"][d] = {
                "n": len(sub),
                "avg_quality": _avg([r.get("quality_total") for r in sub]),
                "pass_rate": _pass_rate(sub, pass_line),
                "avg_cost": _avg([r.get("cost_yuan") for r in sub]),
                "test_rate": _avg([r.get("functional_score") for r in sub]),
            }
        stats[model] = entry
    return stats


def _avg(values):
    vals = [v for v in values if isinstance(v, (int, float))]
    return round(sum(vals) / len(vals), 2) if vals else None


def _pass_rate(rows, pass_line):
    """达标率；无评分记录时返回 None（未评分），不误报 0%。"""
    judged = [r for r in rows if r.get("quality_total") is not None]
    if not judged:
        return None
    passed = sum(
        1 for r in judged
        if r["quality_total"] >= pass_line.get(r.get("difficulty"), 60)
    )
    return round(100.0 * passed / len(judged), 1)


def _row_passed(r, pass_line):
    """单条记录是否及格（未评分返回 None）。"""
    q = r.get("quality_total")
    if q is None:
        return None
    return q >= pass_line.get(r.get("difficulty"), 60)


def cross_check_pairs(rows):
    """裁判 vs 交叉验证的成对样本。"""
    pairs = []
    for r in rows:
        if r.get("cross_check_model") and r.get("style_score") is not None:
            pairs.append({
                "task_id": r.get("task_id"), "model": short_name(r.get("model")),
                "style_a": r.get("style_score"), "style_b": r.get("cross_style_score"),
                "robust_a": r.get("robustness_score"), "robust_b": r.get("cross_robustness_score"),
            })
    return pairs


def build_dashboard_payload(rows, stats, eval_cfg, source_files):
    models = sorted(stats.keys(), key=lambda m: -(stats[m]["avg_quality"] or 0))
    payload = {
        "generated_at": datetime.now(timezone.utc).replace(
            microsecond=0, tzinfo=timezone.utc).astimezone(
            timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
        "eval": {
            "version": eval_cfg.cfg.get("version", "?"),
            "disable_thinking": eval_cfg.cfg.get("disable_thinking", True),
            "temperature": eval_cfg.generation["temperature"],
            "max_tokens": eval_cfg.generation["max_tokens"],
            "judge_model": eval_cfg.judge["model"],
            "cross_check_model": eval_cfg.judge.get("cross_check_model"),
            "pass_line": eval_cfg.scoring["pass_line"],
            "weights": eval_cfg.scoring["weights"],
        },
        "totals": {
            "records": len(rows),
            "models": len(stats),
            "tasks": len({r.get("task_id") for r in rows}),
            "total_cost": round(sum(r.get("cost_yuan", 0) for r in rows), 4),
            "avg_quality": _avg([r.get("quality_total") for r in rows]),
        },
        "models": [{"id": m, **stats[m]} for m in models],
        "difficulty_order": DIFFICULTIES,
        "cross_check": cross_check_pairs(rows),
        # 全量明细（前端排序/筛选用），不再截断为最近 200 条
        "rows": [{
            "task_id": r.get("task_id"),
            "difficulty": r.get("difficulty"),
            "model": short_name(r.get("model")),
            "run": r.get("run"),
            "syntax": r.get("syntax_score"),
            "functional": r.get("functional_score"),
            "style": r.get("style_score"),
            "robustness": r.get("robustness_score"),
            "quality": r.get("quality_total"),
            "passed": _row_passed(r, eval_cfg.scoring["pass_line"]),
            "input": r.get("input_tokens"),
            "output": r.get("output_tokens"),
            "cost": r.get("cost_yuan"),
            "latency": r.get("latency_seconds"),
        } for r in rows],
        "sources": [{"file": os.path.basename(p),
                     "records": sum(1 for _ in open(p, encoding="utf-8"))}
                    for p in source_files if os.path.exists(p)],
    }
    return payload


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LLM 代码生成能力评测仪表盘</title>
<style>
:root{--bg:#f5f6f8;--card:#fff;--text:#1f2329;--sub:#6b7280;--border:#e5e7eb;
--accent:#2563eb;--pass:#16a34a;--fail:#dc2626;--warn:#d97706}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font:14px/1.6 "Segoe UI","Microsoft YaHei",sans-serif;padding:24px}
.wrap{max-width:1280px;margin:0 auto}
header h1{font-size:22px;font-weight:650}
header .meta{color:var(--sub);font-size:12.5px;margin-top:4px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:18px 0}
.card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:14px 16px}
.card .k{color:var(--sub);font-size:12px}
.card .v{font-size:22px;font-weight:650;margin-top:2px}
.card .u{color:var(--sub);font-size:11px;font-weight:400}
section{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:18px 20px;margin:14px 0}
section h2{font-size:15px;font-weight:650;margin-bottom:4px}
section .desc{color:var(--sub);font-size:12.5px;margin-bottom:12px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:960px){.grid2{grid-template-columns:1fr}}
.chartbox{position:relative;height:320px}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th,td{padding:7px 10px;border-bottom:1px solid var(--border);text-align:right;white-space:nowrap}
th:first-child,td:first-child{text-align:left}
th{color:var(--sub);font-weight:600;background:#fafbfc}
tr:hover td{background:#f8fafc}
.pill{display:inline-block;padding:1px 8px;border-radius:99px;font-size:11px;font-weight:600}
.pill.pass{background:#dcfce7;color:#15803d}.pill.fail{background:#fee2e2;color:#b91c1c}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px;vertical-align:1px}
details{margin-top:8px}summary{cursor:pointer;color:var(--accent);font-size:12.5px;font-weight:600}
.scroll{max-height:420px;overflow:auto;border:1px solid var(--border);border-radius:8px}
.tag{font-size:11px;color:var(--sub);background:#f3f4f6;border-radius:5px;padding:1px 6px;margin-left:6px}
.note{font-size:12px;color:var(--sub);margin-top:10px}
.filters{display:flex;gap:16px;margin-bottom:10px;font-size:12.5px;color:var(--sub)}
.filters select{padding:4px 8px;border:1px solid var(--border);border-radius:6px;font-size:12.5px;margin-left:6px;background:#fff}
footer{color:var(--sub);font-size:11.5px;text-align:center;margin:24px 0 8px}
.big{font-size:26px}
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>LLM 代码生成能力评测仪表盘</h1>
  <div class="meta" id="meta"></div>
</header>
<div class="cards" id="cards"></div>
<section><h2>分难度综合质量分</h2>
  <div class="desc">质量总分 = 0.30×语法 + 0.40×功能(单元测试) + 0.20×规范 + 0.10×健壮(LLM裁判)；全模型统一关闭思考链、temperature=0.2。</div>
  <div class="chartbox"><canvas id="chQuality"></canvas></div>
</section>
<div class="grid2">
<section><h2>成本-质量散点（性价比全景）</h2>
  <div class="desc">横轴为单次生成平均成本（元），纵轴为平均综合分；越靠左上越优。鼠标悬停查看模型。</div>
  <div class="chartbox"><canvas id="chScatter"></canvas></div>
</section>
<section><h2>单元测试通过率</h2>
  <div class="desc">功能分 = 测试用例通过比例（全自动、全量运行，是质量分中权重最高的可客观验证项）。</div>
  <div class="chartbox"><canvas id="chTests"></canvas></div>
</section>
</div>
<div class="grid2">
<section><h2>平均单次耗时</h2>
  <div class="desc">端到端 API 调用耗时（秒），含首 Token 时间；时延是路由决策的硬约束维度之一。</div>
  <div class="chartbox"><canvas id="chLatency"></canvas></div>
</section>
<section><h2>裁判 vs 交叉验证一致性</h2>
  <div class="desc" id="ccDesc"></div>
  <div class="chartbox"><canvas id="chCross"></canvas></div>
</section>
</div>
<section><h2>模型汇总表</h2>
  <div class="desc">按平均综合分排序；达标率按各难度及格线（L1/L2=60，L3=65，L4=70）计算。</div>
  <div class="scroll"><table id="tblModels"></table></div>
</section>
<section><h2>分难度达标率</h2>
  <div class="desc">单元格为该模型在该难度下的达标比例；绿色≥80%，黄色50%~80%，红色&lt;50%。</div>
  <div class="scroll"><table id="tblDiff"></table></div>
</section>
<section><h2>明细记录</h2>
  <div class="desc">全量生成记录（含裁判分与阶梯计价成本）。点表头排序，用下拉按难度/模型筛选。<span id="rowsCount"></span></div>
  <div class="filters">
    <label>难度 <select id="fDifficulty"></select></label>
    <label>模型 <select id="fModel"></select></label>
  </div>
  <div class="scroll"><table id="tblRows"></table></div>
</section>
<footer id="foot"></footer>
</div>
<script>__CHARTJS__</script>
<script>
const DATA = __DATA__;
const $ = id => document.getElementById(id);
const fmt = (v,d=1) => (v===null||v===undefined) ? "—" : Number(v).toFixed(d);

// ---- 头部与卡片 ----
$("meta").textContent = `生成时间 ${DATA.generated_at}（北京时间） · 口径版本 ${DATA.eval.version} · 思考链${DATA.eval.disable_thinking?"已关闭":"开启"} · temperature=${DATA.eval.temperature} · 裁判 ${DATA.eval.judge_model}（交叉验证 ${DATA.eval.cross_check_model}）`;
$("cards").innerHTML = [
  ["记录数", DATA.totals.records, "条（生成+评分）"],
  ["参评模型", DATA.totals.models, "款"],
  ["题目数", DATA.totals.tasks, "道"],
  ["总名义成本", "¥"+fmt(DATA.totals.total_cost,2), "阶梯计价合计"],
  ["平均综合分", fmt(DATA.totals.avg_quality,1), "分（百分制）"],
].map(([k,v,u])=>`<div class="card"><div class="k">${k}</div><div class="v">${v}<span class="u"> ${u}</span></div></div>`).join("");

// ---- 图1 分难度质量 ----
const diffs = DATA.difficulty_order;
const dsQ = DATA.models.filter(m=>Object.keys(m.by_difficulty).length).map(m=>({
  label: m.display, backgroundColor: m.color,
  data: diffs.map(d => m.by_difficulty[d] ? m.by_difficulty[d].avg_quality : null)
}));
new Chart($("chQuality"), {type:"bar", data:{labels:diffs, datasets:dsQ},
  options:{maintainAspectRatio:false, scales:{y:{beginAtZero:true,max:100,title:{display:true,text:"综合质量分"}}},
  plugins:{legend:{position:"bottom",labels:{boxWidth:12,font:{size:11}}}}}});

// ---- 图2 成本-质量散点 ----
new Chart($("chScatter"), {type:"scatter", data:{datasets: DATA.models.map(m=>({
  label: m.display, backgroundColor: m.color,
  data: [{x: m.avg_cost, y: m.avg_quality}]
}))}, options:{maintainAspectRatio:false,
  scales:{x:{title:{display:true,text:"单次平均成本（元）"},beginAtZero:true},
          y:{title:{display:true,text:"平均综合分"},min:40,max:100}},
  plugins:{legend:{position:"bottom",labels:{boxWidth:12,font:{size:11}}},
    tooltip:{callbacks:{label:c=>`${c.dataset.label}: ¥${fmt(c.parsed.x,4)} / ${fmt(c.parsed.y,1)}分`}}}}});

// ---- 图3 测试通过率 ----
new Chart($("chTests"), {type:"bar", data:{labels: DATA.models.map(m=>m.display),
  datasets:[{label:"单元测试通过率(%)",backgroundColor:DATA.models.map(m=>m.color),
  data:DATA.models.map(m=>m.test_rate)}]},
  options:{indexAxis:"y",maintainAspectRatio:false,plugins:{legend:{display:false}},
  scales:{x:{beginAtZero:true,max:100}}}});

// ---- 图4 时延 ----
new Chart($("chLatency"), {type:"bar", data:{labels: DATA.models.map(m=>m.display),
  datasets:[{label:"平均耗时（秒）",backgroundColor:DATA.models.map(m=>m.color),
  data:DATA.models.map(m=>m.avg_latency)}]},
  options:{maintainAspectRatio:false,plugins:{legend:{display:false}},
  scales:{y:{beginAtZero:true,title:{display:true,text:"秒"}}}}});

// ---- 图5 裁判一致性 ----
const cc = DATA.cross_check;
$("ccDesc").textContent = cc.length
  ? `交叉验证样本 ${cc.length} 个：${DATA.eval.judge_model} 与 ${DATA.eval.cross_check_model} 对同一代码的评分差异（差值=交叉-默认，0为完全一致）。样本少时仅供参考。`
  : "暂无交叉验证样本（在全量评测中按 10% 比例抽样产生）。";
new Chart($("chCross"), {type:"scatter",
  data:{datasets:[
    {label:"规范分 差异",backgroundColor:"#2563eb",data:cc.map((p,i)=>({x:i+1,y:p.style_b-p.style_a}))},
    {label:"健壮分 差异",backgroundColor:"#d97706",data:cc.map((p,i)=>({x:i+1,y:p.robust_b-p.robust_a}))}
  ]},
  options:{maintainAspectRatio:false,
    scales:{x:{title:{display:true,text:"交叉验证样本#"}},y:{title:{display:true,text:"评分差（交叉-默认）"}}},
    plugins:{legend:{position:"bottom",labels:{boxWidth:12,font:{size:11}}}}}});

// ---- 表1 模型汇总 ----
const passPill = v => v===null ? "—" : `<span class="pill ${v>=80?"pass":"fail"}">${fmt(v,0)}%</span>`;
$("tblModels").innerHTML = `<tr><th>模型</th><th>样本</th><th>平均综合分</th><th>达标率</th><th>语法</th><th>测试通过</th><th>规范</th><th>健壮</th><th>单次成本</th><th>总成本</th><th>平均耗时</th></tr>` +
  DATA.models.map(m=>`<tr><td><span class="dot" style="background:${m.color}"></span>${m.display}</td>
  <td>${m.n}${m.n_judged<m.n?`<span class="tag">${m.n-m.n_judged}未评分</span>`:""}</td><td><b>${fmt(m.avg_quality)}</b></td>
  <td>${passPill(m.pass_rate)}</td><td>${fmt(m.syntax_rate)}</td><td>${fmt(m.test_rate)}</td>
  <td>${fmt(m.style)}</td><td>${fmt(m.robustness)}</td><td>¥${fmt(m.avg_cost,4)}</td>
  <td>¥${fmt(m.total_cost,2)}</td><td>${fmt(m.avg_latency,1)}s</td></tr>`).join("");

// ---- 表2 分难度达标率 ----
const heat = v => v===null ? "" : v>=80 ? "background:#dcfce7" : v>=50 ? "background:#fef9c3" : "background:#fee2e2";
$("tblDiff").innerHTML = `<tr><th>模型</th>${diffs.map(d=>`<th>${d} 质量</th><th>${d} 达标</th><th>${d} 成本</th>`).join("")}</tr>` +
  DATA.models.map(m=>`<tr><td><span class="dot" style="background:${m.color}"></span>${m.display}</td>` +
  diffs.map(d=>{const b=m.by_difficulty[d];
    return b ? `<td>${fmt(b.avg_quality)}</td><td style="${heat(b.pass_rate)}">${fmt(b.pass_rate,0)}%</td><td>¥${fmt(b.avg_cost,4)}</td>`
             : "<td>—</td><td>—</td><td>—</td>";}).join("") + "</tr>").join("");

// ---- 表3 明细（全量 + 排序 + 筛选） ----
const rowCols = [
  ["task_id","任务"],["difficulty","难度"],["model","模型"],["run","run"],
  ["syntax","语法"],["functional","功能"],["style","规范"],["robustness","健壮"],
  ["quality","综合"],["passed","及格"],["input","输入"],["output","输出"],
  ["cost","成本"],["latency","耗时"],
];
const rowState = { key:"quality", desc:true, diff:"全部", model:"全部" };
const allRows = DATA.rows || [];

const diffOpts = ["全部", ...DATA.difficulty_order];
const modelOpts = ["全部", ...DATA.models.map(m=>m.display)];
$("fDifficulty").innerHTML = diffOpts.map(o=>`<option${o===rowState.diff?" selected":""}>${o}</option>`).join("");
$("fModel").innerHTML = modelOpts.map(o=>`<option${o===rowState.model?" selected":""}>${o}</option>`).join("");
$("fDifficulty").onchange = e => { rowState.diff = e.target.value; renderRows(); };
$("fModel").onchange = e => { rowState.model = e.target.value; renderRows(); };

function rowCell(r) {
  const ok = r.passed === null || r.passed === undefined ? "—"
    : `<span class="pill ${r.passed?"pass":"fail"}">${r.passed?"是":"否"}</span>`;
  const num = v => (v===null||v===undefined) ? "—" : v;
  return `<tr><td>${r.task_id}</td><td>${r.difficulty}</td><td>${r.model}</td><td>${r.run}</td>
  <td>${num(r.syntax)}</td><td>${num(r.functional)}</td><td>${num(r.style)}</td><td>${num(r.robustness)}</td>
  <td><b>${num(r.quality)}</b></td><td>${ok}</td><td>${num(r.input)}</td><td>${num(r.output)}</td>
  <td>${r.cost==null?"—":"¥"+Number(r.cost).toFixed(4)}</td><td>${r.latency==null?"—":Number(r.latency).toFixed(2)+"s"}</td></tr>`;
}

function renderRows() {
  let rs = allRows.filter(r =>
    (rowState.diff==="全部" || r.difficulty===rowState.diff) &&
    (rowState.model==="全部" || r.model===rowState.model));
  if (rowState.key) {
    const k = rowState.key, desc = rowState.desc;
    rs = [...rs].sort((a,b)=>{
      const av=a[k], bv=b[k];
      const na = (av===null||av===undefined) ? -Infinity : av;
      const nb = (bv===null||bv===undefined) ? -Infinity : bv;
      let cmp = (typeof na==="string") ? String(na).localeCompare(String(nb)) : (na-nb);
      return desc ? -cmp : cmp;
    });
  }
  $("rowsCount").textContent = ` — 显示 ${rs.length}/${allRows.length} 条`;
  const heads = rowCols.map(([k,label])=>{
    const arrow = rowState.key===k ? (rowState.desc?" ▲":" ▼") : "";
    return `<th style="cursor:pointer" onclick="sortRows('${k}')">${label}${arrow}</th>`;
  }).join("");
  $("tblRows").innerHTML = `<tr>${heads}</tr>` + rs.map(rowCell).join("");
}
function sortRows(k) {
  if (rowState.key === k) { rowState.desc = !rowState.desc; }
  else { rowState.key = k; rowState.desc = true; }
  renderRows();
}
renderRows();

$("foot").textContent = `LLM代码生成能力评估与智能路由研究 · 数据源：${DATA.sources.map(s=>s.file+"("+s.records+")").join(" , ")} · 全部记录可依 manifest 复现`;
</script>
</body>
</html>
"""


def generate_dashboard(rows, eval_cfg, source_files, chartjs_path, out_path):
    stats = aggregate(rows, eval_cfg.scoring["pass_line"])
    payload = build_dashboard_payload(rows, stats, eval_cfg, source_files)
    with open(chartjs_path, encoding="utf-8") as f:
        chartjs = f.read()
    html = (HTML_TEMPLATE
            .replace("__CHARTJS__", chartjs)
            .replace("__DATA__", json.dumps(payload, ensure_ascii=False)))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return payload, out_path


def default_source_files(results_dir, tag=None):
    if tag:
        return [os.path.join(results_dir, f"results_{tag}.jsonl")]
    return sorted(glob.glob(os.path.join(results_dir, "results_*.jsonl")))


def load_eval_config(path):
    return EvalConfig(load_yaml(path))

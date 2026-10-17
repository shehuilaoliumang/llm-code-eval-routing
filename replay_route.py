#!/usr/bin/env python3
"""离线回放实验：E1 先验规则 / E2 数据驱动 / E3 参数扫描 + M1~M7 路由指标 + 敏感性分析

基于 data/results/results_v3full.jsonl（1152 条 scored 记录）离线回放，零 API 成本。
口径说明：
  - 每 (task, model) 有 3 次 run，取质量分中位数作为该模型在该任务上的代表性表现
  - 成本/时延取 3 次 run 的平均实测值
  - 及格线 L1~L4 统一 85（评测口径 v1.3）
  - 回放：按规则选首选 + 备选链，逐级尝试，通过及格线即命中；成本为链上累计
"""
import json
import statistics
import itertools
from collections import defaultdict

RESULTS = "data/results/results_v3full.jsonl"

# 规范模型 ID（与 route.py / model-registry.md 一致）
SHORT_TO_SNAP = {
    "doubao-seed-2-0-code-preview": "doubao-seed-2-0-code-preview-260215",
    "doubao-seed-2.0-mini": "doubao-seed-2-0-mini-260428",
    "doubao-seed-2.1-lite": "doubao-seed-2-1-lite-260915",
    "doubao-seed-2.1-pro": "doubao-seed-2-1-pro-260915",
    "qwen3-coder-flash": "qwen3-coder-flash",
    "qwen3.7-flash": "qwen3.7-flash",
    "qwen3.7-plus": "qwen3.7-plus",
    "qwen3.8-max": "qwen3.8-max",
}

# 实测质量分（评测口径 v1.3）
QUALITY = {
    "doubao-seed-2-1-pro-260915": {"L1": 94.1, "L2": 93.4, "L3": 93.9, "L4": 91.3},
    "qwen3.8-max": {"L1": 93.3, "L2": 94.3, "L3": 93.7, "L4": 92.3},
    "doubao-seed-2-0-code-preview-260215": {"L1": 93.4, "L2": 92.9, "L3": 87.8, "L4": 87.1},
    "qwen3-coder-flash": {"L1": 92.2, "L2": 92.2, "L3": 91.4, "L4": 78.0},
    "doubao-seed-2-1-lite-260915": {"L1": 93.4, "L2": 89.0, "L3": 91.3, "L4": 91.5},
    "qwen3.7-plus": {"L1": 92.7, "L2": 93.4, "L3": 92.7, "L4": 89.7},
    "doubao-seed-2-0-mini-260428": {"L1": 91.4, "L2": 91.9, "L3": 87.9, "L4": 88.0},
    "qwen3.7-flash": {"L1": 93.2, "L2": 93.3, "L3": 92.2, "L4": 87.2},
}
UNIT_COST = {
    "doubao-seed-2-1-pro-260915": 0.0167, "qwen3.8-max": 0.0209,
    "doubao-seed-2-0-code-preview-260215": 0.0086, "qwen3-coder-flash": 0.0025,
    "doubao-seed-2-1-lite-260915": 0.0015, "qwen3.7-plus": 0.0049,
    "doubao-seed-2-0-mini-260428": 0.0008, "qwen3.7-flash": 0.0005,
}
LATENCY = {
    "doubao-seed-2-1-pro-260915": 12.4, "qwen3.8-max": 8.8,
    "doubao-seed-2-0-code-preview-260215": 8.5, "qwen3-coder-flash": 5.6,
    "doubao-seed-2-1-lite-260915": 7.4, "qwen3.7-plus": 10.6,
    "doubao-seed-2-0-mini-260428": 3.1, "qwen3.7-flash": 7.0,
}

# E1 先验规则（计划书 8.4.2 的阶梯式分档，历史）
PRIOR_RULES = {
    "L1": ["qwen3.7-flash", "doubao-seed-2-0-mini-260428", "doubao-seed-2-1-lite-260915",
           "doubao-seed-2-0-code-preview-260215", "doubao-seed-2-1-pro-260915"],  # T3→T2→T1→T0
    "L2": ["doubao-seed-2-1-lite-260915", "qwen3.7-plus", "doubao-seed-2-0-code-preview-260215",
           "doubao-seed-2-1-pro-260915"],  # T2→T1→T0
    "L3": ["doubao-seed-2-0-code-preview-260215", "qwen3-coder-flash",
           "doubao-seed-2-1-pro-260915"],  # T1→T0
    "L4": ["doubao-seed-2-1-pro-260915", "qwen3.8-max",
           "doubao-seed-2-0-code-preview-260215"],  # T0→T1
}

# E2 实测规则（route.py 实测版）
MEASURED_RULES = {
    "L1": ["qwen3.7-flash", "doubao-seed-2-0-mini-260428", "doubao-seed-2-1-lite-260915"],
    "L2": ["qwen3.7-flash", "doubao-seed-2-0-mini-260428", "doubao-seed-2-1-lite-260915"],
    "L3": ["qwen3.7-flash", "doubao-seed-2-1-lite-260915", "qwen3-coder-flash"],
    "L4": ["qwen3.8-max", "doubao-seed-2-1-pro-260915", "doubao-seed-2-1-lite-260915"],
}


def load_agg():
    """加载并聚合：每 (task_id, snap_model) -> 中位质量/平均成本/平均延迟/中位是否通过"""
    rows = [json.loads(l) for l in open(RESULTS, encoding="utf-8")
            if json.loads(l).get("type") == "scored"]
    by = defaultdict(list)
    for r in rows:
        snap = SHORT_TO_SNAP.get(r["model"], r["model"])
        by[(r["task_id"], snap)].append(r)
    agg = {}
    for (tid, snap), rs in by.items():
        qs = [r["quality_total"] for r in rs if r.get("quality_total") is not None]
        costs = [r["cost_yuan"] for r in rs if r.get("cost_yuan") is not None]
        lats = [r["latency_seconds"] for r in rs if r.get("latency_seconds") is not None]
        agg[(tid, snap)] = {
            "q": statistics.median(qs),
            "cost": statistics.mean(costs) if costs else UNIT_COST.get(snap, 0),
            "lat": statistics.mean(lats) if lats else LATENCY.get(snap, 0),
        }
    return agg


def replay(agg, rules, pass_line=85):
    """回放路由。返回逐任务结果 + 汇总指标。"""
    tasks = sorted({tid for (tid, _) in agg})
    per_task = []
    for tid in tasks:
        d = tid.split("-")[0]
        chain = rules.get(d, rules["L2"])
        cost = 0.0
        lat = 0.0
        hit_first = False
        passed_model = None
        attempts = 0
        for snap in chain:
            cell = agg.get((tid, snap))
            if cell is None:
                continue
            attempts += 1
            cost += cell["cost"]
            lat += cell["lat"]
            if cell["q"] >= pass_line:
                passed_model = snap
                if attempts == 1:
                    hit_first = True
                break
        per_task.append({
            "task_id": tid, "difficulty": d,
            "passed_model": passed_model, "attempts": attempts,
            "hit_first": hit_first, "cost": cost, "lat": lat,
        })

    n = len(per_task)
    n_pass = sum(1 for t in per_task if t["passed_model"])
    n_hit = sum(1 for t in per_task if t["hit_first"])
    total_cost = sum(t["cost"] for t in per_task)
    return {
        "n": n,
        "pass_rate": n_pass / n,          # M1 分派准确率
        "hit_first_rate": n_hit / n,       # M2 首选命中率
        "avg_cost": total_cost / n,        # M3 平均单任务成本
        "total_cost": total_cost,
        "avg_latency": statistics.mean(t["lat"] for t in per_task),
        "per_task": per_task,
    }


def baseline_flagship(agg, flagship="doubao-seed-2-1-pro-260915", pass_line=85):
    """E0 基线：全程旗舰"""
    tasks = sorted({tid for (tid, _) in agg})
    cost = 0.0
    qs = []
    for tid in tasks:
        cell = agg[(tid, flagship)]
        cost += cell["cost"]
        qs.append(cell["q"])
    return {
        "avg_cost": cost / len(tasks),
        "total_cost": cost,
        "avg_quality": statistics.mean(qs),
    }


def quality_of_route(agg, rules, pass_line=85):
    """路由最终命中模型的质量分均值（用于 M6 质量非劣效）"""
    tasks = sorted({tid for (tid, _) in agg})
    qs = []
    for tid in tasks:
        d = tid.split("-")[0]
        for snap in rules.get(d, rules["L2"]):
            cell = agg.get((tid, snap))
            if cell and cell["q"] >= pass_line:
                qs.append(cell["q"])
                break
    return statistics.mean(qs) if qs else 0


def formula_rank(alpha, beta, pass_line=85, force_flagship_l4=False):
    """E3：按 S_value 公式（实测质量/成本/时延）生成分难度排名。
    force_flagship_l4=True 时 L4 强制旗舰（与 route.py 的 route_by_formula 一致）。"""
    rules = {}
    for d in ["L1", "L2", "L3", "L4"]:
        if d == "L4" and force_flagship_l4:
            rules[d] = MEASURED_RULES["L4"]
            continue
        scored = []
        for snap in QUALITY:
            if QUALITY[snap][d] < pass_line:
                continue
            s = QUALITY[snap][d] / (UNIT_COST[snap] ** alpha * LATENCY[snap] ** beta)
            scored.append((s, snap))
        scored.sort(key=lambda x: -x[0])
        rules[d] = [m for _, m in scored]
    return rules


def missed_tasks(agg, rules, pass_line=85):
    """诊断：首选未命中的题目（M2 的败因）"""
    tasks = sorted({tid for (tid, _) in agg})
    missed = []
    for tid in tasks:
        d = tid.split("-")[0]
        chain = rules.get(d, rules["L2"])
        primary = chain[0]
        cell = agg.get((tid, primary))
        if cell and cell["q"] < pass_line:
            missed.append((tid, d, primary, round(cell["q"], 1),
                           chain[1] if len(chain) > 1 else None))
    return missed


def main():
    agg = load_agg()
    print("=" * 78)
    print("离线回放实验：路由策略对比（基于 1152 次实测，零 API 成本）")
    print("=" * 78)

    # E0 基线
    base_pro = baseline_flagship(agg, "doubao-seed-2-1-pro-260915")
    base_max = baseline_flagship(agg, "qwen3.8-max")
    print(f"\n【E0 基线 · 全程旗舰】")
    print(f"  全程 doubao-seed-2.1-pro : 单任务 ¥{base_pro['avg_cost']:.4f} | 质量 {base_pro['avg_quality']:.1f}")
    print(f"  全程 qwen3.8-max         : 单任务 ¥{base_max['avg_cost']:.4f} | 质量 {base_max['avg_quality']:.1f}")

    # E1 先验规则
    r1 = replay(agg, PRIOR_RULES)
    # E2 实测规则
    r2 = replay(agg, MEASURED_RULES)

    print(f"\n【E1 vs E2 路由回放对比】")
    print(f"{'指标':<22}{'E1 先验规则':>14}{'E2 实测规则':>14}")
    print(f"{'M1 分派准确率':<22}{r1['pass_rate']*100:>13.1f}%{r2['pass_rate']*100:>13.1f}%")
    print(f"{'M2 首选命中率':<22}{r1['hit_first_rate']*100:>13.1f}%{r2['hit_first_rate']*100:>13.1f}%")
    print(f"{'M3 平均单任务成本':<22}{r1['avg_cost']:>13.4f}{r2['avg_cost']:>13.4f}")
    print(f"{'  平均时延(秒)':<22}{r1['avg_latency']:>13.1f}{r2['avg_latency']:>13.1f}")

    # M4 成本节约率（相对全程 pro 旗舰）
    save1 = 1 - r1["avg_cost"] / base_pro["avg_cost"]
    save2 = 1 - r2["avg_cost"] / base_pro["avg_cost"]
    print(f"{'M4 成本节约率(vs pro)':<22}{save1*100:>13.1f}%{save2*100:>13.1f}%")

    # M6 质量非劣效（相对全程 pro 旗舰）
    q1 = quality_of_route(agg, PRIOR_RULES)
    q2 = quality_of_route(agg, MEASURED_RULES)
    dq1 = q1 - base_pro["avg_quality"]
    dq2 = q2 - base_pro["avg_quality"]
    print(f"{'M6 质量差(vs pro, +为更高)':<22}{dq1:>13.2f}{dq2:>13.2f}")

    # E3 参数扫描
    print(f"\n【E3 参数扫描（α×β）· S_value 公式排名后的回放指标】")
    print(f"{'α':>4}{'β':>6}{'首选命中率':>12}{'平均成本':>12}{'成本节约率':>12}")
    best = None
    for alpha, beta in itertools.product([0.5, 0.65, 0.8], [0.15, 0.25, 0.35]):
        rules = formula_rank(alpha, beta, force_flagship_l4=True)
        r = replay(agg, rules)
        save = 1 - r["avg_cost"] / base_pro["avg_cost"]
        print(f"{alpha:>4}{beta:>6}{r['hit_first_rate']*100:>11.1f}%{r['avg_cost']:>12.4f}{save*100:>11.1f}%")
        if best is None or r["avg_cost"] < best[1]:
            best = (f"α={alpha} β={beta}", r["avg_cost"], r["hit_first_rate"]*100, save*100)
    print(f"  → 最低成本组合: {best[0]}  成本¥{best[1]:.4f}  首选命中{best[2]:.1f}%  节约{best[3]:.1f}%")

    # E3 补充：L4 是否强制旗舰的对比（验证「L4 需旗舰」）
    print(f"\n【E3 补充 · L4 套公式 vs 强制旗舰（α=0.65 β=0.25）】")
    r_pure = replay(agg, formula_rank(0.65, 0.25, force_flagship_l4=False))
    r_flag = replay(agg, formula_rank(0.65, 0.25, force_flagship_l4=True))
    q_pure = quality_of_route(agg, formula_rank(0.65, 0.25, force_flagship_l4=False))
    q_flag = quality_of_route(agg, formula_rank(0.65, 0.25, force_flagship_l4=True))
    print(f"{'L4 策略':<20}{'首选命中率':>12}{'平均成本':>12}{'质量分':>10}")
    print(f"{'套公式(选轻量)':<20}{r_pure['hit_first_rate']*100:>11.1f}%{r_pure['avg_cost']:>12.4f}{q_pure:>10.1f}")
    print(f"{'强制旗舰':<20}{r_flag['hit_first_rate']*100:>11.1f}%{r_flag['avg_cost']:>12.4f}{q_flag:>10.1f}")

    # 敏感性分析：及格线 ±5
    print(f"\n【敏感性分析 · 及格线波动（E2 实测规则）】")
    print(f"{'及格线':>6}{'分派准确率':>12}{'首选命中率':>12}{'平均成本':>12}")
    for pl in [80, 85, 90]:
        r = replay(agg, MEASURED_RULES, pass_line=pl)
        print(f"{pl:>6}{r['pass_rate']*100:>11.1f}%{r['hit_first_rate']*100:>11.1f}%{r['avg_cost']:>12.4f}")

    # 首选未命中诊断
    print(f"\n【首选未命中诊断（E2 实测规则，及格线85）】")
    missed = missed_tasks(agg, MEASURED_RULES)
    if missed:
        for tid, d, primary, q, alt in missed:
            print(f"  {tid} ({d}): 首选 {primary} 质量 {q} < 85 → 回退 {alt}")
    else:
        print("  （无首选未命中）")

    # 输出 JSON 结果供后续引用
    out = {
        "baseline": {"pro": base_pro, "max": base_max},
        "E1_prior": r1,
        "E2_measured": r2,
        "E3_best": {"label": best[0], "avg_cost": best[1]},
        "L4_comparison": {
            "pure_formula": {"hit_first": r_pure["hit_first_rate"], "avg_cost": r_pure["avg_cost"], "quality": round(q_pure, 1)},
            "force_flagship": {"hit_first": r_flag["hit_first_rate"], "avg_cost": r_flag["avg_cost"], "quality": round(q_flag, 1)},
        },
        "M6": {"prior_delta": round(dq1, 2), "measured_delta": round(dq2, 2)},
    }
    with open("data/results/replay_summary.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n✅ 结果已写入 data/results/replay_summary.json")


if __name__ == "__main__":
    main()

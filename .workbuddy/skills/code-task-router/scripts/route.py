#!/usr/bin/env python3
"""code-task-router 确定性路由脚本 v1.0（实测数据版，2026-10-17）

用法:
    python route.py --task task.json [--formula]

task.json 字段:
    difficulty     难度等级 L1/L2/L3/L4（可由分类器或人工提供）
    confidence     分类置信度 0~1（可选，默认1.0；<0.7 时自动升档）
    latency        时效要求 realtime/interactive/offline（可选，默认interactive）
    privacy        public_cloud_ok/local_only（可选，默认public_cloud_ok）
    quality        pass/premium（可选，默认pass；premium=高价值质量优先）
    budget         单任务成本上限，元（可选）
    input_tokens  预计输入Token数（可选，用于阶梯价判断）

输出: JSON 分派决策（首选 + 备选链 + 决策依据）

v1.0（实测数据版）: 基于 2026-10-17 全量评测 1152 次生成，分难度质量分/成本/时延均为实测值。
评测口径 v1.3（权重 0.10/0.45/0.20/0.25，及格线 85，裁判官方 Pro）。
核心结论: L1~L3 首选 qwen3.7-flash（性价比碾压）；L4 指定旗舰（质量敏感）。
调用方舟必须用精确版本 ID；所有调用须关闭思考链。

说明:
    - 默认按 references/dispatch-rules.md 实测规则表分派
    - --formula 切换到 S_value = S_quality / (Cost^α × Time^β) 公式排序（基于实测质量分；L4 除外）
    - 本脚本与 SKILL.md 逻辑层分离：规则与模型数据更新时只需改本文件顶部的数据区
"""

import argparse
import json
import sys

# ============ 数据区（与 references/ 同步，v1.0 实测数据版 2026-10-17） ============

PLATFORM = {
    "doubao-seed-2-1-pro-260915": "volcengine",
    "doubao-seed-2-0-code-preview-260215": "volcengine",
    "doubao-seed-2-1-lite-260915": "volcengine",
    "doubao-seed-2-0-mini-260428": "volcengine",
    "qwen3.8-max": "aliyun",
    "qwen3-coder-flash": "aliyun",
    "qwen3.7-plus": "aliyun",
    "qwen3.7-flash": "aliyun",
}

TIER = {  # 档位，用于备选链构造
    "doubao-seed-2-1-pro-260915": "T0", "qwen3.8-max": "T0",
    "doubao-seed-2-0-code-preview-260215": "T1", "qwen3-coder-flash": "T1",
    "doubao-seed-2-1-lite-260915": "T2", "qwen3.7-plus": "T2",
    "doubao-seed-2-0-mini-260428": "T3", "qwen3.7-flash": "T3",
}

QUALITY = {  # 分难度实测质量分（2026-10-17 全量评测，口径 v1.3）
    "doubao-seed-2-1-pro-260915": {"L1": 94.1, "L2": 93.4, "L3": 93.9, "L4": 91.3},
    "qwen3.8-max": {"L1": 93.3, "L2": 94.3, "L3": 93.7, "L4": 92.3},
    "doubao-seed-2-0-code-preview-260215": {"L1": 93.4, "L2": 92.9, "L3": 87.8, "L4": 87.1},
    "qwen3-coder-flash": {"L1": 92.2, "L2": 92.2, "L3": 91.4, "L4": 78.0},
    "doubao-seed-2-1-lite-260915": {"L1": 93.4, "L2": 89.0, "L3": 91.3, "L4": 91.5},
    "qwen3.7-plus": {"L1": 92.7, "L2": 93.4, "L3": 92.7, "L4": 89.7},
    "doubao-seed-2-0-mini-260428": {"L1": 91.4, "L2": 91.9, "L3": 87.9, "L4": 88.0},
    "qwen3.7-flash": {"L1": 93.2, "L2": 93.3, "L3": 92.2, "L4": 87.2},
}

UNIT_COST = {  # 实测单次成本（元，关思考后全量均值）
    "doubao-seed-2-1-pro-260915": 0.0167, "qwen3.8-max": 0.0209,
    "doubao-seed-2-0-code-preview-260215": 0.0086, "qwen3-coder-flash": 0.0025,
    "doubao-seed-2-1-lite-260915": 0.0015, "qwen3.7-plus": 0.0049,
    "doubao-seed-2-0-mini-260428": 0.0008, "qwen3.7-flash": 0.0005,
}

LATENCY = {  # 实测平均耗时（秒，关思考后全量均值）
    "doubao-seed-2-1-pro-260915": 12.4, "qwen3.8-max": 8.8,
    "doubao-seed-2-0-code-preview-260215": 8.5, "qwen3-coder-flash": 5.6,
    "doubao-seed-2-1-lite-260915": 7.4, "qwen3.7-plus": 10.6,
    "doubao-seed-2-0-mini-260428": 3.1, "qwen3.7-flash": 7.0,
}

PASS_LINE = {"L1": 85, "L2": 85, "L3": 85, "L4": 85}
TIER_ORDER = ["T3", "T2", "T1", "T0"]
ALPHA, BETA = 0.65, 0.25

FLAGSHIP = "qwen3.8-max"                      # L4 首选旗舰（功能分99.5最高）
FLAGSHIP_FALLBACK = "doubao-seed-2-1-pro-260915"  # 备选旗舰

# ============ 逻辑区 ============


def upgrade(d):
    return {"L1": "L2", "L2": "L3", "L3": "L4", "L4": "L4"}[d]


def entry(model):
    return {"platform": PLATFORM[model], "model": model}


def route_by_rule(task, d):
    """实测规则表分派"""
    quality = task.get("quality", "pass")
    latency = task.get("latency", "interactive")
    if quality == "premium" or d == "L4":
        primary = FLAGSHIP
        chain = [FLAGSHIP_FALLBACK, "doubao-seed-2-1-lite-260915"]
        reason = "L4专家级/高价值任务，旗舰兜底（实测 coder-flash L4 仅78分，轻量模型功能分不足）"
    elif d == "L3":
        primary = "qwen3.7-flash"
        chain = ["doubao-seed-2-1-lite-260915", "qwen3-coder-flash"]
        reason = "L3高级，flash 实测质量92.2/成本0.0005，S_value第一"
    elif d == "L2":
        primary = "qwen3.7-flash"
        chain = ["doubao-seed-2-0-mini-260428", "doubao-seed-2-1-lite-260915"]
        reason = "L2进阶，flash 实测质量93.3/成本0.0004，S_value第一"
    else:
        primary = "qwen3.7-flash"
        chain = ["doubao-seed-2-0-mini-260428", "doubao-seed-2-1-lite-260915"]
        reason = "L1入门，flash 实测质量93.2/成本0.0003，S_value第一"
    if latency == "realtime":
        primary = "doubao-seed-2-0-mini-260428"  # 实测延迟最低 3.1s
        chain = ["qwen3-coder-flash", "qwen3.7-flash"]
        reason += "；实时场景切换最低延迟 mini(3.1s)"
    return primary, chain, reason


def route_by_formula(task, d):
    """S_value 公式排序（实测质量分）；L4 强制旗舰，不套公式"""
    if d == "L4":
        return route_by_rule(task, d)
    budget = task.get("budget")
    scored = []
    for m, q in QUALITY.items():
        if q[d] < PASS_LINE[d]:
            continue
        if budget and UNIT_COST[m] > budget:
            continue
        s = q[d] / (UNIT_COST[m] ** ALPHA * LATENCY[m] ** BETA)
        scored.append((s, m))
    if not scored:
        return None, [], "无候选模型通过质量门槛"
    scored.sort(key=lambda x: -x[0])
    primary = scored[0][1]
    chain = [m for _, m in scored[1:3]]
    return primary, chain, "S_value公式排序Top1（实测数据）"


def route(task):
    d = task.get("difficulty", "L2")
    conf = float(task.get("confidence", 1.0))
    upgraded = False
    if conf < 0.7 and d != "L4":
        d = upgrade(d)
        upgraded = True

    if task.get("privacy") == "local_only":
        return {"error": "无本地部署模型，无法满足隐私约束，已拒绝分派"}

    use_formula = task.pop("_formula", False)
    if use_formula:
        primary, chain, reason = route_by_formula(task, d)
        if primary is None:
            return {"error": reason}
    else:
        primary, chain, reason = route_by_rule(task, d)

    decision = {
        "primary": entry(primary),
        "fallback_chain": [entry(m) for m in chain],
        "decision": {
            "difficulty": d,
            "confidence": conf,
            "upgraded": upgraded,
            "estimated_cost": UNIT_COST[primary],
            "reason": reason,
        },
    }
    return decision


def main():
    ap = argparse.ArgumentParser(description="code-task-router 确定性路由")
    ap.add_argument("--task", required=True, help="任务JSON文件路径")
    ap.add_argument("--formula", action="store_true", help="使用S_value公式排序替代实测规则表")
    args = ap.parse_args()

    with open(args.task, "r", encoding="utf-8") as f:
        task = json.load(f)
    if args.formula:
        task["_formula"] = True

    result = route(task)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(1 if "error" in result else 0)


if __name__ == "__main__":
    main()

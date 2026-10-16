#!/usr/bin/env python3
"""code-task-router 确定性路由脚本 v0.3（先验规则版，2026-10-17 修订）

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

v0.3 修订（双平台 Key 实测）: 方舟侧切换为账号可调用的精确版本 ID
（doubao-seed-2-1-lite-260915 / doubao-seed-2-0-mini-260428 /
doubao-seed-2-0-code-preview-260215）；doubao-seed-2-1-pro-260915 已核实价格
但账号未开通（控制台激活后参与路由）；evolving/turbo/seed-code 均已退出。
所有价格经官方定价页核实；调用方舟必须用精确版本 ID。

说明:
    - 默认按 references/dispatch-rules.md 先验规则表分派
    - --formula 切换到 S_value = S_quality / (Cost^α × Time^β) 公式排序（基于先验质量分）
    - 本脚本与 SKILL.md 逻辑层分离：规则与模型数据更新时只需改本文件顶部的数据区
"""

import argparse
import json
import sys

# ============ 数据区（与 references/ 同步，v0.2 先验版，待控制台核实） ============

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

PRIOR_QUALITY = {  # 分难度先验质量分
    "doubao-seed-2-1-pro-260915": {"L1": 95, "L2": 90, "L3": 85, "L4": 80},
    "qwen3.8-max": {"L1": 95, "L2": 90, "L3": 85, "L4": 80},
    "doubao-seed-2-0-code-preview-260215": {"L1": 92, "L2": 88, "L3": 84, "L4": 76},
    "qwen3-coder-flash": {"L1": 91, "L2": 86, "L3": 82, "L4": 72},
    "doubao-seed-2-1-lite-260915": {"L1": 90, "L2": 84, "L3": 76, "L4": 65},
    "qwen3.7-plus": {"L1": 93, "L2": 86, "L3": 80, "L4": 70},
    "doubao-seed-2-0-mini-260428": {"L1": 80, "L2": 70, "L3": 55, "L4": 40},
    "qwen3.7-flash": {"L1": 80, "L2": 70, "L3": 55, "L4": 40},
}

UNIT_COST = {  # 单次成本（元，0-32K档，输入1500/输出800假设；2026-10-17 官方定价核实）
    "doubao-seed-2-1-pro-260915": 0.033, "qwen3.8-max": 0.047,
    "doubao-seed-2-0-code-preview-260215": 0.014, "qwen3-coder-flash": 0.005,
    "doubao-seed-2-1-lite-260915": 0.003, "qwen3.7-plus": 0.009,
    "doubao-seed-2-0-mini-260428": 0.002, "qwen3.7-flash": 0.001,
}

LATENCY = {  # 先验平均耗时（秒）
    "doubao-seed-2-1-pro-260915": 12, "qwen3.8-max": 12,
    "doubao-seed-2-0-code-preview-260215": 8, "qwen3-coder-flash": 6,
    "doubao-seed-2-1-lite-260915": 4, "qwen3.7-plus": 7,
    "doubao-seed-2-0-mini-260428": 3, "qwen3.7-flash": 3,
}

PASS_LINE = {"L1": 60, "L2": 60, "L3": 65, "L4": 70}
TIER_ORDER = ["T3", "T2", "T1", "T0"]
ALPHA, BETA = 0.65, 0.25

# ============ 逻辑区 ============


def upgrade(d):
    return {"L1": "L2", "L2": "L3", "L3": "L4", "L4": "L4"}[d]


def entry(model):
    return {"platform": PLATFORM[model], "model": model}


def route_by_rule(task, d):
    """先验规则表分派"""
    quality = task.get("quality", "pass")
    latency = task.get("latency", "interactive")
    if quality == "premium" or d == "L4":
        primary = "doubao-seed-2-1-pro-260915"
        chain = ["qwen3.8-max", "doubao-seed-2-0-code-preview-260215"]
        reason = "L4专家级/高价值任务，旗舰兜底"
    elif d == "L3":
        primary = "doubao-seed-2-0-code-preview-260215"
        chain = ["qwen3-coder-flash", "doubao-seed-2-1-pro-260915"]
        reason = "L3高级，代码专项模型性价比最优"
    elif d == "L2":
        primary = "doubao-seed-2-1-lite-260915"
        chain = ["qwen3.7-plus", "doubao-seed-2-0-code-preview-260215"]
        reason = "L2进阶，T2均衡档能力-成本平衡点"
    else:
        primary = "qwen3.7-flash"
        chain = ["doubao-seed-2-0-mini-260428", "doubao-seed-2-1-lite-260915"]
        reason = "L1入门，T3轻量档成本最低"
    if latency == "realtime" and d in ("L1", "L2"):
        primary = "qwen3.7-flash"
        reason += "；实时场景切换轻量侧"
    return primary, chain, reason


def route_by_formula(task, d):
    """S_value 公式排序（先验质量分）"""
    budget = task.get("budget")
    scored = []
    for m, q in PRIOR_QUALITY.items():
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
    return primary, chain, "S_value公式排序Top1（先验数据）"


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
    ap.add_argument("--formula", action="store_true", help="使用S_value公式排序替代先验规则表")
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

#!/usr/bin/env python3
"""评测仪表盘 CLI：从 JSONL 结果生成自包含可视化 HTML 窗口。

示例：
    python make_dashboard.py                          # 汇总全部试跑/评测结果
    python make_dashboard.py --tag v3                 # 只汇总指定 tag（如 v3full）
    python make_dashboard.py --out dashboard.html     # 指定输出（默认 report/dashboard.html）

产物为单文件 HTML（数据与图表库全部内联），双击即可在浏览器打开，无需服务器、无需联网。
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from eval_kit.dashboard import (default_source_files, generate_dashboard,
                                load_eval_config, load_result_rows)

ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser(description="生成评测结果可视化仪表盘")
    ap.add_argument("--results-dir", default=os.path.join(ROOT, "data", "results"))
    ap.add_argument("--eval-config", default=os.path.join(ROOT, "config", "eval.yaml"))
    ap.add_argument("--chartjs", default=os.path.join(ROOT, "assets", "chart.umd.min.js"))
    ap.add_argument("--out", default=os.path.join(ROOT, "report", "dashboard.html"))
    ap.add_argument("--tag", default=None, help="只汇总指定 tag 的结果文件")
    args = ap.parse_args()

    sources = default_source_files(args.results_dir, args.tag)
    if not sources:
        print("未找到结果文件（data/results/results_*.jsonl）")
        sys.exit(1)

    rows = load_result_rows(sources)
    if not rows:
        print("结果文件为空")
        sys.exit(1)

    eval_cfg = load_eval_config(args.eval_config)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    payload, path = generate_dashboard(rows, eval_cfg, sources, args.chartjs, args.out)
    print(f"仪表盘已生成: {path}")
    print(f"  记录 {payload['totals']['records']} 条 | 模型 {payload['totals']['models']} 款 | "
          f"题目 {payload['totals']['tasks']} 道 | 总名义成本 ¥{payload['totals']['total_cost']}")
    for m in payload["models"]:
        judged = "未评分" if m["avg_quality"] is None else f"综合 {m['avg_quality']}"
        pr = "未评分" if m["pass_rate"] is None else f"达标 {m['pass_rate']}%"
        print(f"  - {m['display']}: {judged} | {pr} | 单次 ¥{m['avg_cost']} | {m['avg_latency']}s")


if __name__ == "__main__":
    main()

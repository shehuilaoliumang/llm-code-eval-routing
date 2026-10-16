#!/usr/bin/env python3
"""评测套件 CLI 入口。

示例：
    # 干跑自检（无 key）
    python run_eval.py --dry-run --limit 2

    # 试跑：每模型5题×1次（第1笔预算 ~2元）
    python run_eval.py --limit 5 --runs 1

    # 全量评测
    python run_eval.py

    # 生成评测 manifest
    python run_eval.py --manifest-only

API Key 通过环境变量提供：
    火山方舟  VOLCENGINE_API_KEY
    阿里百炼  DASHSCOPE_API_KEY
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from eval_kit.clients import DualPlatformClient, MockClient
from eval_kit.config import EvalConfig, ModelRegistry, load_dotenv, load_yaml
from eval_kit.manifest import build_manifest, save_manifest
from eval_kit.recorder import JSONLRecorder
from eval_kit.runner import load_tasks, make_runner

ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser(description="LLM代码生成能力评测套件")
    ap.add_argument("--tasks", default=os.path.join(ROOT, "data", "tasks", "tasks_v2.json"))
    ap.add_argument("--models", default=os.path.join(ROOT, "config", "models.yaml"))
    ap.add_argument("--eval-config", default=os.path.join(ROOT, "config", "eval.yaml"))
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "results"))
    ap.add_argument("--tag", default="v1")
    ap.add_argument("--limit", type=int, default=None, help="只跑前 N 题（试跑用）")
    ap.add_argument("--runs", type=int, default=None, help="每题每模型运行次数")
    ap.add_argument("--models-filter", nargs="*", default=None, help="只跑指定模型")
    ap.add_argument("--no-judge", action="store_true", help="跳过LLM裁判（只跑自动判分）")
    ap.add_argument("--dry-run", action="store_true", help="MockClient 干跑，不调真实API")
    ap.add_argument("--manifest-only", action="store_true", help="只生成 manifest")
    args = ap.parse_args()

    load_dotenv(os.path.join(ROOT, ".env.local"))
    models_cfg = load_yaml(args.models)
    eval_cfg_raw = load_yaml(args.eval_config)
    registry = ModelRegistry(models_cfg)
    eval_cfg = EvalConfig(eval_cfg_raw)

    if args.manifest_only:
        manifest = build_manifest(eval_cfg_raw, registry, args.tasks,
                                  args.eval_config, args.models)
        path = os.path.join(ROOT, "manifests", f"manifest_{args.tag}.json")
        save_manifest(manifest, path)
        print(f"manifest 已生成: {path}")
        return

    tasks = load_tasks(args.tasks)
    model_ids = args.models_filter or registry.candidates()
    for m in model_ids:
        registry.get(m)

    os.makedirs(args.out, exist_ok=True)
    call_recorder = JSONLRecorder(os.path.join(args.out, f"api_calls_{args.tag}.jsonl"))
    result_recorder = JSONLRecorder(os.path.join(args.out, f"results_{args.tag}.jsonl"))

    if args.dry_run:
        client = MockClient()
        print("[dry-run] 使用 MockClient，不调用真实 API")
    else:
        client = DualPlatformClient(registry, retry_cfg=eval_cfg.retry,
                                    recorder=call_recorder)

    runner = make_runner(registry, eval_cfg, client, result_recorder,
                         cross_check_ratio=eval_cfg.judge.get("cross_check_ratio", 0.0))
    if args.no_judge:
        runner._maybe_judge = lambda *a, **k: None

    print(f"任务数: {len(tasks)} | 模型数: {len(model_ids)} | "
          f"运行次数: {args.runs or eval_cfg.generation['runs_per_task']}")
    rows = runner.run(tasks, model_ids, runs=args.runs, limit=args.limit)
    ok = sum(1 for r in rows if not r.get("api_error"))
    print(f"\n完成: {len(rows)} 次生成（成功 {ok}），结果写入 {args.out}")


if __name__ == "__main__":
    main()

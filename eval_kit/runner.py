"""评测执行器：加载任务 → 双平台调用 → 代码提取 → 自动判分 → 裁判 → 全量记录。

用法见 run_eval.py；干跑（无 key）用 MockClient 自检管线。
"""

import json
import os
from typing import Dict, List, Optional

from .clients import DualPlatformClient, MockClient
from .code_extract import extract_code
from .judge import build_judge_messages, parse_judge_response
from .pricing import cost_yuan, tier_name
from .recorder import JSONLRecorder
from .scoring import quality_total, run_unit_tests, syntax_check


def load_tasks(path: str) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["tasks"] if isinstance(data, dict) else data


class EvaluationRunner:
    def __init__(self, registry, eval_cfg, client, recorder: JSONLRecorder,
                 cross_check_ratio: float = 0.0):
        self.registry = registry
        self.cfg = eval_cfg
        self.client = client
        self.recorder = recorder
        self.weights = eval_cfg.scoring["weights"]
        self.gen = eval_cfg.generation
        self.judge_cfg = eval_cfg.judge
        self.cross_check_ratio = cross_check_ratio
        self.disable_thinking = eval_cfg.cfg.get("disable_thinking", True)

    def _extra_body(self, model_cfg):
        """按口径关闭思考链（默认关闭）。各平台机制不同，配置在 models.yaml
        的 disable_thinking_body 字段。实测：Qwen 系不关时 max_tokens 被无视，
        输出可达 10 倍（思考链计入输出），必须显式关闭。"""
        if not self.disable_thinking:
            return None
        return model_cfg.get("disable_thinking_body")

    # ---------- 单次生成 + 判分 ----------
    def run_one(self, task: Dict, model_id: str, run_idx: int) -> Dict:
        model_cfg = self.registry.get(model_id)
        platform = model_cfg["platform"]
        messages = [
            {"role": "system", "content": self.cfg.system_prompt},
            {"role": "user", "content": task["description"]},
        ]
        result = self.client.chat(
            platform=platform,
            model=model_cfg.get("snapshot", model_id)
            if platform == "volcengine" else model_id,
            messages=messages,
            temperature=self.gen["temperature"],
            top_p=self.gen["top_p"],
            max_tokens=self.gen["max_tokens"],
            timeout=self.gen["timeout_seconds"],
            extra_body=self._extra_body(model_cfg),
        )
        row = {
            "type": "generation",
            "task_id": task["task_id"],
            "difficulty": task["difficulty"],
            "task_type": task.get("task_type", ""),
            "platform": platform,
            "model": model_id,
            "model_version": model_cfg.get("snapshot", "latest"),
            "run": run_idx,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "latency_seconds": round(result.latency, 3),
            "api_error": result.error,
        }
        if result.error:
            row.update({"passed": False, "syntax_score": 0, "functional_score": 0,
                        "quality_total": 0, "code": "", "cost_yuan": 0.0})
            self.recorder.write(row)
            return row

        code = extract_code(result.content)
        syn_score, syn_errors = syntax_check(code)
        passed, total, details = run_unit_tests(
            code, task["entry_point"], task["test_cases"],
            timeout=self.gen["timeout_seconds"],
        )
        func_score = 100.0 * passed / total if total else 0.0
        cost = cost_yuan(model_cfg, result.input_tokens, result.output_tokens)

        row.update({
            "code": code,
            "syntax_score": syn_score,
            "syntax_errors": syn_errors,
            "tests_passed": passed,
            "tests_total": total,
            "test_details": details,
            "functional_score": round(func_score, 2),
            "cost_yuan": round(cost, 6),
            "input_tier": tier_name(model_cfg, result.input_tokens),
            "raw_output": result.content,
        })
        self.recorder.write(row)
        self._maybe_judge(task, model_id, code, row)
        return row

    def _maybe_judge(self, task: Dict, model_id: str, code: str, row: Dict) -> None:
        """规范/健壮性评分：默认裁判全量 + 主力裁判按比例交叉验证。"""
        judge_model = self.judge_cfg["model"]
        cross_model = self.judge_cfg.get("cross_check_model")
        style, robust, judge_err = self._judge_once(judge_model, task, code)
        row.update({"style_score": style, "robustness_score": robust,
                    "judge_model": judge_model, "judge_error": judge_err})
        if cross_model and self.cross_check_ratio > 0 and _in_cross_check(task, model_id, row["run"]):
            c_style, c_robust, c_err = self._judge_once(cross_model, task, code)
            row.update({"cross_check_model": cross_model,
                        "cross_style_score": c_style, "cross_robustness_score": c_robust,
                        "cross_judge_error": c_err})
        row["quality_total"] = round(quality_total(
            row.get("syntax_score", 0), row.get("functional_score", 0),
            style, robust, self.weights), 2)
        row["passed"] = row["quality_total"] >= self.cfg.pass_line(task["difficulty"])
        # 注意：type 必须放在 ** 解包之后（或从解包中排除），否则被 row 的 generation 覆盖
        scored = {k: v for k, v in row.items() if k not in ("raw_output", "type")}
        scored["type"] = "scored"
        self.recorder.write(scored)

    def _judge_once(self, judge_model: str, task: Dict, code: str):
        judge_cfg = self.registry.get(judge_model)
        messages = build_judge_messages(task["description"], code)
        result = self.client.chat(
            platform=judge_cfg["platform"],
            model=judge_cfg.get("snapshot", judge_model)
            if judge_cfg["platform"] == "volcengine" else judge_model,
            messages=messages,
            temperature=self.judge_cfg["temperature"],
            max_tokens=self.judge_cfg["max_tokens"],
            timeout=self.judge_cfg["timeout_seconds"],
            extra_body=self._extra_body(judge_cfg),
        )
        if result.error:
            return 0, 0, result.error
        scores = parse_judge_response(result.content)
        if scores is None:
            return 0, 0, "judge_response_unparseable"
        return scores["style_score"], scores["robustness_score"], None

    # ---------- 批量 ----------
    def run(self, tasks: List[Dict], model_ids: List[str],
            runs: Optional[int] = None, limit: Optional[int] = None) -> List[Dict]:
        runs = runs or self.gen["runs_per_task"]
        rows: List[Dict] = []
        selected = tasks[:limit] if limit else tasks
        for task in selected:
            for model_id in model_ids:
                for run_idx in range(1, runs + 1):
                    row = self.run_one(task, model_id, run_idx)
                    rows.append(row)
                    status = "OK" if not row.get("api_error") else "API_ERR"
                    print(f"[{status}] {task['task_id']} {model_id} run{run_idx} "
                          f"质量={row.get('quality_total')} 成本={row.get('cost_yuan')}元")
        return rows


def _in_cross_check(task: Dict, model_id: str, run_idx: int) -> bool:
    """确定性抽样：同一 (task, model, run) 哈希 < ratio 时进入交叉验证。"""
    import hashlib

    key = f"{task['task_id']}|{model_id}|{run_idx}"
    h = int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)
    return (h % 1000) / 1000.0 < _RATIO_HOLDER["ratio"]


_RATIO_HOLDER = {"ratio": 0.0}


def make_runner(registry, eval_cfg, client, recorder, cross_check_ratio):
    _RATIO_HOLDER["ratio"] = cross_check_ratio
    return EvaluationRunner(registry, eval_cfg, client, recorder, cross_check_ratio)


def default_recorder(out_dir: str, tag: str) -> JSONLRecorder:
    os.makedirs(out_dir, exist_ok=True)
    return JSONLRecorder(os.path.join(out_dir, f"results_{tag}.jsonl"))

"""eval_kit 本地单元测试（无需 API key）。

运行: python -m unittest discover -s tests -v
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval_kit.code_extract import extract_code
from eval_kit.config import EvalConfig, ModelRegistry, load_yaml
from eval_kit.pricing import cost_yuan, select_tier, tier_name
from eval_kit.sandbox import run_python
from eval_kit.scoring import quality_total, run_unit_tests, syntax_check

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestPricing(unittest.TestCase):
    def setUp(self):
        self.registry = ModelRegistry(load_yaml(os.path.join(ROOT, "config", "models.yaml")))

    def test_tier_selection(self):
        cfg = self.registry.get("qwen3-coder-flash")
        self.assertEqual(select_tier(cfg["pricing"], 1000), (1.0, 4.0))
        self.assertEqual(select_tier(cfg["pricing"], 50000), (1.5, 6.0))
        self.assertEqual(select_tier(cfg["pricing"], 500000), (5.0, 25.0))

    def test_cost_calculation(self):
        cfg = self.registry.get("doubao-seed-2.0-mini")
        # 输入1500/输出800, 0-32K档 0.2/2 元每百万
        cost = cost_yuan(cfg, 1500, 800)
        self.assertAlmostEqual(cost, 1500 / 1e6 * 0.2 + 800 / 1e6 * 2.0, places=8)

    def test_tier_name(self):
        cfg = self.registry.get("qwen3-coder-flash")
        self.assertEqual(tier_name(cfg, 1000), "0-32K")
        self.assertEqual(tier_name(cfg, 50000), "32-128K")
        self.assertEqual(tier_name(cfg, 500000), "256K-1M")


class TestSandbox(unittest.TestCase):
    def test_hello(self):
        r = run_python("print('hello')", timeout=10)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), "hello")

    def test_timeout(self):
        r = run_python("import time\nwhile True:\n    time.sleep(0.1)", timeout=2)
        self.assertTrue(r.timed_out)
        self.assertEqual(r.returncode, -1)

    def test_syntax_error_runs(self):
        r = run_python("def broken(:\n    pass", timeout=10)
        self.assertNotEqual(r.returncode, 0)


class TestScoring(unittest.TestCase):
    def test_syntax_check_pass(self):
        score, errors = syntax_check("def f(x):\n    return x + 1\n")
        self.assertEqual(score, 100.0)
        self.assertEqual(errors, [])

    def test_syntax_check_fail(self):
        score, errors = syntax_check("def f(:\n    pass")
        self.assertEqual(score, 0.0)
        self.assertTrue(any("SyntaxError" in e for e in errors))

    def test_unit_tests_pass(self):
        code = "def add(a, b):\n    return a + b\n"
        cases = [{"args": [1, 2], "expected": 3}, {"args": [-1, 1], "expected": 0}]
        passed, total, details = run_unit_tests(code, "add", cases, timeout=15)
        self.assertEqual((passed, total), (2, 2))
        self.assertEqual(details, [])

    def test_unit_tests_partial(self):
        code = "def add(a, b):\n    return a - b\n"
        cases = [{"args": [1, 2], "expected": 3}, {"args": [5, 3], "expected": 2}]
        passed, total, details = run_unit_tests(code, "add", cases, timeout=15)
        self.assertEqual(passed, 1)
        self.assertEqual(total, 2)
        self.assertTrue(any("CASE_0_FAIL" in d for d in details))

    def test_class_steps(self):
        code = (
            "class Counter:\n"
            "    def __init__(self):\n"
            "        self.n = 0\n"
            "    def inc(self, k=1):\n"
            "        self.n += k\n"
            "        return self.n\n"
        )
        cases = [{"class": "Counter", "steps": [["inc"], ["inc", 5]], "expected": 6}]
        passed, total, _ = run_unit_tests(code, "Counter", cases, timeout=15)
        self.assertEqual((passed, total), (1, 1))

    def test_quality_total(self):
        weights = {"syntax": 0.3, "functional": 0.4, "style": 0.2, "robustness": 0.1}
        self.assertEqual(quality_total(100, 100, 100, 100, weights), 100.0)
        self.assertEqual(quality_total(0, 100, 100, 100, weights), 70.0)


class TestCodeExtract(unittest.TestCase):
    def test_fence(self):
        text = "说明文字\n```python\ndef f():\n    return 1\n```\n结尾"
        self.assertIn("def f():", extract_code(text))

    def test_bare_code(self):
        self.assertIn("def f():", extract_code("def f():\n    return 1"))

    def test_empty(self):
        self.assertEqual(extract_code(""), "")


class TestConfigAndTasks(unittest.TestCase):
    def test_eval_config_loads(self):
        cfg = EvalConfig(load_yaml(os.path.join(ROOT, "config", "eval.yaml")))
        self.assertEqual(cfg.pass_line("L1"), 60)
        self.assertEqual(cfg.pass_line("L4"), 70)
        self.assertEqual(cfg.generation["temperature"], 0.2)

    def test_seed_tasks_reference_solutions_pass(self):
        """所有任务集文件的参考实现必须全部通过各自测试（回归保护）。

        覆盖 tasks_v1.json（种子集）与 tasks_v2.json（48题完整集，若已构建）。
        这是「LLM 出题质量门」的自动化落地：抓错误的期望值与不可运行代码。
        """
        import glob
        task_files = sorted(glob.glob(os.path.join(ROOT, "data", "tasks", "tasks_*.json")))
        self.assertTrue(task_files, "未找到任何任务集文件")
        for tf in task_files:
            with open(tf, encoding="utf-8") as f:
                payload = json.load(f)
            tasks = payload["tasks"] if isinstance(payload, dict) else payload
            for task in tasks:
                passed, total, details = run_unit_tests(
                    task["reference_solution"], task["entry_point"],
                    task["test_cases"], timeout=30,
                )
                self.assertEqual(passed, total,
                                 f"{os.path.basename(tf)}:{task['task_id']} 参考实现未全过: {details}")

    def test_tasks_v2_schema(self):
        """tasks_v2.json（若存在）须满足结构约束：ID唯一、4~6用例、stdlib-only。"""
        import glob
        v2 = os.path.join(ROOT, "data", "tasks", "tasks_v2.json")
        if not os.path.exists(v2):
            self.skipTest("tasks_v2.json 尚未构建")
        with open(v2, encoding="utf-8") as f:
            payload = json.load(f)
        tasks = payload["tasks"]
        ids = [t["task_id"] for t in tasks]
        self.assertEqual(len(ids), len(set(ids)), "task_id 有重复")
        for t in tasks:
            self.assertIn(t["difficulty"], ("L1", "L2", "L3", "L4"))
            self.assertTrue(4 <= len(t["test_cases"]) <= 6, f"{t['task_id']} 用例数越界")
            self.assertIn(t.get("split"), ("rule_dev", "holdout"), f"{t['task_id']} 缺少划分")
        # 元数据溯源（可复现性）
        meta = payload.get("metadata", {})
        self.assertIn("editor", meta)
        self.assertIn("prompt_hash", meta)
        dev = sum(1 for t in tasks if t.get("split") == "rule_dev")
        hold = sum(1 for t in tasks if t.get("split") == "holdout")
        self.assertEqual(dev, hold, "dev/holdout 应各24题")


class TestScoredRecordType(unittest.TestCase):
    """回归：scored 记录的 type 不得被 generation 行覆盖（dict 解包顺序 bug）。"""

    def setUp(self):
        from eval_kit.recorder import JSONLRecorder
        self.JSONLRecorder = JSONLRecorder

    def test_scored_type_not_overridden(self):
        row = {"type": "generation", "task_id": "T1", "raw_output": "x",
               "syntax_score": 100.0}
        # 与 runner._maybe_judge 相同的构造方式
        scored = {k: v for k, v in row.items() if k not in ("raw_output", "type")}
        scored["type"] = "scored"
        self.assertEqual(scored["type"], "scored")
        self.assertNotIn("raw_output", scored)

    def test_dict_literal_merge_order(self):
        """文档化陷阱：{'type':'scored', **row} 会被 row 的 type 覆盖。"""
        row = {"type": "generation"}
        merged = {"type": "scored", **row}
        self.assertEqual(merged["type"], "generation")  # 证明旧写法确有 bug


class TestDashboardRender(unittest.TestCase):
    """回归：仪表盘渲染 JS 必须无语法/运行时错误。

    历史 bug：__ROWS__ 以裸 HTML 注入 JS 表达式（`表头</tr>` + <tr>...），
    造成 SyntaxError，整个渲染脚本失效、图表全空。
    """

    def test_dashboard_render_js(self):
        import shutil
        import subprocess
        node = shutil.which("node")
        if not node:
            self.skipTest("node 不可用")
        script = os.path.join(ROOT, "tools", "verify_dashboard.js")
        if not os.path.exists(script):
            self.skipTest("tools/verify_dashboard.js 不存在")
        html = os.path.join(ROOT, "report", "dashboard.html")
        if not os.path.exists(html):
            self.skipTest("dashboard.html 尚未生成")
        r = subprocess.run([node, script, html], capture_output=True,
                           text=True, timeout=30, cwd=ROOT)
        self.assertIn("错误: 无", r.stdout,
                      f"仪表盘渲染 JS 有错误:\n{r.stdout}\n{r.stderr}")


if __name__ == "__main__":
    unittest.main()

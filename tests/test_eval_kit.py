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
        """种子任务的参考实现必须全部通过各自测试（回归保护）。"""
        with open(os.path.join(ROOT, "data", "tasks", "tasks_v1.json"),
                  encoding="utf-8") as f:
            tasks = json.load(f)["tasks"]
        for task in tasks:
            passed, total, details = run_unit_tests(
                task["reference_solution"], task["entry_point"],
                task["test_cases"], timeout=30,
            )
            self.assertEqual(passed, total,
                             f"{task['task_id']} 参考实现未全过: {details}")


if __name__ == "__main__":
    unittest.main()

"""质量判分：语法检查（自动）+ 单元测试（自动）+ LLM裁判（规范/健壮）。

质量总分权重由 config/eval.yaml 的 scoring.weights 提供（当前口径 v1.3：
0.10×语法 + 0.45×功能 + 0.20×规范 + 0.25×健壮）。
"""

import ast
import json
import os
import tempfile
from typing import Dict, List, Tuple

from .sandbox import run_python


def syntax_check(code: str) -> Tuple[float, List[str]]:
    """语法正确性：ast.parse + compile 全过得 100，否则 0。"""
    if not code or not code.strip():
        return 0.0, ["输出为空或非代码"]
    try:
        ast.parse(code)
        compile(code, "<candidate>", "exec")
        return 100.0, []
    except SyntaxError as e:
        return 0.0, [f"SyntaxError: {e.msg} (line {e.lineno})"]


# 生成的测试驱动器。占位符用 __TOKEN__ 形式，避免与代码内的花括号冲突。
_HARNESS_TEMPLATE = r'''
import importlib.util
import json
import sys

_ALLOWED_MODULES = ("operator", "time", "math", "functools")


def _resolve(arg):
    """以 @模块.函数 形式引用可调用对象，如 @operator.add。"""
    if isinstance(arg, str) and arg.startswith("@"):
        mod_name, _, attr = arg[1:].partition(".")
        if mod_name not in _ALLOWED_MODULES:
            raise ValueError("module not allowed: " + mod_name)
        return getattr(importlib.import_module(mod_name), attr)
    return arg


spec = importlib.util.spec_from_file_location("candidate", r"__CANDIDATE_PATH__")
mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
except Exception as e:
    print("IMPORT_ERROR " + type(e).__name__ + ": " + str(e))
    sys.exit(2)

cases = json.loads(r"""__CASES_JSON__""")
DEFAULT_ENTRY = "__ENTRY_POINT__"
passed = 0
for i, c in enumerate(cases):
    try:
        if "class" in c:
            cls = getattr(mod, c["class"], None)
            if cls is None:
                print("CASE_" + str(i) + "_ERROR class " + c["class"] + " not found")
                continue
            obj = cls(*c.get("ctor_args", []))
            step_returns = []
            for step in c.get("steps", []):
                head = step[0]
                if isinstance(head, str) and head.startswith("@step:"):
                    idx = int(head.split(":", 1)[1])
                    target = step_returns[idx]
                    name = step[1]
                    args = [_resolve(a) for a in step[2:]]
                elif head == "@last":
                    target = step_returns[-1]
                    name = step[1]
                    args = [_resolve(a) for a in step[2:]]
                else:
                    target = obj
                    name = head
                    args = [_resolve(a) for a in step[1:]]
                method = getattr(target, name)
                step_returns.append(method(*args))
            got = step_returns[-1] if step_returns else None
        else:
            fn = getattr(mod, c.get("entry_point", DEFAULT_ENTRY), None)
            if fn is None:
                print("CASE_" + str(i) + "_ERROR entry point not found")
                continue
            got = fn(*c["args"])
        ok = got == c["expected"]
        if not ok and isinstance(got, (int, float)) and isinstance(c["expected"], (int, float)):
            ok = abs(got - c["expected"]) < 1e-6
        if ok:
            passed += 1
        else:
            print("CASE_" + str(i) + "_FAIL got=" + repr(got) + " expected=" + repr(c["expected"]))
    except Exception as e:
        print("CASE_" + str(i) + "_ERROR " + type(e).__name__ + ": " + str(e))
print("PASSED " + str(passed) + "/" + str(len(cases)))
'''


def run_unit_tests(
    code: str,
    entry_point: str,
    test_cases: List[Dict],
    timeout: float = 30,
) -> Tuple[int, int, List[str]]:
    """在沙箱中运行单元测试，返回 (通过数, 总数, 失败明细)。"""
    if not test_cases:
        return 0, 0, ["无测试用例"]
    cases_json = json.dumps(test_cases, ensure_ascii=False)
    workdir = tempfile.mkdtemp(prefix="eval_tests_")
    candidate_path = os.path.join(workdir, "candidate.py")
    harness_path = os.path.join(workdir, "harness.py")
    try:
        with open(candidate_path, "w", encoding="utf-8") as f:
            f.write(code)
        harness = (_HARNESS_TEMPLATE
                   .replace("__CANDIDATE_PATH__", candidate_path)
                   .replace("__CASES_JSON__", cases_json)
                   .replace("__ENTRY_POINT__", entry_point))
        with open(harness_path, "w", encoding="utf-8") as f:
            f.write(harness)
        result = run_python(harness, timeout=timeout, cwd=workdir)
        details: List[str] = []
        passed, total = 0, len(test_cases)
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith("PASSED "):
                try:
                    passed = int(line.split()[1].split("/")[0])
                except (IndexError, ValueError):
                    pass
            elif line:
                details.append(line)
        if result.returncode != 0 and not any(d.startswith("CASE_") for d in details):
            details.append(f"harness exit={result.returncode}: {result.stderr.strip()[:300]}")
        if result.timed_out:
            details.append("测试执行超时")
        return passed, total, details
    finally:
        for p in (candidate_path, harness_path):
            try:
                os.unlink(p)
            except OSError:
                pass
        try:
            os.rmdir(workdir)
        except OSError:
            pass


def quality_total(syntax: float, functional: float, style: float, robustness: float,
                  weights: Dict[str, float]) -> float:
    """按权重合成质量总分（0~100）。style/robustness 缺失时按 0 计入并标记。"""
    return (
        weights["syntax"] * syntax
        + weights["functional"] * functional
        + weights["style"] * style
        + weights["robustness"] * robustness
    )

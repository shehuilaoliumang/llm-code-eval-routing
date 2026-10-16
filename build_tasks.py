"""48 题完整测试集构建器：DeepSeek-V4-Pro（官方 API）生成 + 自动质量门 + 反馈修订。

设计（三道质量门）：
  1. 参考实现必须通过自己的全部测试用例（沙箱实跑）——抓 LLM 错误期望值
  2. 防污染：prompt 要求改写题干/函数名/场景，不照搬公开基准原题；构建溯源（编辑器
     模型+版本+prompt哈希+日期）写入任务集元数据，随 manifest 复现
  3. 人工终审：生成物交项目负责人抽查（尤其 L3/L4 无歧义性）

用法:
    python build_tasks.py                 # 完整构建（12批次×4题）
    python build_tasks.py --difficulty L1 # 只构建某难度（调试用）
    python build_tasks.py --validate-only # 只校验现有 tasks_v2.json

产物: data/tasks/tasks_v2.json（48题 = 12/难度，含 dev/holdout 划分与溯源元数据）
成本: 约1.5元（官方 v4-pro，思考链关闭）
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from eval_kit.config import load_dotenv, load_yaml
from eval_kit.scoring import run_unit_tests

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(ROOT, "data", "tasks", "tasks_v2.json")

DIFFICULTY_RUBRIC = """L1 入门级：单函数、短代码（参考实现≤30行）、常见API、无复杂逻辑。如数组去重、冒泡排序、简单正则、字符串处理。
L2 进阶级：多函数协作、完整类/模块、中等算法、基础业务逻辑（参考实现≤60行）。如链表CRUD、计算器类封装、单接口CRUD、格式转换。
L3 高级：复杂算法、系统设计片段、调试重构、多模块协作（参考实现≤100行）。如红黑树、线程池、SQL优化、内存泄漏排查、设计模式。
L4 专家级：框架级代码、分布式核心逻辑、疑难问题（参考实现≤150行）。如简易ORM、分布式任务调度核心、性能瓶颈定位、编译器片段。"""

# 每难度 12 题的类型序列（覆盖制：功能/算法/调试/重构 四类均有）
TYPE_PLAN = {
    "L1": ["功能实现", "算法", "功能实现", "调试修复", "功能实现", "算法",
           "功能实现", "调试修复", "功能实现", "算法", "功能实现", "调试修复"],
    "L2": ["功能实现", "算法", "功能实现", "调试修复", "功能实现", "算法",
           "业务逻辑", "调试修复", "功能实现", "重构优化", "算法", "业务逻辑"],
    "L3": ["功能实现", "算法", "功能实现", "调试修复", "算法", "业务逻辑",
           "功能实现", "重构优化", "算法", "调试修复", "业务逻辑", "重构优化"],
    "L4": ["算法", "功能实现", "调试修复", "算法", "重构优化", "功能实现",
           "算法", "业务逻辑", "重构优化", "调试修复", "算法", "重构优化"],
}

LESSONS = """
历次构建中实测发现的失败模式（必须全部避免）：
1. **期望值计算错误**（最常见）：出题后必须逐用例手工推演期望值；测试数据要小到可以心算验证；
   优化类问题（背包/调度等）若存在多个最优解，必须在题目描述中规定确定性的解规则
   （如"存在多个最优选择集时返回字典序最小者"），否则测试无对错标准
2. 禁止返回函数/闭包/生成器等可调用对象——所有返回值必须是 JSON 可序列化的基本类型
3. 禁止返回 tuple——一律用 list；浮点结果避免精度陷阱，必要时 round(x, 2) 并在描述中说明保留位数
4. steps 中的 "@" 仅允许两种用法：引用模块级可调用（如 "@operator.add"）与 "@last" 链式调用；
   不得用于类自身方法（类方法直接写方法名）
5. 状态机/审批流类题目必须规定完整确定性的转移规则与初始状态；金额类用整数分或明确 round 规则
6. 写完参考实现后，以第一个测试用例在脑中走一遍代码，确认输出与期望一致再交卷
7. 测试用例中不要出现需要外部资源或依赖执行顺序的断言；每个用例相互独立"""

SYSTEM_PROMPT = """你是一名资深 Python 测评题目设计师，为一个 LLM 代码生成能力基准评测设计测试题。
你必须只输出一个 JSON 数组，不要任何额外解释、不要 markdown 代码围栏。

每道题是一个 JSON 对象，字段：
- task_id: 字符串，如 "L1-001"（按批次指定）
- difficulty: "L1"/"L2"/"L3"/"L4"
- task_type: "功能实现"/"算法"/"调试修复"/"重构优化"/"业务逻辑"
- description: 题目描述（自包含！被测模型只能看到这段文字）。功能/算法题说清输入输出与功能要求；
  调试修复题必须在描述中内嵌有 bug 的代码并说明现象；重构优化题必须内联待重构代码与优化目标
- entry_point: 主入口名称（函数用 snake_case，类用 PascalCase）
- test_cases: 4~6 个测试用例，两种格式：
    函数题: {"args": [参数...], "expected": 期望值}
    类题:   {"class": "类名", "ctor_args": [构造参数], "steps": [["方法名", 参数], ...], "expected": 最终返回值}
    steps 中可用 "@模块.函数" 引用可调用对象（如 "@operator.add"），"@last" 表示作用于上一步返回值
- reference_solution: 完整可独立运行的 Python 参考实现（含必要 import）
- constraints: 额外约束（时间复杂度、禁用内置函数等；无则空字符串）

硬性规则（违反任何一条都视为不合格）：
1. 只允许使用 Python 标准库；禁止网络、文件IO、多进程、随机数、时间依赖——必须完全确定性
2. expected 与 args 中的值必须是 JSON 可序列化类型（int/float/str/bool/None/list/dict）；
   禁止 tuple/set（期望列表用 list，集合类结果要求函数内部排序后返回 list）
3. 参考实现必须通过你自己写的全部测试用例——出题前请在脑中逐例推演
4. 函数入口名/类名必须新颖具体（如 "merge_intervals" 而非 "solve"），避免与公开基准重名
5. **改编要求**：基于常见编程知识点重新设计场景与数据规模，严禁照搬 HumanEval/MBPP/LeetCode 原题
   （换函数名、换场景 framing、自拟测试数据、补充边界用例）
6. 难度必须贴合下述定级标准，同级内难度均值一致
7. description 用简体中文，表述无歧义，包含输入输出格式说明

难度定级标准：
""" + DIFFICULTY_RUBRIC + LESSONS

USER_TEMPLATE = """请设计 {count} 道难度为 {difficulty} 的 Python 代码生成测试题。

本题批次的 task_id 与题型指定如下（必须严格遵守）：
{id_type_list}

{feedback_block}请直接输出 JSON 数组（{count} 个对象），不要任何其他内容。"""

# 格式示例（取自种子集，展示两种 test_cases 格式）
FORMAT_EXAMPLES = """
格式示例（函数题）：
{"task_id": "L1-001", "difficulty": "L1", "task_type": "功能实现",
 "description": "实现函数 dedup(nums)，去除整数列表中的重复元素，保留各元素首次出现的顺序并返回新列表。",
 "entry_point": "dedup",
 "test_cases": [{"args": [[1,2,2,3,1]], "expected": [1,2,3]},
                {"args": [[]], "expected": []},
                {"args": [[5,5,5]], "expected": [5]},
                {"args": [[3,1,2,1,3]], "expected": [3,1,2]}],
 "reference_solution": "def dedup(nums):\\n    seen = set()\\n    out = []\\n    for x in nums:\\n        if x not in seen:\\n            seen.add(x)\\n            out.append(x)\\n    return out\\n",
 "constraints": "时间复杂度 O(n)"}

格式示例（类题）：
{"task_id": "L2-001", "difficulty": "L2", "task_type": "功能实现",
 "description": "实现一个栈类 Stack，支持 push(item)/pop()/peek()/is_empty()/size()；对空栈 pop 或 peek 抛出 IndexError。",
 "entry_point": "Stack",
 "test_cases": [{"class": "Stack", "ctor_args": [], "steps": [["push", 1], ["push", 2], ["peek"]], "expected": 2},
                {"class": "Stack", "ctor_args": [], "steps": [["push", 1], ["pop"], ["is_empty"]], "expected": true},
                {"class": "Stack", "ctor_args": [], "steps": [["size"]], "expected": 0}],
 "reference_solution": "class Stack:\\n    def __init__(self):\\n        self._items = []\\n\\n    def push(self, item):\\n        self._items.append(item)\\n\\n    def pop(self):\\n        if self.is_empty():\\n            raise IndexError('pop from empty stack')\\n        return self._items.pop()\\n\\n    def peek(self):\\n        if self.is_empty():\\n            raise IndexError('peek from empty stack')\\n        return self._items[-1]\\n\\n    def is_empty(self):\\n        return len(self._items) == 0\\n\\n    def size(self):\\n        return len(self._items)\\n",
 "constraints": ""}
"""

STDLIB_WHITELIST = {
    "abc", "argparse", "array", "ast", "asyncio", "base64", "bisect", "calendar",
    "collections", "contextlib", "copy", "csv", "dataclasses", "datetime", "decimal",
    "enum", "functools", "fractions", "hashlib", "heapq", "itertools", "json", "math",
    "operator", "pathlib", "queue", "random", "re", "shutil", "socket", "statistics",
    "string", "struct", "textwrap", "time", "traceback", "types", "typing", "unicodedata",
    "urllib", "uuid", "weakref", "xml", "threading", "concurrent",
}


def extract_json_array(text: str):
    """从模型输出中提取 JSON 数组（容忍前后杂质与代码围栏）。"""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("输出中未找到 JSON 数组")
    return json.loads(text[start:end + 1])


def validate_task_schema(task: dict) -> list:
    """结构校验，返回错误列表（空=通过）。"""
    errors = []
    for field in ("task_id", "difficulty", "task_type", "description",
                  "entry_point", "test_cases", "reference_solution"):
        if field not in task:
            errors.append(f"缺少字段 {field}")
    if errors:
        return errors
    if task["difficulty"] not in TYPE_PLAN:
        errors.append(f"非法难度 {task['difficulty']}")
    if not isinstance(task["test_cases"], list) or not (4 <= len(task["test_cases"]) <= 6):
        errors.append(f"测试用例数应为4~6，实际 {len(task.get('test_cases', []))}")
    if not isinstance(task["reference_solution"], str) or len(task["reference_solution"]) < 20:
        errors.append("参考实现过短或缺失")
    if not task["description"] or len(task["description"]) < 30:
        errors.append("题目描述过短")
    # 标准库白名单
    try:
        import ast
        tree = ast.parse(task["reference_solution"])
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    root = a.name.split(".")[0]
                    if root not in STDLIB_WHITELIST:
                        errors.append(f"非白名单导入: {a.name}")
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                if root and root not in STDLIB_WHITELIST:
                    errors.append(f"非白名单导入: from {node.module}")
    except SyntaxError as e:
        errors.append(f"参考实现语法错误: {e}")
    return errors


def validate_reference_passes(task: dict) -> list:
    """质量门1：参考实现必须通过自己的全部测试（沙箱实跑）。"""
    passed, total, details = run_unit_tests(
        task["reference_solution"], task["entry_point"], task["test_cases"], timeout=30)
    if passed == total and total > 0:
        return []
    return [f"参考实现未通过自有测试: {passed}/{total} {details}"]


def generate_batch(client, difficulty: str, batch: list, attempt: int = 1,
                   feedback: str = "") -> list:
    """生成一批 4 道题（带反馈重试）。"""
    count = len(batch)
    id_type_list = "\n".join(f"  - {tid}（{ttype}）" for tid, ttype in batch)
    user = USER_TEMPLATE.format(count=count, difficulty=difficulty,
                                id_type_list=id_type_list,
                                feedback_block=feedback)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user + "\n" + FORMAT_EXAMPLES},
    ]
    # 429/5xx 指数退避重试（单次调用最多 6 次尝试，最长等待约 5 分钟）
    resp = None
    last_err = None
    for try_no in range(6):
        try:
            resp = client.chat.completions.create(
                model="deepseek-v4-pro",
                messages=messages,
                temperature=0.4 if attempt == 1 else 0.2,
                max_tokens=16000,
                timeout=300,
                extra_body={"thinking": {"type": "disabled"}},
            )
            break
        except Exception as e:  # noqa: BLE001
            last_err = e
            msg = str(e)
            retryable = ("429" in msg or "rate" in msg.lower()
                         or "500" in msg or "502" in msg or "503" in msg
                         or "timeout" in msg.lower())
            if not retryable or try_no == 5:
                raise
            wait = min(20 * (2 ** try_no), 180)
            print(f"    ⏳ 限流/服务错误，{wait}s 后重试 ({try_no + 1}/6): {msg[:70]}")
            time.sleep(wait)
    if resp is None:
        raise last_err
    tasks = extract_json_array(resp.choices[0].message.content)
    if not isinstance(tasks, list):
        raise ValueError("输出不是 JSON 数组")
    return tasks


def run_batch_with_repair(client, difficulty: str, batch_spec: list) -> tuple:
    """单题打捞：一批中通过的题立即收下，只重试失败的题（最多5轮）。"""
    collected = {}
    feedback_state = {"text": ""}
    for round_no in range(1, 6):
        pending = [(tid, tt) for tid, tt in batch_spec if tid not in collected]
        if not pending:
            break
        fb = "只生成以下 %d 题（task_id 与题型必须完全一致）：\n%s\n" % (
            len(pending), "\n".join(f"- {tid}（{tt}）" for tid, tt in pending))
        if feedback_state["text"]:
            fb += "上一轮的失败反馈（务必修正）：\n" + feedback_state["text"] + "\n"
        try:
            tasks = generate_batch(client, difficulty, pending,
                                    attempt=round_no, feedback=fb)
        except Exception as e:  # noqa: BLE001
            print(f"  第{round_no}轮生成失败: {type(e).__name__}: {str(e)[:90]}")
            continue
        errs_all = []
        n_pass = 0
        for t in tasks:
            tid = t.get("task_id")
            t.setdefault("difficulty", difficulty)
            errs = validate_task_schema(t) + validate_reference_passes(t)
            if errs:
                errs_all += [f"{tid}: {e}" for e in errs]
            elif tid in {i for i, _ in batch_spec} and tid not in collected:
                collected[tid] = t
                n_pass += 1
        if errs_all:
            print(f"  第{round_no}轮: 新增通过 {n_pass}，剩 {len(batch_spec)-len(collected)} 题待修")
            for e in errs_all[:3]:
                print(f"    - {e[:130]}")
            feedback_state["text"] = "\n".join(errs_all[:8])
        else:
            print(f"  第{round_no}轮: 全部通过")
    return collected, [(tid, tt) for tid, tt in batch_spec if tid not in collected]


def save_progress(all_tasks: list, extra_rules: list = None):
    """增量落盘：每完成一个批次就写一次，避免中途崩溃丢进度。"""
    tasks = sorted(all_tasks, key=lambda t: (t["difficulty"], t["task_id"]))
    for t in tasks:
        idx = int(t["task_id"].split("-")[1])
        t["split"] = "rule_dev" if idx <= 6 else "holdout"
    provenance = {
        "editor": "deepseek-v4-pro (DeepSeek official API)",
        "editor_thinking": "disabled",
        "prompt_hash": hashlib.sha256(
            (SYSTEM_PROMPT + USER_TEMPLATE + FORMAT_EXAMPLES).encode()).hexdigest()[:16],
        "built_at": datetime.now(timezone.utc).astimezone(
            timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
        "rules": ["仅标准库/确定性", "4~6测试用例", "参考实现须通过自有测试",
                  "改编自常见知识点，严禁照搬公开基准原题",
                  "dev/holdout=每难度前6/后6"] + (extra_rules or []),
    }
    payload = {"metadata": provenance, "tasks": tasks}
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    tmp = OUT_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT_PATH)
    return tasks


def build(prompt_hash_note: str = "", difficulties=("L1", "L2", "L3", "L4"),
          repair: bool = False):
    from openai import OpenAI
    load_dotenv(os.path.join(ROOT, ".env.local"))
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        print("❌ 缺少 DEEPSEEK_API_KEY（.env.local）")
        sys.exit(1)
    client = OpenAI(api_key=key, base_url="https://api.deepseek.com")

    all_tasks = []
    if repair and os.path.exists(OUT_PATH):
        with open(OUT_PATH, encoding="utf-8") as f:
            prev = json.load(f)
        all_tasks = prev["tasks"]
        print(f"修复模式：已有 {len(all_tasks)} 题，只补缺失题")

    for difficulty in difficulties:
        types = TYPE_PLAN[difficulty]
        have = {t["task_id"] for t in all_tasks if t["difficulty"] == difficulty}
        for b in range(3):
            batch_spec = [(f"{difficulty}-{b*4+i+1:03d}", types[b * 4 + i])
                          for i in range(4)]
            todo = [spec for spec in batch_spec if spec[0] not in have]
            if not todo:
                continue
            print(f"\n=== {difficulty} 批次 {b+1}/3: 待 {[t for _, t in todo]} ===")
            collected, failed = run_batch_with_repair(client, difficulty, todo)
            all_tasks.extend(collected.values())
            have |= set(collected.keys())
            if failed:
                print(f"  ⚠️ {len(failed)} 题5轮后仍未过门: {[tid for tid, _ in failed]}")
            else:
                print(f"  ✅ 批次完成")
            # 增量落盘 + 批次间隔（降低限流概率）
            save_progress(all_tasks, [
                "修复轮教训: 期望值手工推演/禁返回函数与tuple/优化题须规定平局规则"])
            print(f"  💾 已落盘，当前累计 {len(all_tasks)} 题")
            time.sleep(8)

    all_tasks = save_progress(all_tasks, [
        "修复轮教训: 期望值手工推演/禁返回函数与tuple/优化题须规定平局规则"])
    by_diff = {}
    for t in all_tasks:
        by_diff[t["difficulty"]] = by_diff.get(t["difficulty"], 0) + 1
    print(f"\n========== 构建/修复完成 ==========")
    print(f"产出: {OUT_PATH}")
    print(f"题目: {len(all_tasks)} 道 | 分布: {by_diff} | 缺口: {48 - len(all_tasks)}")


def validate_only():
    with open(OUT_PATH, encoding="utf-8") as f:
        payload = json.load(f)
    tasks = payload["tasks"] if isinstance(payload, dict) else payload
    print(f"校验 {OUT_PATH}: {len(tasks)} 题")
    fails = 0
    for t in tasks:
        errs = validate_task_schema(t) + validate_reference_passes(t)
        if errs:
            fails += 1
            print(f"  ❌ {t.get('task_id')}: {errs}")
    ids = [t["task_id"] for t in tasks]
    dup = len(ids) - len(set(ids))
    print(f"\n结果: {len(tasks) - fails}/{len(tasks)} 通过 | 重复ID: {dup}")
    by_split = {}
    for t in tasks:
        by_split[t.get("split", "?")] = by_split.get(t.get("split", "?"), 0) + 1
    print(f"划分: {by_split}")
    return fails == 0 and dup == 0


def main():
    ap = argparse.ArgumentParser(description="48题测试集构建器（DeepSeek-V4-Pro 编辑）")
    ap.add_argument("--validate-only", action="store_true")
    ap.add_argument("--repair", action="store_true", help="修复模式：保留已通过的题，只补缺失题")
    ap.add_argument("--difficulty", default=None, help="只构建指定难度（调试用）")
    args = ap.parse_args()
    if args.validate_only:
        sys.exit(0 if validate_only() else 1)
    if args.difficulty:
        build(difficulties=(args.difficulty,), repair=args.repair)
    else:
        build(repair=args.repair)


if __name__ == "__main__":
    main()

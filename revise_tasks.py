"""质量审计后的题目修正：替换退化/重复题，消除重名。

修正清单（审计发现）:
    L3-002  原为 max_sum_after_k_swaps，描述直接给出答案 -> 换为贪心+堆的任务调度题
    L3-005  与 L3-002 完全重复且退化          -> 换为编辑距离 DP 题
    L1-007  与 L1-001 实质雷同（同一手机号格式化）  -> 换为分数截断题
    L2-008  与 L2-004 同题重复（merge_sorted_lists）-> 换为最长连续递增段调试题
    L1-009  与 L1-001/L1-007 重名               -> 改名为 format_us_phone
    L3-008  与 L2-010 重名                        -> 改名为 apply_tier_discount

用法:
    python revise_tasks.py
"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_tasks import validate_reference_passes, validate_task_schema  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(ROOT, "data", "tasks", "tasks_v2.json")

REVISED = {
    "L1-007": {
        "task_id": "L1-007",
        "difficulty": "L1",
        "task_type": "功能实现",
        "description": (
            "实现函数 clamp_scores(scores)，接收一个数值列表 scores（元素为 int 或 float），"
            "返回一个新列表：其中小于 0 的元素变为 0，大于 100 的元素变为 100，"
            "其余元素保持原值不变。\n"
            "若输入列表为空，返回空列表。\n"
            "要求：不得修改原列表，必须返回一个新列表。\n"
            "示例：clamp_scores([-5, 50, 105]) 返回 [0, 50, 100]。"
        ),
        "entry_point": "clamp_scores",
        "test_cases": [
            {"args": [[-5, 50, 105]], "expected": [0, 50, 100]},
            {"args": [[]], "expected": []},
            {"args": [[-1, -2, -3]], "expected": [0, 0, 0]},
            {"args": [[101, 102]], "expected": [100, 100]},
            {"args": [[0, 50, 100]], "expected": [0, 50, 100]},
        ],
        "reference_solution": '''def clamp_scores(scores):
    result = []
    for s in scores:
        if s < 0:
            result.append(0)
        elif s > 100:
            result.append(100)
        else:
            result.append(s)
    return result
''',
        "constraints": "不得修改传入的原列表；时间复杂度 O(n)。",
    },
    "L1-009": {
        "task_id": "L1-009",
        "difficulty": "L1",
        "task_type": "功能实现",
        "description": (
            "实现函数 format_us_phone(digits: str) -> str。输入是一个仅包含数字字符的字符串，"
            "长度固定为 10。要求将其格式化为形如 \"(123) 456-7890\" 的美国电话号码格式："
            "前三位数字用小括号包裹，后跟一个空格，接着中间三位数字，再跟一个连字符，"
            "最后是四位数字。返回格式化后的字符串。\n"
            "示例：format_us_phone(\"1234567890\") 返回 \"(123) 456-7890\"。"
        ),
        "entry_point": "format_us_phone",
        "test_cases": [
            {"args": ["1234567890"], "expected": "(123) 456-7890"},
            {"args": ["0000000000"], "expected": "(000) 000-0000"},
            {"args": ["9876543210"], "expected": "(987) 654-3210"},
            {"args": ["1112223333"], "expected": "(111) 222-3333"},
        ],
        "reference_solution": '''def format_us_phone(digits: str) -> str:
    return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
''',
        "constraints": "输入长度固定为 10；只做格式化，不做合法性校验。",
    },
    "L2-008": {
        "task_id": "L2-008",
        "difficulty": "L2",
        "task_type": "调试修复",
        "description": (
            "下面这段代码的本意是：求整数列表 nums 中「最长连续严格递增段」的长度"
            "（连续指下标相邻，严格递增指后一个数严格大于前一个数）。\n"
            "但当前实现有 bug：无论输入什么，返回值永远是 1。\n\n"
            "```python\n"
            "def longest_increasing_run(nums):\n"
            "    if len(nums) == 0:\n"
            "        return 0\n"
            "    best = 1\n"
            "    cur = 1\n"
            "    for i in range(1, len(nums)):\n"
            "        if nums[i] > nums[i - 1]:\n"
            "            cur = cur + 1\n"
            "        else:\n"
            "            cur = 1\n"
            "    return best\n"
            "```\n\n"
            "请定位并修复该 bug，提交完整函数实现。约定：\n"
            "- 输入为空列表时返回 0；\n"
            "- 只含一个元素时返回 1；\n"
            "- 相邻元素相等即视为递增中断；\n"
            "- 返回值为整数。"
        ),
        "entry_point": "longest_increasing_run",
        "test_cases": [
            {"args": [[1, 2, 3, 1, 2]], "expected": 3},
            {"args": [[]], "expected": 0},
            {"args": [[5]], "expected": 1},
            {"args": [[3, 2, 1]], "expected": 1},
            {"args": [[1, 2, 2, 3]], "expected": 2},
            {"args": [[1, 2, 3, 4]], "expected": 4},
        ],
        "reference_solution": '''def longest_increasing_run(nums):
    if len(nums) == 0:
        return 0
    best = 1
    cur = 1
    for i in range(1, len(nums)):
        if nums[i] > nums[i - 1]:
            cur += 1
            if cur > best:
                best = cur
        else:
            cur = 1
    return best
''',
        "constraints": "时间复杂度 O(n)；仅一次遍历。",
    },
    "L3-002": {
        "task_id": "L3-002",
        "difficulty": "L3",
        "task_type": "算法",
        "description": (
            "实现函数 max_completable_tasks(tasks)。\n"
            "参数 tasks 是一个列表，元素形如 [duration, deadline]："
            "表示某个任务需要连续投入 duration 天完成，且完成时间不得晚于第 deadline 天"
            "（时间从第 0 天开始计，duration 与 deadline 均为正整数）。\n"
            "同一时间只能做一个任务，任务一旦开始不可中断，可以选择任意子集与执行顺序。\n"
            "返回最多能够完成的任务数（整数）。\n"
            "要求使用贪心 + 最大堆：按 deadline 升序依次考虑任务，累加已选任务总耗时；"
            "一旦总耗时超过当前任务的 deadline，就从已选任务中移除 duration 最大的那个。\n"
            "tasks 可能为空列表，此时返回 0。\n"
            "示例：max_completable_tasks([[3,4],[2,6],[1,3],[4,7]]) 返回 3。"
        ),
        "entry_point": "max_completable_tasks",
        "test_cases": [
            {"args": [[[3, 4], [2, 6], [1, 3], [4, 7]]], "expected": 3},
            {"args": [[[5, 5], [5, 5]]], "expected": 1},
            {"args": [[]], "expected": 0},
            {"args": [[[1, 10]]], "expected": 1},
            {"args": [[[1, 2], [2, 3], [3, 4]]], "expected": 2},
            {"args": [[[3, 2], [1, 3], [2, 4]]], "expected": 2},
        ],
        "reference_solution": '''import heapq


def max_completable_tasks(tasks):
    heap = []
    total = 0
    for duration, deadline in sorted(tasks or [], key=lambda t: (t[1], t[0])):
        total += duration
        heapq.heappush(heap, -duration)
        if total > deadline:
            total += heapq.heappop(heap)
    return len(heap)
''',
        "constraints": "时间复杂度 O(n log n)；使用最大堆保存已选任务耗时。",
    },
    "L3-005": {
        "task_id": "L3-005",
        "difficulty": "L3",
        "task_type": "算法",
        "description": (
            "实现函数 spell_check_distance(a, b)，计算把字符串 a 转换成字符串 b "
            "所需的最少单字符编辑次数（Levenshtein 距离）。\n"
            "允许的三种操作，每次计 1 次编辑：\n"
            "1. 在任意位置插入一个字符；\n"
            "2. 删除任意一个字符；\n"
            "3. 把任意一个字符替换成另一个字符。\n"
            "返回最少编辑次数（整数）。两字符串均为小写英文字母或空字符串。\n"
            "要求使用动态规划，时间复杂度 O(len(a) × len(b))，空间可优化为 O(min(len(a), len(b)))。\n"
            "示例：spell_check_distance(\"kitten\", \"sitting\") 返回 3；"
            "spell_check_distance(\"\", \"abc\") 返回 3。"
        ),
        "entry_point": "spell_check_distance",
        "test_cases": [
            {"args": ["kitten", "sitting"], "expected": 3},
            {"args": ["", "abc"], "expected": 3},
            {"args": ["abc", ""], "expected": 3},
            {"args": ["same", "same"], "expected": 0},
            {"args": ["flaw", "lawn"], "expected": 2},
            {"args": ["abc", "abd"], "expected": 1},
        ],
        "reference_solution": '''def spell_check_distance(a, b):
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[len(b)]
''',
        "constraints": "必须使用动态规划；禁止调用第三方编辑距离库。",
    },
    "L3-008": {
        "task_id": "L3-008",
        "difficulty": "L3",
        "task_type": "重构优化",
        "description": (
            "以下代码实现了一个简单的订单折扣计算器，但存在可读性差、重复代码多、"
            "扩展性差的问题。请重构代码，实现一个函数 "
            "apply_tier_discount(items, customer_tier)，"
            "其中 items 是一个列表，每个元素为字典，包含 'name'（字符串）、"
            "'price'（数字）、'quantity'（整数）；customer_tier 是字符串，"
            "取值为 'regular'、'silver'、'gold'。折扣规则：regular 无折扣；"
            "silver 享受 5% 折扣；gold 享受 10% 折扣。此外，如果订单总价（折扣前）"
            "超过 1000，则额外享受 5% 折扣（在等级折扣基础上叠加）。"
            "未知等级按 regular 处理。函数返回折扣后的总价，保留两位小数。"
            "请重构代码，使其结构清晰、易于扩展新的客户等级，并保持功能完全一致。\n\n"
            "待重构代码：\n"
            "```python\n"
            "def apply_tier_discount(items, customer_tier):\n"
            "    total = 0\n"
            "    for item in items:\n"
            "        total += item['price'] * item['quantity']\n"
            "    if customer_tier == 'regular':\n"
            "        discount = 0\n"
            "    elif customer_tier == 'silver':\n"
            "        discount = 0.05\n"
            "    elif customer_tier == 'gold':\n"
            "        discount = 0.10\n"
            "    else:\n"
            "        discount = 0\n"
            "    total = total * (1 - discount)\n"
            "    if total > 1000:\n"
            "        total = total * 0.95\n"
            "    return round(total, 2)\n"
            "```"
        ),
        "entry_point": "apply_tier_discount",
        "test_cases": [
            {"args": [[{"name": "apple", "price": 10, "quantity": 2},
                       {"name": "banana", "price": 5, "quantity": 4}], "regular"],
             "expected": 40.0},
            {"args": [[{"name": "laptop", "price": 1200, "quantity": 1}], "silver"],
             "expected": 1083.0},
            {"args": [[{"name": "phone", "price": 800, "quantity": 2}], "gold"],
             "expected": 1368.0},
            {"args": [[{"name": "book", "price": 30, "quantity": 3}], "regular"],
             "expected": 90.0},
            {"args": [[{"name": "tv", "price": 1500, "quantity": 1}], "gold"],
             "expected": 1282.5},
            {"args": [[{"name": "mouse", "price": 25, "quantity": 1}], "bronze"],
             "expected": 25.0},
        ],
        "reference_solution": '''TIER_DISCOUNT = {
    "regular": 0.0,
    "silver": 0.05,
    "gold": 0.10,
}
BULK_THRESHOLD = 1000
BULK_DISCOUNT = 0.05


def _subtotal(items):
    return sum(item["price"] * item["quantity"] for item in items or [])


def apply_tier_discount(items, customer_tier):
    subtotal = _subtotal(items)
    discount = TIER_DISCOUNT.get(customer_tier, TIER_DISCOUNT["regular"])
    total = subtotal * (1 - discount)
    if subtotal > BULK_THRESHOLD:
        total *= (1 - BULK_DISCOUNT)
    return round(total, 2)
''',
        "constraints": "折扣表必须写为模块级常量字典；未知等级按 regular 处理。",
    },
}


def main():
    with open(OUT_PATH, encoding="utf-8") as f:
        payload = json.load(f)

    ok = []
    for tid, task in REVISED.items():
        errs = validate_task_schema(task) + validate_reference_passes(task)
        if errs:
            print(f"❌ {tid}: {errs}")
            sys.exit(1)
        ok.append(tid)
        print(f"✅ {tid} 修正通过 -> {task['entry_point']} "
              f"({task['task_type']}, {len(task['test_cases'])} 用例)")

    by_id = {t["task_id"]: t for t in payload["tasks"]}
    by_id.update(REVISED)
    merged = sorted(by_id.values(), key=lambda t: (t["difficulty"], t["task_id"]))
    for t in merged:
        idx = int(t["task_id"].split("-")[1])
        t["split"] = "rule_dev" if idx <= 6 else "holdout"

    payload["tasks"] = merged
    payload["metadata"]["built_at"] = datetime.now().isoformat(timespec="seconds")
    payload["metadata"].setdefault("revisions", [])
    payload["metadata"]["revisions"].append({
        "reason": "质量审计：替换退化/重复题，消除入口名冲突",
        "task_ids": ok,
    })

    tmp = OUT_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT_PATH)
    print(f"\n已写入 {OUT_PATH} | 题目总数: {len(merged)} / 48")


if __name__ == "__main__":
    main()

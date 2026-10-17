"""L1 题目升级（v3）：由 DeepSeek-V4-Pro 直接出题，不调用 API。

升级动机（基于 tasks_v2 全量评测诊断）：
  L1 全部 12 题功能分标准差 = 0（8 模型全部 100 分），对 2026 年模型完全无区分度。
  根因：原 L1 是「数组去重/格式化/简单类」送分题。

升级设计（三类区分度杀手锏）：
  1. 密集边界条件：tricky 边界 case，马虎实现即失分
  2. 算法复杂度约束：大数据量测试（3~5 万元素）让 O(n²) 朴素实现超时、O(n)/O(n log n) 通过
  3. 非平凡逻辑：需要一定算法思维，非「一眼会」的送分题

用法:
    python upgrade_tasks.py --check      # 只校验不写
    python upgrade_tasks.py              # 校验通过后生成 tasks_v3.json（L1 升级 + L2/L3/L4 沿用 v2）
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_tasks import validate_reference_passes, validate_task_schema  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.path.join(ROOT, "data", "tasks", "tasks_v2.json")
OUT_PATH = os.path.join(ROOT, "data", "tasks", "tasks_v3.json")

# 大数据量性能测试用例（确定性构造，避免 random；O(n²) 超时、O(n) 秒过）
_BIG = list(range(1, 30001))  # 30000 个递增元素

L1_NEW = [
    {
        "task_id": "L1-001",
        "difficulty": "L1",
        "task_type": "功能实现",
        "description": (
            "实现函数 max_price_gain(prices)，给定某商品在一段时间内的每日价格序列 prices"
            "（非负整数列表），求「在某一天买入、之后的某一天卖出」所能获得的最大收益（卖出价减买入价）。\n"
            "只能买卖一次；必须先买后卖；若无法获利（如价格单调下降）则返回 0。\n"
            "要求：单次遍历完成，时间复杂度 O(n)。\n"
            "示例：max_price_gain([7,1,5,3,6,4]) 返回 5（第 2 天 1 元买入、第 5 天 6 元卖出）。"
        ),
        "entry_point": "max_price_gain",
        "test_cases": [
            {"args": [[7, 1, 5, 3, 6, 4]], "expected": 5},
            {"args": [[5, 4, 3, 2, 1]], "expected": 0},
            {"args": [[]], "expected": 0},
            {"args": [[3]], "expected": 0},
            {"args": [[1, 2, 3, 4, 5]], "expected": 4},
            {"args": [_BIG], "expected": 29999},
        ],
        "reference_solution": '''def max_price_gain(prices):
    if not prices:
        return 0
    min_price = prices[0]
    best = 0
    for p in prices[1:]:
        if p < min_price:
            min_price = p
        else:
            gain = p - min_price
            if gain > best:
                best = gain
    return best
''',
        "constraints": "时间复杂度 O(n)，单次遍历；不得使用暴力枚举所有买卖对。",
    },
    {
        "task_id": "L1-002",
        "difficulty": "L1",
        "task_type": "算法",
        "description": (
            "实现函数 find_two_sum(nums, target)，给定整数列表 nums 和整数 target，"
            "找出两个不同下标 i、j（i != j），使 nums[i] + nums[j] == target。\n"
            "若存在，返回 [i, j]（顺序任意，取任意一对即可）；若不存在，返回 [-1, -1]。\n"
            "要求：用哈希表一次遍历完成，时间复杂度 O(n)；不得使用双重循环暴力枚举。\n"
            "示例：find_two_sum([2,7,11,15], 9) 返回 [0,1]。"
        ),
        "entry_point": "find_two_sum",
        "test_cases": [
            {"args": [[2, 7, 11, 15], 9], "expected": [0, 1]},
            {"args": [[3, 3], 6], "expected": [0, 1]},
            {"args": [[1, 2, 3], 10], "expected": [-1, -1]},
            {"args": [[-1, -2, -3, -4], -6], "expected": [1, 3]},
            {"args": [[0, 4, 3, 0], 0], "expected": [0, 3]},
            {"args": [_BIG, 59999], "expected": [29998, 29999]},
        ],
        "reference_solution": '''def find_two_sum(nums, target):
    seen = {}
    for i, x in enumerate(nums):
        need = target - x
        if need in seen:
            return [seen[need], i]
        seen[x] = i
    return [-1, -1]
''',
        "constraints": "时间复杂度 O(n)；返回任意一对即可。",
    },
    {
        "task_id": "L1-003",
        "difficulty": "L1",
        "task_type": "功能实现",
        "description": (
            "实现函数 merge_ranges(intervals)，合并所有重叠的闭区间。\n"
            "intervals 是 [start, end] 列表（start <= end，整数），可能无序。\n"
            "若两个区间重叠（含端点相接，如 [1,2] 与 [2,3]），则合并为一个连续区间。\n"
            "返回按 start 升序排列的合并后区间列表。空输入返回空列表。\n"
            "示例：merge_ranges([[1,3],[2,6],[8,10],[15,18]]) 返回 [[1,6],[8,10],[15,18]]。"
        ),
        "entry_point": "merge_ranges",
        "test_cases": [
            {"args": [[[1, 3], [2, 6], [8, 10], [15, 18]]],
             "expected": [[1, 6], [8, 10], [15, 18]]},
            {"args": [[[1, 4], [4, 5]]], "expected": [[1, 5]]},
            {"args": [[[1, 5], [2, 3]]], "expected": [[1, 5]]},
            {"args": [[[3, 4], [1, 2], [2, 3]]], "expected": [[1, 4]]},
            {"args": [[[1, 2]]], "expected": [[1, 2]]},
            {"args": [[]], "expected": []},
        ],
        "reference_solution": '''def merge_ranges(intervals):
    if not intervals:
        return []
    ordered = sorted(intervals, key=lambda r: (r[0], r[1]))
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = [last_start, max(last_end, end)]
        else:
            merged.append([start, end])
    return merged
''',
        "constraints": "时间复杂度 O(n log n)（排序）；返回区间列表须按 start 升序。",
    },
    {
        "task_id": "L1-004",
        "difficulty": "L1",
        "task_type": "调试修复",
        "description": (
            "下面这个函数本意是：在升序排列的整数列表 nums 中，用二分查找找到「第一个 >= target 的元素下标」；"
            "若不存在则返回 -1。但当前实现有 off-by-one 错误：当 lo 与 hi 相邻或相等时，"
            "循环会提前退出，漏判最后一个候选元素。\n\n"
            "```python\n"
            "def lower_bound(nums, target):\n"
            "    lo, hi = 0, len(nums) - 1\n"
            "    ans = -1\n"
            "    while lo < hi:\n"
            "        mid = (lo + hi) // 2\n"
            "        if nums[mid] >= target:\n"
            "            ans = mid\n"
            "            hi = mid - 1\n"
            "        else:\n"
            "            lo = mid + 1\n"
            "    return ans\n"
            "```\n\n"
            "请修复并提交完整函数。约定：nums 已升序、可能为空或含重复元素；返回值为整数下标或 -1。"
        ),
        "entry_point": "lower_bound",
        "test_cases": [
            {"args": [[1, 3, 5, 7], 7], "expected": 3},
            {"args": [[1, 3, 5, 7], 1], "expected": 0},
            {"args": [[1, 3, 5, 7], 4], "expected": 2},
            {"args": [[1, 1, 1, 3], 1], "expected": 0},
            {"args": [[1, 3, 5, 7], 8], "expected": -1},
            {"args": [[], 1], "expected": -1},
        ],
        "reference_solution": '''def lower_bound(nums, target):
    lo, hi = 0, len(nums) - 1
    ans = -1
    while lo <= hi:
        mid = (lo + hi) // 2
        if nums[mid] >= target:
            ans = mid
            hi = mid - 1
        else:
            lo = mid + 1
    return ans
''',
        "constraints": "时间复杂度 O(log n)；正确处理空列表与重复元素。",
    },
    {
        "task_id": "L1-005",
        "difficulty": "L1",
        "task_type": "功能实现",
        "description": (
            "实现函数 decode_roman(s)，将罗马数字字符串转换为整数。\n"
            "字符值：I=1, V=5, X=10, L=50, C=100, D=500, M=1000。\n"
            "减法规则：小值字符在大值字符左侧时表示相减（如 IV=4、IX=9、XL=40、XC=90、CD=400、CM=900）。\n"
            "其余情况按从左到右相加。输入 s 保证为合法罗马数字（仅含上述大写字符），可能为空字符串（返回 0）。\n"
            "示例：decode_roman('MCMXCIV') 返回 1994；decode_roman('LVIII') 返回 58。"
        ),
        "entry_point": "decode_roman",
        "test_cases": [
            {"args": ["III"], "expected": 3},
            {"args": ["IV"], "expected": 4},
            {"args": ["IX"], "expected": 9},
            {"args": ["LVIII"], "expected": 58},
            {"args": ["MCMXCIV"], "expected": 1994},
            {"args": [""], "expected": 0},
        ],
        "reference_solution": '''def decode_roman(s):
    value = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    prev = 0
    for ch in reversed(s):
        cur = value[ch]
        if cur < prev:
            total -= cur
        else:
            total += cur
        prev = cur
    return total
''',
        "constraints": "时间复杂度 O(n)；正确处理减法规则（IV/IX/XL/XC/CD/CM）。",
    },
    {
        "task_id": "L1-006",
        "difficulty": "L1",
        "task_type": "算法",
        "description": (
            "实现函数 majority_element(nums)，找出列表中的多数元素——即出现次数严格超过 len(nums)/2 的元素。\n"
            "题目保证输入一定存在多数元素。\n"
            "要求：使用 Boyer-Moore 投票算法，时间复杂度 O(n)、空间复杂度 O(1)；"
            "不得使用 Counter/排序等需要额外空间或 O(n log n) 时间的方法。\n"
            "示例：majority_element([3,2,3]) 返回 3；majority_element([2,2,1,1,1,2,2]) 返回 2。"
        ),
        "entry_point": "majority_element",
        "test_cases": [
            {"args": [[3, 2, 3]], "expected": 3},
            {"args": [[2, 2, 1, 1, 1, 2, 2]], "expected": 2},
            {"args": [[1]], "expected": 1},
            {"args": [[7, 7, 5, 7, 5, 1, 5, 7, 5, 5, 7, 7, 7, 7, 7]], "expected": 7},
            {"args": [[0, 0, 0, 1]], "expected": 0},
            {"args": [[1] * 15000 + [2] * 15001], "expected": 2},
        ],
        "reference_solution": '''def majority_element(nums):
    candidate = None
    count = 0
    for x in nums:
        if count == 0:
            candidate = x
            count = 1
        elif x == candidate:
            count += 1
        else:
            count -= 1
    return candidate
''',
        "constraints": "时间复杂度 O(n)、空间复杂度 O(1)；必须用 Boyer-Moore 投票法。",
    },
    {
        "task_id": "L1-007",
        "difficulty": "L1",
        "task_type": "功能实现",
        "description": (
            "实现函数 longest_common_prefix(strs)，求字符串列表中所有字符串的最长公共前缀。\n"
            "若列表为空或不存在公共前缀，返回空字符串 ''。\n"
            "要求：横向逐字符扫描或纵向比较，时间复杂度 O(S)（S 为所有字符总数）。\n"
            "示例：longest_common_prefix(['flower','flow','flight']) 返回 'fl'。"
        ),
        "entry_point": "longest_common_prefix",
        "test_cases": [
            {"args": [["flower", "flow", "flight"]], "expected": "fl"},
            {"args": [["dog", "racecar", "car"]], "expected": ""},
            {"args": [["", "abc"]], "expected": ""},
            {"args": [["a"]], "expected": "a"},
            {"args": [[]], "expected": ""},
            {"args": [["ab", "abc", "abcd"]], "expected": "ab"},
        ],
        "reference_solution": '''def longest_common_prefix(strs):
    if not strs:
        return ""
    prefix = strs[0]
    for s in strs[1:]:
        while not s.startswith(prefix):
            prefix = prefix[:-1]
            if not prefix:
                return ""
    return prefix
''',
        "constraints": "时间复杂度 O(S)；正确处理空列表与含空串的情况。",
    },
    {
        "task_id": "L1-008",
        "difficulty": "L1",
        "task_type": "调试修复",
        "description": (
            "下面这个函数本意是反转一个 32 位有符号整数的数字位（如 123 -> 321，-123 -> -321），"
            "并在结果超出 32 位有符号整数范围 [-2147483648, 2147483647] 时返回 0。"
            "但当前实现缺少溢出检查，反转大数时会返回错误结果。\n\n"
            "```python\n"
            "def reverse_digits(x):\n"
            "    sign = -1 if x < 0 else 1\n"
            "    x = abs(x)\n"
            "    rev = 0\n"
            "    while x:\n"
            "        rev = rev * 10 + x % 10\n"
            "        x //= 10\n"
            "    return sign * rev\n"
            "```\n\n"
            "请修复并提交完整函数（注意：反转过程中的中间值也可能溢出，需在每次累加前检查）。"
        ),
        "entry_point": "reverse_digits",
        "test_cases": [
            {"args": [123], "expected": 321},
            {"args": [-123], "expected": -321},
            {"args": [120], "expected": 21},
            {"args": [0], "expected": 0},
            {"args": [1534236469], "expected": 0},
            {"args": [-2147483648], "expected": 0},
        ],
        "reference_solution": '''def reverse_digits(x):
    INT_MAX = 2147483647
    INT_MIN = -2147483648
    sign = -1 if x < 0 else 1
    x = abs(x)
    rev = 0
    while x:
        digit = x % 10
        if rev > (INT_MAX - digit) // 10:
            return 0
        rev = rev * 10 + digit
        x //= 10
    result = sign * rev
    if result < INT_MIN or result > INT_MAX:
        return 0
    return result
''',
        "constraints": "32 位有符号整数范围；溢出（含中间值）返回 0。",
    },
    {
        "task_id": "L1-009",
        "difficulty": "L1",
        "task_type": "功能实现",
        "description": (
            "实现函数 valid_brackets(s)，判断字符串 s 中的括号是否有效配对。\n"
            "括号种类：圆括号 ()、方括号 []、花括号 {}。\n"
            "有效条件：每种左括号必须由同类型的右括号闭合，且闭合顺序正确（后开先闭）。\n"
            "空字符串视为有效。\n"
            "要求：用栈实现，时间复杂度 O(n)。\n"
            "示例：valid_brackets('()[]{}') 返回 True；valid_brackets('([)]') 返回 False。"
        ),
        "entry_point": "valid_brackets",
        "test_cases": [
            {"args": ["()[]{}"], "expected": True},
            {"args": ["([)]"], "expected": False},
            {"args": ["{[]}"], "expected": True},
            {"args": [""], "expected": True},
            {"args": ["("], "expected": False},
            {"args": ["]"], "expected": False},
        ],
        "reference_solution": '''def valid_brackets(s):
    pairs = {")": "(", "]": "[", "}": "{"}
    stack = []
    for ch in s:
        if ch in "([{":
            stack.append(ch)
        elif ch in ")]}":
            if not stack or stack.pop() != pairs[ch]:
                return False
    return len(stack) == 0
''',
        "constraints": "时间复杂度 O(n)；使用栈；空串返回 True。",
    },
    {
        "task_id": "L1-010",
        "difficulty": "L1",
        "task_type": "算法",
        "description": (
            "实现函数 rotate_inplace(nums, k)，将列表 nums 向右循环移动 k 个位置，原地完成，返回移动后的列表。\n"
            "k 为非负整数，可能大于列表长度（此时取模处理）。\n"
            "要求：原地操作（不返回新列表、不分配等长辅助数组），用三次反转法，时间复杂度 O(n)、空间 O(1)。\n"
            "示例：rotate_inplace([1,2,3,4,5], 2) 返回 [4,5,1,2,3]。"
        ),
        "entry_point": "rotate_inplace",
        "test_cases": [
            {"args": [[1, 2, 3, 4, 5], 2], "expected": [4, 5, 1, 2, 3]},
            {"args": [[1, 2, 3], 3], "expected": [1, 2, 3]},
            {"args": [[1, 2, 3, 4], 5], "expected": [4, 1, 2, 3]},
            {"args": [[1], 10], "expected": [1]},
            {"args": [[1, 2, 3, 4], 0], "expected": [1, 2, 3, 4]},
            {"args": [list(range(20000)), 7777], "expected": list(range(20000))[-7777:] + list(range(20000))[:-7777]},
        ],
        "reference_solution": '''def rotate_inplace(nums, k):
    n = len(nums)
    if n == 0:
        return nums
    k %= n

    def reverse(lo, hi):
        while lo < hi:
            nums[lo], nums[hi] = nums[hi], nums[lo]
            lo += 1
            hi -= 1

    reverse(0, n - 1)
    reverse(0, k - 1)
    reverse(k, n - 1)
    return nums
''',
        "constraints": "原地操作（空间 O(1)）；k 可能大于 n，需取模；用三次反转法。",
    },
    {
        "task_id": "L1-011",
        "difficulty": "L1",
        "task_type": "功能实现",
        "description": (
            "实现函数 valid_ipv4(s)，判断字符串 s 是否为合法的 IPv4 地址。\n"
            "合法条件：恰好 4 段、用 '.' 分隔；每段为十进制整数，取值范围 0~255；"
            "不允许前导零（如 '01'、'007' 非法），但 '0' 本身合法；不得包含空段、多余字符或非数字。\n"
            "示例：valid_ipv4('192.168.1.1') 返回 True；valid_ipv4('192.168.01.1') 返回 False。"
        ),
        "entry_point": "valid_ipv4",
        "test_cases": [
            {"args": ["192.168.1.1"], "expected": True},
            {"args": ["0.0.0.0"], "expected": True},
            {"args": ["255.255.255.255"], "expected": True},
            {"args": ["192.168.01.1"], "expected": False},
            {"args": ["256.1.1.1"], "expected": False},
            {"args": ["1.2.3"], "expected": False},
        ],
        "reference_solution": '''def valid_ipv4(s):
    parts = s.split(".")
    if len(parts) != 4:
        return False
    for part in parts:
        if not part or not part.isdigit():
            return False
        if len(part) > 1 and part[0] == "0":
            return False
        if not 0 <= int(part) <= 255:
            return False
    return True
''',
        "constraints": "严格校验：4 段、0~255、无前导零、纯数字。",
    },
    {
        "task_id": "L1-012",
        "difficulty": "L1",
        "task_type": "调试修复",
        "description": (
            "下面这个函数本意是对字符串做游程压缩（Run-Length Encoding）：连续相同字符压缩为「字符+次数」，"
            "例如 'aabbb' -> 'a2b3'。规则：若压缩后的字符串长度不短于原串，则返回原串；否则返回压缩串。"
            "但当前实现有一个 bug：它总是返回压缩串，未做「压缩后不短则返回原串」的判断，"
            "导致如 'a' -> 'a1'、'ab' -> 'a1b1' 这类反而变长的情况也返回了压缩串。\n\n"
            "```python\n"
            "def run_length_encode(s):\n"
            "    if not s:\n"
            "        return s\n"
            "    parts = []\n"
            "    count = 1\n"
            "    for i in range(1, len(s)):\n"
            "        if s[i] == s[i - 1]:\n"
            "            count += 1\n"
            "        else:\n"
            "            parts.append(s[i - 1] + str(count))\n"
            "            count = 1\n"
            "    parts.append(s[-1] + str(count))\n"
            "    return ''.join(parts)\n"
            "```\n\n"
            "请修复并提交完整函数。约定：输入仅含小写字母，可能为空串。"
        ),
        "entry_point": "run_length_encode",
        "test_cases": [
            {"args": ["aabbb"], "expected": "a2b3"},
            {"args": ["a"], "expected": "a"},
            {"args": ["ab"], "expected": "ab"},
            {"args": ["aa"], "expected": "aa"},
            {"args": [""], "expected": ""},
            {"args": ["aaabbbccc"], "expected": "a3b3c3"},
        ],
        "reference_solution": '''def run_length_encode(s):
    if not s:
        return s
    parts = []
    count = 1
    for i in range(1, len(s)):
        if s[i] == s[i - 1]:
            count += 1
        else:
            parts.append(s[i - 1] + str(count))
            count = 1
    parts.append(s[-1] + str(count))
    compressed = "".join(parts)
    return compressed if len(compressed) < len(s) else s
''',
        "constraints": "压缩后不短于原串时必须返回原串。",
    },
]


def main():
    ap = argparse.ArgumentParser(description="L1 题目升级（v3）")
    ap.add_argument("--check", action="store_true", help="只校验不写文件")
    args = ap.parse_args()

    with open(SRC_PATH, encoding="utf-8") as f:
        src = json.load(f)

    ok, bad = [], []
    for task in L1_NEW:
        errs = validate_task_schema(task) + validate_reference_passes(task)
        if errs:
            bad.append((task["task_id"], errs))
            print(f"❌ {task['task_id']}: {errs}")
        else:
            ok.append(task)
            print(f"✅ {task['task_id']} [{task['task_type']}] entry={task['entry_point']} "
                  f"用例={len(task['test_cases'])}")

    print(f"\n校验结果: {len(ok)}/{len(L1_NEW)} 通过")
    if bad:
        print("存在未过门题目，未写入文件")
        sys.exit(1)
    if args.check:
        return

    by_id = {t["task_id"]: t for t in src["tasks"]}
    for task in ok:
        by_id[task["task_id"]] = task
    merged = sorted(by_id.values(), key=lambda t: (t["difficulty"], t["task_id"]))
    for t in merged:
        idx = int(t["task_id"].split("-")[1])
        t["split"] = "rule_dev" if idx <= 6 else "holdout"

    meta = dict(src["metadata"])
    meta["version"] = "v3-L1-upgraded"
    meta["built_at"] = __import__("datetime").datetime.now().isoformat(timespec="seconds")
    meta.setdefault("upgrade_log", []).append({
        "scope": "L1",
        "reason": "L1 全部 12 题功能分标准差=0（无区分度），升级为边界密集+性能敏感+非平凡逻辑题",
        "editor": "DeepSeek-V4-Pro（对话内直接出题，未调用 API）",
        "task_ids": [t["task_id"] for t in ok],
    })
    payload = {"metadata": meta, "tasks": merged}
    tmp = OUT_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT_PATH)

    from collections import Counter
    print(f"\n已写入 {OUT_PATH}")
    print(f"题目总数: {len(merged)} | L1 已升级 12 题，L2/L3/L4 沿用 v2")
    print(f"分布: {dict(sorted(Counter(t['difficulty'] for t in merged).items()))}")


if __name__ == "__main__":
    main()

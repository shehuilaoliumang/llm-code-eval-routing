"""L2/L3 题目升级（v3 第二批）：DeepSeek-V4-Pro 直接出题，不调 API。

诊断（tasks_v2 全量实测功能分标准差）：
  L2: 11 题 std=0（001/002/003/004/006/007/008/009/010/011/012）→ 全部替换，仅保留 L2-005
  L3: 9 题 std=0（002/004/005/007/008/009/010/011/012）→ 全部替换，保留 L3-001/003/006
区分度杀手锏（同 L1）：性能约束（大数据量 O(n²) 超时）、密集边界、非平凡算法。

用法:
    python upgrade23.py --check    # 只校验
    python upgrade23.py            # 校验后更新 tasks_v3.json（L2/L3 升级）
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_tasks import validate_reference_passes, validate_task_schema  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.path.join(ROOT, "data", "tasks", "tasks_v3.json")
OUT_PATH = os.path.join(ROOT, "data", "tasks", "tasks_v3.json")

_BIG = list(range(1, 30001))
_DEC = list(range(30000, 0, -1))  # 递减序列

L2_NEW = [
    {
        "task_id": "L2-001", "difficulty": "L2", "task_type": "功能实现",
        "description": (
            "实现函数 spiral_matrix(n)，生成 n×n 的螺旋矩阵：从左上角 1 开始，"
            "按「右→下→左→上」顺时针螺旋填入 1 到 n²。n 为正整数。\n"
            "返回二维整数列表。示例：spiral_matrix(3) 返回 [[1,2,3],[8,9,4],[7,6,5]]。"
        ),
        "entry_point": "spiral_matrix",
        "test_cases": [
            {"args": [3], "expected": [[1, 2, 3], [8, 9, 4], [7, 6, 5]]},
            {"args": [1], "expected": [[1]]},
            {"args": [2], "expected": [[1, 2], [4, 3]]},
            {"args": [4], "expected": [[1, 2, 3, 4], [12, 13, 14, 5], [11, 16, 15, 6], [10, 9, 8, 7]]},
        ],
        "reference_solution": '''def spiral_matrix(n):
    mat = [[0] * n for _ in range(n)]
    top, bottom, left, right = 0, n - 1, 0, n - 1
    num = 1
    while top <= bottom and left <= right:
        for c in range(left, right + 1):
            mat[top][c] = num
            num += 1
        top += 1
        for r in range(top, bottom + 1):
            mat[r][right] = num
            num += 1
        right -= 1
        for c in range(right, left - 1, -1):
            mat[bottom][c] = num
            num += 1
        bottom -= 1
        for r in range(bottom, top - 1, -1):
            mat[r][left] = num
            num += 1
        left += 1
    return mat
''',
        "constraints": "n 为正整数；正确处理奇偶 n。",
    },
    {
        "task_id": "L2-002", "difficulty": "L2", "task_type": "算法",
        "description": (
            "实现函数 next_greater(nums)，返回与 nums 等长的列表，其中第 i 个元素为 "
            "nums[i] 右侧第一个比它大的元素的值；若不存在则填 -1。\n"
            "要求：用单调栈，时间复杂度 O(n)；不得使用双重循环（大数据量下 O(n²) 会超时）。\n"
            "示例：next_greater([2,1,5]) 返回 [5,5,-1]。"
        ),
        "entry_point": "next_greater",
        "test_cases": [
            {"args": [[2, 1, 5]], "expected": [5, 5, -1]},
            {"args": [[1, 2, 3, 4]], "expected": [2, 3, 4, -1]},
            {"args": [[4, 3, 2, 1]], "expected": [-1, -1, -1, -1]},
            {"args": [[1]], "expected": [-1]},
            {"args": [[2, 4, 1, 3, 5]], "expected": [4, 5, 3, 5, -1]},
            {"args": [_DEC], "expected": [-1] * 30000},
        ],
        "reference_solution": '''def next_greater(nums):
    n = len(nums)
    result = [-1] * n
    stack = []
    for i in range(n - 1, -1, -1):
        while stack and stack[-1] <= nums[i]:
            stack.pop()
        result[i] = stack[-1] if stack else -1
        stack.append(nums[i])
    return result
''',
        "constraints": "时间复杂度 O(n)，单调栈；大数据量下禁止 O(n²)。",
    },
    {
        "task_id": "L2-003", "difficulty": "L2", "task_type": "功能实现",
        "description": (
            "实现函数 parse_duration(s)，把时长字符串解析为总秒数（int）。\n"
            "格式：由若干「数字+单位」片段组成，单位支持 d(天)/h(时)/m(分)/s(秒)，"
            "片段可任意顺序、可重复，如 '1h30m'、'90s'、'1d2h3m4s'、'1h30s'。\n"
            "输入保证合法（非空、数字为正整数）。示例：parse_duration('1h30m') 返回 5400。"
        ),
        "entry_point": "parse_duration",
        "test_cases": [
            {"args": ["1h30m"], "expected": 5400},
            {"args": ["90s"], "expected": 90},
            {"args": ["1d"], "expected": 86400},
            {"args": ["1d2h3m4s"], "expected": 93784},
            {"args": ["1h30s"], "expected": 3630},
            {"args": ["2m30s"], "expected": 150},
        ],
        "reference_solution": '''def parse_duration(s):
    units = {"d": 86400, "h": 3600, "m": 60, "s": 1}
    total = 0
    num = ""
    for ch in s:
        if ch.isdigit():
            num += ch
        else:
            total += int(num) * units[ch]
            num = ""
    return total
''',
        "constraints": "支持 d/h/m/s 四单位；片段可任意顺序；数字为正整数。",
    },
    {
        "task_id": "L2-004", "difficulty": "L2", "task_type": "调试修复",
        "description": (
            "下面这个函数本意是实现「荷兰国旗问题」：将仅含 0/1/2 的列表原地排序（0 在前、2 在后），"
            "一次遍历、O(1) 额外空间。但当前三指针的交换顺序有 bug，部分输入会得到错误结果。\n\n"
            "```python\n"
            "def sort_colors(nums):\n"
            "    low, mid, high = 0, 0, len(nums) - 1\n"
            "    while mid <= high:\n"
            "        if nums[mid] == 0:\n"
            "            nums[low], nums[mid] = nums[mid], nums[low]\n"
            "            low += 1\n"
            "            mid += 1\n"
            "        elif nums[mid] == 1:\n"
            "            mid += 1\n"
            "        else:\n"
            "            nums[mid], nums[high] = nums[high], nums[mid]\n"
            "            high -= 1\n"
            "    return nums\n"
            "```\n\n"
            "请修复并提交完整函数（原地排序，返回排序后的列表）。"
        ),
        "entry_point": "sort_colors",
        "test_cases": [
            {"args": [[2, 0, 2, 1, 1, 0]], "expected": [0, 0, 1, 1, 2, 2]},
            {"args": [[2, 0, 1]], "expected": [0, 1, 2]},
            {"args": [[0, 0, 0]], "expected": [0, 0, 0]},
            {"args": [[2, 2, 2]], "expected": [2, 2, 2]},
            {"args": [[1, 0]], "expected": [0, 1]},
            {"args": [[2] * 10000 + [0] * 10000 + [1] * 10000],
             "expected": [0] * 10000 + [1] * 10000 + [2] * 10000},
        ],
        "reference_solution": '''def sort_colors(nums):
    low, mid, high = 0, 0, len(nums) - 1
    while mid <= high:
        if nums[mid] == 0:
            nums[low], nums[mid] = nums[mid], nums[low]
            low += 1
            mid += 1
        elif nums[mid] == 1:
            mid += 1
        else:
            nums[mid], nums[high] = nums[high], nums[mid]
            high -= 1
    return nums
''',
        "constraints": "原地排序，一次遍历，O(1) 额外空间。",
    },
    {
        "task_id": "L2-006", "difficulty": "L2", "task_type": "算法",
        "description": (
            "实现函数 kth_largest(nums, k)，返回 nums 中第 k 大的元素（k 从 1 起，"
            "1 <= k <= len(nums)）。nums 可能含重复元素、长度很大。\n"
            "要求：平均 O(n) 时间（快速选择或等价算法）；禁止先排序再取（O(n log n) 在大数据量下偏慢）。\n"
            "示例：kth_largest([3,2,1,5,6,4], 2) 返回 5。"
        ),
        "entry_point": "kth_largest",
        "test_cases": [
            {"args": [[3, 2, 1, 5, 6, 4], 2], "expected": 5},
            {"args": [[3, 2, 3, 1, 2, 4, 5, 5, 6], 4], "expected": 4},
            {"args": [[1], 1], "expected": 1},
            {"args": [[1, 1, 1, 1], 1], "expected": 1},
            {"args": [[5, 5, 5, 3, 3, 3, 1], 4], "expected": 3},
            {"args": [_BIG, 15000], "expected": 15001},
        ],
        "reference_solution": '''import random


def kth_largest(nums, k):
    def quickselect(arr, target):
        pivot = arr[random.randrange(len(arr))]
        left = [x for x in arr if x > pivot]
        mid = [x for x in arr if x == pivot]
        right = [x for x in arr if x < pivot]
        if target <= len(left):
            return quickselect(left, target)
        if target > len(left) + len(mid):
            return quickselect(right, target - len(left) - len(mid))
        return pivot
    return quickselect(nums, k)
''',
        "constraints": "平均 O(n)；1 <= k <= len(nums)。",
    },
    {
        "task_id": "L2-007", "difficulty": "L2", "task_type": "业务逻辑",
        "description": (
            "实现类 OrderProcessor，模拟订单处理的状态机。构造无参数。\n"
            "方法：\n"
            "- place(order_id)：下单，状态置 'CREATED'，重复下单返回 'DUPLICATE'；\n"
            "- pay(order_id)：支付，CREATED→PAID，否则返回当前状态或错误信息；\n"
            "- ship(order_id)：发货，PAID→SHIPPED，否则报错；\n"
            "- deliver(order_id)：签收，SHIPPED→DELIVERED，否则报错；\n"
            "- cancel(order_id)：取消，仅 CREATED 或 PAID 可取消→CANCELLED；\n"
            "- status(order_id)：返回当前状态，不存在返回 'NOT_FOUND'。\n"
            "对不存在的订单执行 pay/ship/deliver/cancel 也返回 'NOT_FOUND'；"
            "订单存在但状态不允许该流转时返回 'INVALID_TRANSITION'。"
        ),
        "entry_point": "OrderProcessor",
        "test_cases": [
            {"class": "OrderProcessor", "ctor_args": [],
             "steps": [["place", "o1"], ["status", "o1"]], "expected": "CREATED"},
            {"class": "OrderProcessor", "ctor_args": [],
             "steps": [["place", "o1"], ["place", "o1"]], "expected": "DUPLICATE"},
            {"class": "OrderProcessor", "ctor_args": [],
             "steps": [["place", "o1"], ["pay", "o1"], ["ship", "o1"], ["deliver", "o1"],
                       ["status", "o1"]], "expected": "DELIVERED"},
            {"class": "OrderProcessor", "ctor_args": [],
             "steps": [["place", "o1"], ["ship", "o1"]], "expected": "INVALID_TRANSITION"},
            {"class": "OrderProcessor", "ctor_args": [],
             "steps": [["place", "o1"], ["pay", "o1"], ["cancel", "o1"], ["status", "o1"]],
             "expected": "CANCELLED"},
            {"class": "OrderProcessor", "ctor_args": [],
             "steps": [["status", "zz"]], "expected": "NOT_FOUND"},
        ],
        "reference_solution": '''class OrderProcessor:
    _FLOW = {
        "CREATED": {"pay": "PAID", "cancel": "CANCELLED"},
        "PAID": {"ship": "SHIPPED", "cancel": "CANCELLED"},
        "SHIPPED": {"deliver": "DELIVERED"},
        "DELIVERED": {},
        "CANCELLED": {},
    }

    def __init__(self):
        self._orders = {}

    def _transition(self, order_id, action):
        if order_id not in self._orders:
            return "NOT_FOUND"
        cur = self._orders[order_id]
        nxt = self._FLOW.get(cur, {}).get(action)
        if nxt is None:
            return "INVALID_TRANSITION"
        self._orders[order_id] = nxt
        return nxt

    def place(self, order_id):
        if order_id in self._orders:
            return "DUPLICATE"
        self._orders[order_id] = "CREATED"
        return "CREATED"

    def pay(self, order_id):
        return self._transition(order_id, "pay")

    def ship(self, order_id):
        return self._transition(order_id, "ship")

    def deliver(self, order_id):
        return self._transition(order_id, "deliver")

    def cancel(self, order_id):
        return self._transition(order_id, "cancel")

    def status(self, order_id):
        return self._orders.get(order_id, "NOT_FOUND")
''',
        "constraints": "状态机流转；非法流转返回 INVALID_TRANSITION；不存在返回 NOT_FOUND。",
    },
    {
        "task_id": "L2-008", "difficulty": "L2", "task_type": "调试修复",
        "description": (
            "下面这个函数本意是统计小于 n 的质数个数（埃拉托斯特尼筛法）。"
            "但当前实现有两处 bug：内层循环起始值错误导致大量合数未被标记，"
            "以及返回时把 n 本身也计入了。\n\n"
            "```python\n"
            "def count_primes(n):\n"
            "    if n < 3:\n"
            "        return 0\n"
            "    is_prime = [True] * n\n"
            "    is_prime[0] = is_prime[1] = False\n"
            "    for i in range(2, n):\n"
            "        if is_prime[i]:\n"
            "            for j in range(i * i, n, 1):\n"
            "                is_prime[j] = False\n"
            "    return sum(is_prime)\n"
            "```\n\n"
            "请修复并提交完整函数。约定：n 为非负整数；返回严格小于 n 的质数个数。"
        ),
        "entry_point": "count_primes",
        "test_cases": [
            {"args": [10], "expected": 4},
            {"args": [2], "expected": 0},
            {"args": [3], "expected": 1},
            {"args": [20], "expected": 8},
            {"args": [0], "expected": 0},
            {"args": [100], "expected": 25},
        ],
        "reference_solution": '''def count_primes(n):
    if n < 3:
        return 0
    is_prime = [True] * n
    is_prime[0] = is_prime[1] = False
    for i in range(2, int(n ** 0.5) + 1):
        if is_prime[i]:
            for j in range(i * i, n, i):
                is_prime[j] = False
    return sum(is_prime)
''',
        "constraints": "埃氏筛；时间复杂度 O(n log log n)；返回严格小于 n 的质数个数。",
    },
    {
        "task_id": "L2-009", "difficulty": "L2", "task_type": "功能实现",
        "description": (
            "实现函数 flatten_deep(nested)，将任意深度嵌套的列表完全扁平化为一维列表。\n"
            "nested 的元素为整数或嵌套列表（可能深层嵌套），返回按原顺序展开的一维整数列表。\n"
            "要求：处理任意深度（可能很深），避免递归栈溢出（用显式栈/迭代）。\n"
            "示例：flatten_deep([1,[2,[3,[4]],5]]) 返回 [1,2,3,4,5]。"
        ),
        "entry_point": "flatten_deep",
        "test_cases": [
            {"args": [[1, [2, [3, [4]], 5]]], "expected": [1, 2, 3, 4, 5]},
            {"args": [[1, 2, 3]], "expected": [1, 2, 3]},
            {"args": [[]], "expected": []},
            {"args": [[[[[1]]]]], "expected": [1]},
            {"args": [[1, [], 2, [3, []]]], "expected": [1, 2, 3]},
            {"args": [list(range(1, 10001))], "expected": list(range(1, 10001))},
        ],
        "reference_solution": '''def flatten_deep(nested):
    result = []
    stack = list(reversed(nested))
    while stack:
        item = stack.pop()
        if isinstance(item, list):
            stack.extend(reversed(item))
        else:
            result.append(item)
    return result
''',
        "constraints": "用迭代/显式栈，避免深递归栈溢出；保持原顺序。",
    },
    {
        "task_id": "L2-010", "difficulty": "L2", "task_type": "重构优化",
        "description": (
            "下面这个运费计算函数用多层嵌套 if 且重复代码多、魔法数字散落。请重构为清晰实现，"
            "函数签名保持 shipping_fee(weight_kg, distance_km, is_express)，行为完全一致：\n\n"
            "```python\n"
            "def shipping_fee(weight_kg, distance_km, is_express):\n"
            "    base = 10\n"
            "    fee = base\n"
            "    if weight_kg <= 1:\n"
            "        fee = fee + 0\n"
            "    elif weight_kg <= 5:\n"
            "        fee = fee + weight_kg * 3\n"
            "    else:\n"
            "        fee = fee + weight_kg * 5\n"
            "    if distance_km <= 100:\n"
            "        fee = fee + 0\n"
            "    elif distance_km <= 500:\n"
            "        fee = fee + 10\n"
            "    else:\n"
            "        fee = fee + 20\n"
            "    if is_express:\n"
            "        fee = fee * 1.5\n"
            "    return round(fee, 2)\n"
            "```\n\n"
            "要求：消除重复分支与魔法数字，保持浮点结果两位小数，负重量/负距离抛 ValueError。"
        ),
        "entry_point": "shipping_fee",
        "test_cases": [
            {"args": [0.5, 50, False], "expected": 10.0},
            {"args": [3, 200, False], "expected": 29.0},
            {"args": [8, 600, True], "expected": 105.0},
            {"args": [1, 100, False], "expected": 10.0},
            {"args": [5, 500, False], "expected": 35.0},
        ],
        "reference_solution": '''BASE = 10.0
LIGHT_MAX = 1.0
MID_MAX = 5.0
LIGHT_RATE, MID_RATE, HEAVY_RATE = 0.0, 3.0, 5.0
NEAR_MAX, MID_DIST = 100.0, 500.0
NEAR_FEE, MID_FEE, FAR_FEE = 0.0, 10.0, 20.0
EXPRESS = 1.5


def _tier(value, limits_rates, fallback):
    for limit, rate in limits_rates:
        if value <= limit:
            return rate
    return fallback


def shipping_fee(weight_kg, distance_km, is_express):
    if weight_kg < 0 or distance_km < 0:
        raise ValueError("weight and distance must be non-negative")
    weight_fee = _tier(weight_kg, ((LIGHT_MAX, LIGHT_RATE), (MID_MAX, MID_RATE)), HEAVY_RATE)
    distance_fee = _tier(distance_km, ((NEAR_MAX, NEAR_FEE), (MID_DIST, MID_FEE)), FAR_FEE)
    total = BASE + weight_kg * weight_fee + distance_fee
    if is_express:
        total *= EXPRESS
    return round(total, 2)
''',
        "constraints": "消除重复分支与魔法数字；负重量/距离抛 ValueError；保留两位小数。",
    },
    {
        "task_id": "L2-011", "difficulty": "L2", "task_type": "算法",
        "description": (
            "实现函数 longest_consecutive(nums)，求未排序整数列表中「最长连续整数序列」的长度"
            "（序列元素在原列表中不必相邻）。\n"
            "要求：O(n) 时间（用哈希集合）；禁止先排序（O(n log n) 大数据量下超时）。\n"
            "示例：longest_consecutive([100,4,200,1,3,2]) 返回 4（序列 [1,2,3,4]）。"
        ),
        "entry_point": "longest_consecutive",
        "test_cases": [
            {"args": [[100, 4, 200, 1, 3, 2]], "expected": 4},
            {"args": [[0, 0]], "expected": 1},
            {"args": [[1, 2, 0, 1]], "expected": 3},
            {"args": [[]], "expected": 0},
            {"args": [[5]], "expected": 1},
            {"args": [_BIG], "expected": 30000},
        ],
        "reference_solution": '''def longest_consecutive(nums):
    s = set(nums)
    best = 0
    for x in s:
        if x - 1 not in s:
            cur = 1
            y = x
            while y + 1 in s:
                y += 1
                cur += 1
            if cur > best:
                best = cur
    return best
''',
        "constraints": "O(n) 时间，哈希集合；禁止排序。",
    },
    {
        "task_id": "L2-012", "difficulty": "L2", "task_type": "业务逻辑",
        "description": (
            "实现类 Trie，前缀树，用于存储单词并支持前缀查询。构造无参数。\n"
            "方法：\n"
            "- insert(word)：插入单词（小写字母）；\n"
            "- search(word)：单词是否完整存在，返回 bool；\n"
            "- starts_with(prefix)：是否存在以该前缀开头的单词，返回 bool；\n"
            "- count_words()：当前完整单词总数。\n"
            "示例：插入 'apple' 后 search('apple') True、search('app') False、starts_with('app') True。"
        ),
        "entry_point": "Trie",
        "test_cases": [
            {"class": "Trie", "ctor_args": [],
             "steps": [["insert", "apple"], ["search", "apple"]], "expected": True},
            {"class": "Trie", "ctor_args": [],
             "steps": [["insert", "apple"], ["search", "app"]], "expected": False},
            {"class": "Trie", "ctor_args": [],
             "steps": [["insert", "apple"], ["starts_with", "app"]], "expected": True},
            {"class": "Trie", "ctor_args": [],
             "steps": [["insert", "apple"], ["insert", "app"], ["count_words"]], "expected": 2},
            {"class": "Trie", "ctor_args": [],
             "steps": [["starts_with", "z"]], "expected": False},
            {"class": "Trie", "ctor_args": [],
             "steps": [["insert", "a"], ["insert", "a"], ["count_words"]], "expected": 1},
        ],
        "reference_solution": '''class Trie:
    def __init__(self):
        self._root = {}
        self._count = 0

    def insert(self, word):
        node = self._root
        for ch in word:
            node = node.setdefault(ch, {})
        if "_end" not in node:
            node["_end"] = True
            self._count += 1

    def search(self, word):
        node = self._root
        for ch in word:
            if ch not in node:
                return False
            node = node[ch]
        return "_end" in node

    def starts_with(self, prefix):
        node = self._root
        for ch in prefix:
            if ch not in node:
                return False
            node = node[ch]
        return True

    def count_words(self):
        return self._count
''',
        "constraints": "用字典节点；insert/search/starts_with O(len(word))。",
    },
]

L3_NEW = [
    {
        "task_id": "L3-002", "difficulty": "L3", "task_type": "算法",
        "description": (
            "实现函数 min_path_sum(grid)，求从 m×n 网格左上角 (0,0) 走到右下角 (m-1,n-1) 的"
            "最小路径和。每步只能向右或向下移动，路径和 = 沿途所有格子数值之和。\n"
            "grid 为 m×n 非负整数矩阵（可能含 0），m,n >= 1。要求动态规划，O(m×n)。\n"
            "示例：min_path_sum([[1,3,1],[1,5,1],[4,2,1]]) 返回 7（路径 1→1→3→1→1）。"
        ),
        "entry_point": "min_path_sum",
        "test_cases": [
            {"args": [[[1, 3, 1], [1, 5, 1], [4, 2, 1]]], "expected": 7},
            {"args": [[[1, 2], [3, 4]]], "expected": 7},
            {"args": [[[5]]], "expected": 5},
            {"args": [[[1, 2, 3]]], "expected": 6},
            {"args": [[[0, 0], [0, 0]]], "expected": 0},
            {"args": [[[1, 100, 1], [1, 100, 1], [1, 1, 1]]], "expected": 5},
        ],
        "reference_solution": '''def min_path_sum(grid):
    m, n = len(grid), len(grid[0])
    dp = [[0] * n for _ in range(m)]
    dp[0][0] = grid[0][0]
    for c in range(1, n):
        dp[0][c] = dp[0][c - 1] + grid[0][c]
    for r in range(1, m):
        dp[r][0] = dp[r - 1][0] + grid[r][0]
    for r in range(1, m):
        for c in range(1, n):
            dp[r][c] = min(dp[r - 1][c], dp[r][c - 1]) + grid[r][c]
    return dp[m - 1][n - 1]
''',
        "constraints": "动态规划 O(m×n)；只能向右/向下。",
    },
    {
        "task_id": "L3-004", "difficulty": "L3", "task_type": "调试修复",
        "description": (
            "下面这个快排的 partition 有 bug：当首元素恰好是最小值或出现大量相等元素时，"
            "会无限递归或分区错误。\n\n"
            "```python\n"
            "def quicksort(nums):\n"
            "    if len(nums) <= 1:\n"
            "        return nums\n"
            "    pivot = nums[0]\n"
            "    left = [x for x in nums[1:] if x <= pivot]\n"
            "    right = [x for x in nums[1:] if x > pivot]\n"
            "    return quicksort(left) + [pivot] + quicksort(right)\n"
            "```\n\n"
            "请修复并提交完整函数（返回升序排序的新列表，不改动原列表）。"
        ),
        "entry_point": "quicksort",
        "test_cases": [
            {"args": [[3, 1, 4, 1, 5, 9, 2, 6]], "expected": [1, 1, 2, 3, 4, 5, 6, 9]},
            {"args": [[5, 4, 3, 2, 1]], "expected": [1, 2, 3, 4, 5]},
            {"args": [[1, 1, 1, 1]], "expected": [1, 1, 1, 1]},
            {"args": [[]], "expected": []},
            {"args": [[7]], "expected": [7]},
            {"args": [[2, 2, 1, 1, 0, 0]], "expected": [0, 0, 1, 1, 2, 2]},
        ],
        "reference_solution": '''def quicksort(nums):
    if len(nums) <= 1:
        return nums
    pivot = nums[len(nums) // 2]
    left = [x for x in nums if x < pivot]
    mid = [x for x in nums if x == pivot]
    right = [x for x in nums if x > pivot]
    return quicksort(left) + mid + quicksort(right)
''',
        "constraints": "返回升序新列表；正确处理相等元素；不修改原列表。",
    },
    {
        "task_id": "L3-005", "difficulty": "L3", "task_type": "算法",
        "description": (
            "实现函数 lis_length(nums)，求最长严格递增子序列的长度（子序列元素不要求连续，"
            "但须保持原顺序且严格递增）。\n"
            "要求：O(n log n) 时间（贪心 + 二分，或 patience sorting）；"
            "禁止 O(n²) 动态规划（大数据量下超时）。\n"
            "示例：lis_length([10,9,2,5,3,7,101,18]) 返回 4（[2,3,7,101]）。"
        ),
        "entry_point": "lis_length",
        "test_cases": [
            {"args": [[10, 9, 2, 5, 3, 7, 101, 18]], "expected": 4},
            {"args": [[0, 1, 0, 3, 2, 3]], "expected": 4},
            {"args": [[7, 7, 7, 7]], "expected": 1},
            {"args": [[]], "expected": 0},
            {"args": [[5]], "expected": 1},
            {"args": [_BIG], "expected": 30000},
        ],
        "reference_solution": '''import bisect


def lis_length(nums):
    tails = []
    for x in nums:
        i = bisect.bisect_left(tails, x)
        if i == len(tails):
            tails.append(x)
        else:
            tails[i] = x
    return len(tails)
''',
        "constraints": "O(n log n)；贪心 + 二分；严格递增。",
    },
    {
        "task_id": "L3-007", "difficulty": "L3", "task_type": "功能实现",
        "description": (
            "实现函数 evaluate_rpn(tokens)，计算逆波兰表达式（RPN）的值。\n"
            "tokens 为字符串列表，元素为整数（正负）或运算符 + - * /。\n"
            "除法为「向零取整」的整数除法（Python 语义）；保证表达式合法，运算不会除零。\n"
            "用栈实现。示例：evaluate_rpn(['2','1','+','3','*']) 返回 9；"
            "evaluate_rpn(['4','13','5','/','+']) 返回 6。"
        ),
        "entry_point": "evaluate_rpn",
        "test_cases": [
            {"args": [["2", "1", "+", "3", "*"]], "expected": 9},
            {"args": [["4", "13", "5", "/", "+"]], "expected": 6},
            {"args": [["10", "6", "9", "3", "+", "-11", "*", "/", "*", "17", "+", "5", "+"]], "expected": 22},
            {"args": [["5"]], "expected": 5},
            {"args": [["3", "-4", "*"]], "expected": -12},
            {"args": [["7", "3", "/"]], "expected": 2},
        ],
        "reference_solution": '''def evaluate_rpn(tokens):
    stack = []
    for t in tokens:
        if t in ("+", "-", "*", "/"):
            b = stack.pop()
            a = stack.pop()
            if t == "+":
                stack.append(a + b)
            elif t == "-":
                stack.append(a - b)
            elif t == "*":
                stack.append(a * b)
            else:
                stack.append(int(a / b))
        else:
            stack.append(int(t))
    return stack[0]
''',
        "constraints": "栈实现；除法向零取整；表达式合法。",
    },
    {
        "task_id": "L3-008", "difficulty": "L3", "task_type": "重构优化",
        "description": (
            "下面这个文档审批函数用一长串 if/elif 硬编码状态转移，新增状态就要改判断链。"
            "请重构为状态转移表驱动，函数签名保持 approve(state, action)，行为完全等价：\n\n"
            "```python\n"
            "def approve(state, action):\n"
            "    if state == 'DRAFT':\n"
            "        if action == 'SUBMIT':\n"
            "            return 'PENDING'\n"
            "        elif action == 'DISCARD':\n"
            "            return 'DISCARDED'\n"
            "        else:\n"
            "            return 'INVALID'\n"
            "    elif state == 'PENDING':\n"
            "        if action == 'APPROVE':\n"
            "            return 'APPROVED'\n"
            "        elif action == 'REJECT':\n"
            "            return 'REJECTED'\n"
            "        else:\n"
            "            return 'INVALID'\n"
            "    elif state == 'APPROVED':\n"
            "        if action == 'PUBLISH':\n"
            "            return 'PUBLISHED'\n"
            "        else:\n"
            "            return 'INVALID'\n"
            "    else:\n"
            "        return 'INVALID'\n"
            "```\n\n"
            "要求：把转移规则写成模块级字典常量，函数体只做查表，无状态字符串比较。"
        ),
        "entry_point": "approve",
        "test_cases": [
            {"args": ["DRAFT", "SUBMIT"], "expected": "PENDING"},
            {"args": ["DRAFT", "DISCARD"], "expected": "DISCARDED"},
            {"args": ["PENDING", "APPROVE"], "expected": "APPROVED"},
            {"args": ["PENDING", "REJECT"], "expected": "REJECTED"},
            {"args": ["APPROVED", "PUBLISH"], "expected": "PUBLISHED"},
            {"args": ["PUBLISHED", "APPROVE"], "expected": "INVALID"},
        ],
        "reference_solution": '''INVALID = "INVALID"

TRANSITIONS = {
    ("DRAFT", "SUBMIT"): "PENDING",
    ("DRAFT", "DISCARD"): "DISCARDED",
    ("PENDING", "APPROVE"): "APPROVED",
    ("PENDING", "REJECT"): "REJECTED",
    ("APPROVED", "PUBLISH"): "PUBLISHED",
}


def approve(state, action):
    return TRANSITIONS.get((state, action), INVALID)
''',
        "constraints": "转移规则写成模块级字典常量；函数体只查表。",
    },
    {
        "task_id": "L3-009", "difficulty": "L3", "task_type": "算法",
        "description": (
            "实现函数 build_order(projects, dependencies)，返回满足依赖关系的一个执行顺序。\n"
            "projects 为项目名字符串列表（无重复）；dependencies 为 [a, b] 列表，表示 a 依赖 b（b 先执行）。\n"
            "要求拓扑排序：当多个项目可执行时取字典序最小者（保证结果唯一）。"
            "若存在循环依赖，返回 ['CYCLE']。dependencies 可能为 None。\n"
            "示例：build_order(['a','b','c','d'], [['a','b'],['b','c'],['c','d']]) 返回 ['d','c','b','a']。"
        ),
        "entry_point": "build_order",
        "test_cases": [
            {"args": [["a", "b", "c", "d"], [["a", "b"], ["b", "c"], ["c", "d"]]],
             "expected": ["d", "c", "b", "a"]},
            {"args": [["x", "y"], [["x", "y"], ["y", "x"]]], "expected": ["CYCLE"]},
            {"args": [["a", "b", "c"], []], "expected": ["a", "b", "c"]},
            {"args": [["web", "db", "cache"], [["web", "db"], ["cache", "db"]]],
             "expected": ["db", "cache", "web"]},
            {"args": [["a"], [["a", "a"]]], "expected": ["CYCLE"]},
            {"args": [["m", "n", "o"], [["m", "n"]]], "expected": ["n", "m", "o"]},
        ],
        "reference_solution": '''import heapq


def build_order(projects, dependencies):
    graph = {p: [] for p in projects}
    indeg = {p: 0 for p in projects}
    for a, b in (dependencies or []):
        if a not in graph or b not in graph:
            continue
        graph[b].append(a)
        indeg[a] += 1
    ready = [p for p in projects if indeg[p] == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        cur = heapq.heappop(ready)
        order.append(cur)
        for nxt in graph[cur]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                heapq.heappush(ready, nxt)
    return order if len(order) == len(projects) else ["CYCLE"]
''',
        "constraints": "拓扑排序（Kahn）；同级取字典序最小；有环返回 ['CYCLE']。",
    },
    {
        "task_id": "L3-010", "difficulty": "L3", "task_type": "调试修复",
        "description": (
            "下面这个并查集（Union-Find）实现用于判断无向图中两点是否连通，但 find 未做路径压缩、"
            "union 未按秩合并，导致在长链时退化为 O(n)（甚至递归栈溢出风险）。\n\n"
            "```python\n"
            "class DSU:\n"
            "    def __init__(self, n):\n"
            "        self.parent = list(range(n))\n"
            "\n"
            "    def find(self, x):\n"
            "        while self.parent[x] != x:\n"
            "            x = self.parent[x]\n"
            "        return x\n"
            "\n"
            "    def union(self, a, b):\n"
            "        self.parent[self.find(a)] = self.find(b)\n"
            "\n"
            "    def connected(self, a, b):\n"
            "        return self.find(a) == self.find(b)\n"
            "```\n\n"
            "请修复并提交完整类（路径压缩 + 按秩合并），用于下面的连通性判断测试。"
        ),
        "entry_point": "DSU",
        "test_cases": [
            {"class": "DSU", "ctor_args": [5],
             "steps": [["union", 0, 1], ["connected", 0, 1]], "expected": True},
            {"class": "DSU", "ctor_args": [5],
             "steps": [["connected", 0, 4]], "expected": False},
            {"class": "DSU", "ctor_args": [6],
             "steps": [["union", 0, 1], ["union", 1, 2], ["union", 3, 4], ["connected", 0, 2]],
             "expected": True},
            {"class": "DSU", "ctor_args": [6],
             "steps": [["union", 0, 1], ["union", 1, 2], ["union", 3, 4], ["connected", 0, 4]],
             "expected": False},
            {"class": "DSU", "ctor_args": [3],
             "steps": [["union", 0, 1], ["union", 1, 2], ["connected", 0, 2]], "expected": True},
        ],
        "reference_solution": '''class DSU:
    def __init__(self, n):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1

    def connected(self, a, b):
        return self.find(a) == self.find(b)
''',
        "constraints": "find 路径压缩、union 按秩合并；均摊近 O(1)。",
    },
    {
        "task_id": "L3-011", "difficulty": "L3", "task_type": "业务逻辑",
        "description": (
            "实现类 RateLimiter，滑动窗口限流器。\n"
            "构造函数 __init__(self, capacity, window)：capacity 为窗口内允许的最大请求数（正整数），"
            "window 为窗口时长（正整数）。\n"
            "方法 allow(timestamp)：timestamp 为非负整数（单调非减的时刻）。"
            "若 [timestamp-window+1, timestamp] 这个窗口内已接受的请求数 < capacity，"
            "则接受本次请求并返回 True；否则拒绝并返回 False。\n"
            "示例：capacity=2, window=10 时，allow(1)、allow(2) 返回 True，allow(3) 返回 False。"
        ),
        "entry_point": "RateLimiter",
        "test_cases": [
            {"class": "RateLimiter", "ctor_args": [2, 10],
             "steps": [["allow", 1], ["allow", 2], ["allow", 3]], "expected": False},
            {"class": "RateLimiter", "ctor_args": [2, 10],
             "steps": [["allow", 1], ["allow", 2], ["allow", 11]], "expected": True},
            {"class": "RateLimiter", "ctor_args": [1, 5],
             "steps": [["allow", 1], ["allow", 2], ["allow", 6]], "expected": True},
            {"class": "RateLimiter", "ctor_args": [3, 100],
             "steps": [["allow", 1], ["allow", 50], ["allow", 99], ["allow", 100]],
             "expected": False},
            {"class": "RateLimiter", "ctor_args": [2, 1],
             "steps": [["allow", 5], ["allow", 5], ["allow", 6]], "expected": True},
        ],
        "reference_solution": '''class RateLimiter:
    def __init__(self, capacity, window):
        self.capacity = capacity
        self.window = window
        self._times = []

    def allow(self, timestamp):
        threshold = timestamp - self.window + 1
        while self._times and self._times[0] < threshold:
            self._times.pop(0)
        if len(self._times) < self.capacity:
            self._times.append(timestamp)
            return True
        return False
''',
        "constraints": "滑动窗口；窗口 [timestamp-window+1, timestamp]；超出 capacity 拒绝。",
    },
    {
        "task_id": "L3-012", "difficulty": "L3", "task_type": "重构优化",
        "description": (
            "下面这个积分计算函数用一长串 if/elif 硬编码会员等级与活动折扣，扩展新等级就要改判断链。"
            "请重构为「策略/配置表驱动」，函数签名保持 calc_points(amount, level)，行为完全等价：\n\n"
            "```python\n"
            "def calc_points(amount, level):\n"
            "    if level == 'bronze':\n"
            "        rate = 1\n"
            "    elif level == 'silver':\n"
            "        rate = 1.5\n"
            "    elif level == 'gold':\n"
            "        rate = 2\n"
            "    else:\n"
            "        rate = 0\n"
            "    return int(amount * rate)\n"
            "```\n\n"
            "规格：积分 = int(金额 × 倍率)；bronze=1、silver=1.5、gold=2；未知等级倍率为 0。"
            "要求：倍率写成模块级字典常量，函数体只查表。"
        ),
        "entry_point": "calc_points",
        "test_cases": [
            {"args": [100, "bronze"], "expected": 100},
            {"args": [100, "silver"], "expected": 150},
            {"args": [100, "gold"], "expected": 200},
            {"args": [100, "platinum"], "expected": 0},
            {"args": [0, "gold"], "expected": 0},
            {"args": [333, "silver"], "expected": 499},
        ],
        "reference_solution": '''RATES = {"bronze": 1, "silver": 1.5, "gold": 2}


def calc_points(amount, level):
    return int(amount * RATES.get(level, 0))
''',
        "constraints": "倍率写成模块级字典常量；未知等级返回 0；结果 int(金额×倍率)。",
    },
]


def main():
    ap = argparse.ArgumentParser(description="L2/L3 题目升级（v3 第二批）")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    with open(SRC_PATH, encoding="utf-8") as f:
        src = json.load(f)

    all_new = L2_NEW + L3_NEW
    ok, bad = [], []
    for task in all_new:
        errs = validate_task_schema(task) + validate_reference_passes(task)
        if errs:
            bad.append((task["task_id"], errs))
            print(f"❌ {task['task_id']}: {errs}")
        else:
            ok.append(task)
            print(f"✅ {task['task_id']} [{task['task_type']}] entry={task['entry_point']} "
                  f"用例={len(task['test_cases'])}")

    print(f"\n校验结果: {len(ok)}/{len(all_new)} 通过")
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
    meta["version"] = "v3-L1-L2-L3-upgraded"
    meta["built_at"] = __import__("datetime").datetime.now().isoformat(timespec="seconds")
    meta.setdefault("upgrade_log", []).append({
        "scope": "L2+L3",
        "reason": "L2 11 题 + L3 9 题功能分标准差=0，升级为性能敏感+边界密集+非平凡算法题",
        "editor": "DeepSeek-V4-Pro（对话内直接出题）",
        "task_ids": [t["task_id"] for t in ok],
    })
    payload = {"metadata": meta, "tasks": merged}
    tmp = OUT_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT_PATH)

    from collections import Counter
    print(f"\n已写入 {OUT_PATH}")
    print(f"题目总数: {len(merged)} | L1/L2/L3 已升级，L4 沿用 v2")
    print(f"分布: {dict(sorted(Counter(t['difficulty'] for t in merged).items()))}")


if __name__ == "__main__":
    main()

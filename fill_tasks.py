"""补齐 tasks_v2.json 的缺失题目（人工编辑：由 DeepSeek-V4-Pro 直接出题）。

用法:
    python fill_tasks.py --check     # 只做质量门校验，不写文件
    python fill_tasks.py             # 校验通过后合并写入 data/tasks/tasks_v2.json

质量门与自动构建器完全一致:
    1. schema 结构校验（字段/用例数/标准库白名单/语法）
    2. 参考实现必须通过自己的全部测试用例（沙箱实跑）
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_tasks import validate_reference_passes, validate_task_schema  # noqa: E402
from eval_kit.runner import load_tasks  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(ROOT, "data", "tasks", "tasks_v2.json")

TASKS = [
    # ==================== L3 ====================
    {
        "task_id": "L3-009",
        "difficulty": "L3",
        "task_type": "算法",
        "description": (
            "实现函数 max_profit_schedule(jobs)，求解加权区间调度：给定若干工作，"
            "每项工作用 [start, end, profit] 表示，占用半开区间 [start, end)，"
            "即该工作从 start 开始、在 end 结束，另一项工作只要其 start >= 前一项的 end 就不冲突。\n"
            "要求：选出一组互不冲突的工作，使总收益最大，返回最大总收益（整数）。\n"
            "输入 jobs 是列表，元素为长度为 3 的列表 [start, end, profit]，"
            "start/end 为非负整数且 start < end，profit 为正整数；jobs 可能为空，此时返回 0。\n"
            "示例：jobs=[[1,3,20],[2,5,30],[4,7,25],[6,9,40]] 时，"
            "选择 [2,5,30] 与 [6,9,40] 收益最大，返回 70。"
        ),
        "entry_point": "max_profit_schedule",
        "test_cases": [
            {"args": [[[1, 3, 20], [2, 5, 30], [4, 7, 25], [6, 9, 40]]], "expected": 70},
            {"args": [[[1, 2, 50], [1, 2, 60], [1, 3, 10]]], "expected": 60},
            {"args": [[]], "expected": 0},
            {"args": [[[1, 4, 10], [4, 7, 10], [7, 10, 10]]], "expected": 30},
            {"args": [[[3, 10, 20], [1, 3, 15], [10, 12, 5]]], "expected": 40},
            {"args": [[[5, 9, 100]]], "expected": 100},
        ],
        "reference_solution": '''import bisect


def max_profit_schedule(jobs):
    if not jobs:
        return 0
    ordered = sorted(jobs, key=lambda job: (job[1], job[0]))
    ends = [job[1] for job in ordered]
    dp = [0] * len(ordered)
    for i, job in enumerate(ordered):
        start, _end, profit = job[0], job[1], job[2]
        k = min(bisect.bisect_right(ends, start), i)
        best_prev = dp[k - 1] if k > 0 else 0
        take = best_prev + profit
        skip = dp[i - 1] if i > 0 else 0
        dp[i] = max(take, skip)
    return dp[-1]
''',
        "constraints": "时间复杂度 O(n log n)，n 为工作数量；不得使用全局变量缓存。",
    },
    {
        "task_id": "L3-010",
        "difficulty": "L3",
        "task_type": "调试修复",
        "description": (
            "下面这段代码的本意是：统计单词出现频次，返回出现次数最高的 k 个单词；"
            "排序规则为「频次降序，频次相同时按单词字典序升序」。但当前实现有 bug："
            "它用 set(words) 去重后仅按频次降序排序，没有处理频次相同的平局情况，"
            "而 set 的迭代顺序不稳定，导致频次相同时返回结果不确定。\n\n"
            "```python\n"
            "def top_k_frequent_words(words, k):\n"
            "    counts = {}\n"
            "    for w in words:\n"
            "        counts[w] = counts.get(w, 0) + 1\n"
            "    unique = list(set(words))\n"
            "    unique.sort(key=lambda w: -counts[w])\n"
            "    return unique[:k]\n"
            "```\n\n"
            "请修复该函数并提交完整实现。要求：返回值为字符串列表，长度为 min(k, 不同单词数)；"
            "排序必须完全确定——先按频次降序，频次相同按单词字典序升序；"
            "输入 words 可能为空列表，此时返回空列表。"
        ),
        "entry_point": "top_k_frequent_words",
        "test_cases": [
            {"args": [["apple", "banana", "apple", "cherry", "banana", "apple"], 2],
             "expected": ["apple", "banana"]},
            {"args": [["dog", "cat", "dog", "bird", "cat", "dog"], 3],
             "expected": ["dog", "cat", "bird"]},
            {"args": [["z", "a", "z", "a"], 2], "expected": ["a", "z"]},
            {"args": [["x"], 1], "expected": ["x"]},
            {"args": [["m", "m", "n", "o", "o", "o", "p"], 2], "expected": ["o", "m"]},
            {"args": [[], 3], "expected": []},
        ],
        "reference_solution": '''def top_k_frequent_words(words, k):
    counts = {}
    for w in words or []:
        counts[w] = counts.get(w, 0) + 1
    unique = sorted(counts.keys(), key=lambda w: (-counts[w], w))
    return unique[:k]
''',
        "constraints": "结果必须完全确定；不得依赖 set 的迭代顺序。",
    },
    {
        "task_id": "L3-011",
        "difficulty": "L3",
        "task_type": "业务逻辑",
        "description": (
            "实现类 WarehouseInventory，模拟仓库库存的「预留—确认—释放」三段式流程。\n"
            "构造函数 __init__(self, initial=None)：initial 是 {sku: 数量} 字典（可能为 None），"
            "表示各 SKU 的初始可用库存。\n"
            "方法：\n"
            "- reserve(sku, qty)：预留。若 qty <= 0 或可用库存不足则返回 False；"
            "否则可用库存减去 qty、预留量加上 qty，返回 True。\n"
            "- confirm(sku, qty)：确认出库。若 qty <= 0 或预留量不足则返回 False；"
            "否则预留量减去 qty（不改动可用库存），返回 True。\n"
            "- release(sku, qty)：取消预留。若 qty <= 0 或预留量不足则返回 False；"
            "否则预留量减去 qty、可用库存加回 qty，返回 True。\n"
            "- available(sku)：返回该 SKU 可用库存（不存在返回 0）。\n"
            "- reserved(sku)：返回该 SKU 预留量（不存在返回 0）。\n"
            "- total(sku)：返回 available + reserved。\n"
            "所有数量均为整数，初始化时应拷贝传入的字典，不得与调用方共享同一对象。"
        ),
        "entry_point": "WarehouseInventory",
        "test_cases": [
            {"class": "WarehouseInventory", "ctor_args": [{"A": 10}],
             "steps": [["reserve", "A", 4], ["available", "A"]], "expected": 6},
            {"class": "WarehouseInventory", "ctor_args": [{"A": 10, "B": 3}],
             "steps": [["reserve", "A", 7], ["reserve", "B", 5],
                       ["reserved", "A"], ["total", "A"]], "expected": 10},
            {"class": "WarehouseInventory", "ctor_args": [{"A": 10}],
             "steps": [["reserve", "A", 4], ["confirm", "A", 3],
                       ["available", "A"], ["reserved", "A"]], "expected": 1},
            {"class": "WarehouseInventory", "ctor_args": [{"A": 10}],
             "steps": [["reserve", "A", 6], ["release", "A", 2],
                       ["available", "A"]], "expected": 6},
            {"class": "WarehouseInventory", "ctor_args": [{}],
             "steps": [["available", "Z"]], "expected": 0},
            {"class": "WarehouseInventory", "ctor_args": [{"A": 2}],
             "steps": [["reserve", "A", 3], ["reserve", "A", 2],
                       ["available", "A"]], "expected": 0},
        ],
        "reference_solution": '''class WarehouseInventory:
    def __init__(self, initial=None):
        self._available = dict(initial or {})
        self._reserved = {}

    def reserve(self, sku, qty):
        if qty <= 0 or self._available.get(sku, 0) < qty:
            return False
        self._available[sku] = self._available.get(sku, 0) - qty
        self._reserved[sku] = self._reserved.get(sku, 0) + qty
        return True

    def confirm(self, sku, qty):
        if qty <= 0 or self._reserved.get(sku, 0) < qty:
            return False
        self._reserved[sku] -= qty
        return True

    def release(self, sku, qty):
        if qty <= 0 or self._reserved.get(sku, 0) < qty:
            return False
        self._reserved[sku] -= qty
        self._available[sku] = self._available.get(sku, 0) + qty
        return True

    def available(self, sku):
        return self._available.get(sku, 0)

    def reserved(self, sku):
        return self._reserved.get(sku, 0)

    def total(self, sku):
        return self._available.get(sku, 0) + self._reserved.get(sku, 0)
''',
        "constraints": "数量均为 int；不得让内部状态与传入的 initial 字典产生别名共享。",
    },
    {
        "task_id": "L3-012",
        "difficulty": "L3",
        "task_type": "重构优化",
        "description": (
            "下面这段运费计算函数存在重复的分支嵌套、魔法数字散落、且未对重量向上取整"
            "导致金额偏小。请重构它，函数签名保持为 "
            "compute_shipping_fee(weight_kg, distance_km, is_express)，并严格实现下列规格：\n\n"
            "```python\n"
            "def compute_shipping_fee(weight_kg, distance_km, is_express):\n"
            "    total = 8\n"
            "    if weight_kg > 1:\n"
            "        if weight_kg <= 5:\n"
            "            total = total + weight_kg * 2\n"
            "        else:\n"
            "            total = total + weight_kg * 3\n"
            "    if distance_km > 100:\n"
            "        if distance_km <= 500:\n"
            "            total = total + 6\n"
            "        else:\n"
            "            total = total + 15\n"
            "    if is_express == True:\n"
            "        total = total * 1.5\n"
            "    return total\n"
            "```\n\n"
            "规格：\n"
            "1. 基础费 8 元；\n"
            "2. 计费重量 = math.ceil(weight_kg)，即向上取整到整千克；\n"
            "3. 重量费：计费重量 <= 1 时为 0；2~5（含）时 = 计费重量 × 2；大于 5 时 = 计费重量 × 3；\n"
            "4. 距离费：distance_km <= 100 时为 0；101~500（含）时为 6；大于 500 时为 15；\n"
            "5. 若 is_express 为 True，最终金额 = (基础费 + 重量费 + 距离费) × 1.5；\n"
            "6. 返回 float，用 round(total, 2) 保留两位小数；\n"
            "7. 若 weight_kg 或 distance_km 为负数，抛出 ValueError。"
        ),
        "entry_point": "compute_shipping_fee",
        "test_cases": [
            {"args": [0.5, 50, False], "expected": 8.0},
            {"args": [3.2, 200, False], "expected": 22.0},
            {"args": [7, 600, True], "expected": 66.0},
            {"args": [1, 100, False], "expected": 8.0},
            {"args": [5, 500, False], "expected": 24.0},
            {"args": [6.1, 501, False], "expected": 44.0},
        ],
        "reference_solution": '''import math

BASE_FEE = 8.0
LIGHT_MAX = 1           # 计费重量 <= 1 不收重量费
MID_MAX = 5             # 计费重量 2~5 的费率区间
MID_RATE = 2.0
HEAVY_RATE = 3.0
NEAR_MAX = 100          # 距离 <= 100 不收距离费
MID_DISTANCE_MAX = 500
MID_DISTANCE_FEE = 6.0
FAR_DISTANCE_FEE = 15.0
EXPRESS_FACTOR = 1.5


def compute_shipping_fee(weight_kg, distance_km, is_express):
    if weight_kg < 0 or distance_km < 0:
        raise ValueError("weight and distance must be non-negative")
    billable = math.ceil(weight_kg)
    if billable <= LIGHT_MAX:
        weight_fee = 0.0
    elif billable <= MID_MAX:
        weight_fee = billable * MID_RATE
    else:
        weight_fee = billable * HEAVY_RATE
    if distance_km <= NEAR_MAX:
        distance_fee = 0.0
    elif distance_km <= MID_DISTANCE_MAX:
        distance_fee = MID_DISTANCE_FEE
    else:
        distance_fee = FAR_DISTANCE_FEE
    total = BASE_FEE + weight_fee + distance_fee
    if is_express:
        total *= EXPRESS_FACTOR
    return round(total, 2)
''',
        "constraints": "必须消除重复分支并保留完全一致的计费结果；返回 float 且保留两位小数。",
    },

    # ==================== L4 ====================
    {
        "task_id": "L4-001",
        "difficulty": "L4",
        "task_type": "算法",
        "description": (
            "实现函数 network_throughput(n, pipes, source, sink)，计算有向网络的最大流。\n"
            "参数：n 为节点数（编号 0 ~ n-1）；pipes 为有向管道列表，元素形如 [u, v, capacity]，"
            "表示从 u 到 v 的管道最多可通过 capacity 单位流量（capacity 为非负整数，"
            "同一对节点可能出现多次，视为多条并行管道，容量叠加）；source 为源点编号，sink 为汇点编号。\n"
            "返回从 source 到 sink 的最大可输送总流量（整数）。若 source == sink 返回 0。\n"
            "要求使用 Dinic 算法（BFS 分层 + DFS 阻塞流增广），保证在 n <= 200、管道数 <= 2000 时快速完成。\n"
            "示例：n=4, pipes=[[0,1,3],[0,2,2],[1,2,1],[1,3,2],[2,3,4]], source=0, sink=3 时返回 5。"
        ),
        "entry_point": "network_throughput",
        "test_cases": [
            {"args": [4, [[0, 1, 3], [0, 2, 2], [1, 2, 1], [1, 3, 2], [2, 3, 4]], 0, 3],
             "expected": 5},
            {"args": [2, [[0, 1, 7]], 0, 1], "expected": 7},
            {"args": [3, [], 0, 2], "expected": 0},
            {"args": [6, [[0, 1, 10], [0, 2, 10], [1, 3, 5], [1, 2, 2], [2, 4, 10],
                          [3, 5, 10], [4, 5, 10], [3, 4, 5]], 0, 5], "expected": 15},
            {"args": [4, [[0, 1, 5], [1, 2, 5], [2, 3, 5], [0, 3, 1]], 0, 3], "expected": 6},
        ],
        "reference_solution": '''from collections import deque


class _Edge:
    __slots__ = ("to", "cap", "rev")

    def __init__(self, to, cap, rev):
        self.to = to
        self.cap = cap
        self.rev = rev


def network_throughput(n, pipes, source, sink):
    if source == sink:
        return 0
    graph = [[] for _ in range(n)]
    for u, v, cap in pipes or []:
        graph[u].append(_Edge(v, cap, len(graph[v])))
        graph[v].append(_Edge(u, 0, len(graph[u]) - 1))

    flow = 0
    while True:
        level = [-1] * n
        level[source] = 0
        queue = deque([source])
        while queue:
            u = queue.popleft()
            for edge in graph[u]:
                if edge.cap > 0 and level[edge.to] < 0:
                    level[edge.to] = level[u] + 1
                    queue.append(edge.to)
        if level[sink] < 0:
            return flow
        it = [0] * n

        def dfs(u, pushed):
            if u == sink:
                return pushed
            while it[u] < len(graph[u]):
                edge = graph[u][it[u]]
                if edge.cap > 0 and level[edge.to] == level[u] + 1:
                    delta = dfs(edge.to, min(pushed, edge.cap))
                    if delta > 0:
                        edge.cap -= delta
                        graph[edge.to][edge.rev].cap += delta
                        return delta
                it[u] += 1
            return 0

        while True:
            pushed = dfs(source, float("inf"))
            if pushed == 0:
                break
            flow += pushed
    return flow
''',
        "constraints": "必须使用 Dinic（BFS 分层 + DFS 阻塞流）；不得使用第三方库。",
    },
    {
        "task_id": "L4-002",
        "difficulty": "L4",
        "task_type": "功能实现",
        "description": (
            "实现函数 render_template(template: str, context: dict) -> str，"
            "实现一个最小模板引擎，支持变量与两种控制标签。\n\n"
            "语法与语义：\n"
            "1. 变量 {{ path }}：从 context 中按点号路径取值，如 {{ user.name }} "
            "等价于 context['user']['name']；若路径中任一层不存在，替换为空字符串。\n"
            "2. 条件 {% if key %}...{% else %}...{% endif %}：key 为 context 中的键名，"
            "按 Python 真值判断；{% else %} 可省略。\n"
            "3. 循环 {% for item in items %}...{% endfor %}：items 为 context 中的列表键名，"
            "循环体内可将 item 作为变量名取值（如 {{ item }}）。循环体中若引用列表元素为字典，"
            "可用 {{ item.field }} 取值。\n"
            "4. 标签与变量之外的所有字符原样输出（包括空格与换行），引擎不做任何空白吞并；"
            "标签自身不产生输出。\n"
            "5. 取到的值统一用 str() 转为字符串后拼接。\n\n"
            "示例：render_template('Hello, {{ name }}!', {'name': 'Alice'}) 返回 'Hello, Alice!'。"
        ),
        "entry_point": "render_template",
        "test_cases": [
            {"args": ["Hello, {{ name }}!", {"name": "Alice"}], "expected": "Hello, Alice!"},
            {"args": ["{% if flag %}yes{% else %}no{% endif %}", {"flag": True}], "expected": "yes"},
            {"args": ["{% if flag %}yes{% else %}no{% endif %}", {"flag": False}], "expected": "no"},
            {"args": ["{% for x in nums %}[{{ x }}]{% endfor %}", {"nums": [1, 2, 3]}],
             "expected": "[1][2][3]"},
            {"args": ["{{ a.b.c }}", {"a": {"b": {"c": 42}}}], "expected": "42"},
            {"args": ["{{ missing }}|end", {}], "expected": "|end"},
        ],
        "reference_solution": '''import re

_TOKEN = re.compile(r"\\{\\{(.*?)\\}\\}|\\{%(.*?)%\\}")


def _lookup(context, path):
    cur = context
    for part in str(path).strip().split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _split_block(nodes, start, open_kw, close_kw, else_kw="else"):
    depth = 0
    body, else_body = [], []
    in_else = False
    j = start + 1
    while j < len(nodes):
        kind, text = nodes[j]
        if kind == "tag":
            parts = text.strip().split()
            kw = parts[0] if parts else ""
            if kw in (open_kw, "for", "if"):
                depth += 1
            elif kw == close_kw:
                if depth == 0:
                    return body, (else_body if in_else else None), j + 1
                depth -= 1
            elif kw == else_kw and depth == 0:
                in_else = True
                j += 1
                continue
        (else_body if in_else else body).append(nodes[j])
        j += 1
    return body, None, j


def _render(nodes, context, out):
    i = 0
    while i < len(nodes):
        kind, text = nodes[i]
        if kind == "text":
            out.append(text)
            i += 1
        elif kind == "var":
            val = _lookup(context, text)
            out.append("" if val is None else str(val))
            i += 1
        else:
            parts = text.strip().split()
            kw = parts[0] if parts else ""
            if kw == "if":
                body, else_body, nxt = _split_block(nodes, i, "if", "endif")
                if _lookup(context, parts[1]):
                    _render(body, context, out)
                elif else_body:
                    _render(else_body, context, out)
                i = nxt
            elif kw == "for":
                body, _else, nxt = _split_block(nodes, i, "for", "endfor")
                for item in (_lookup(context, parts[3]) or []):
                    local = dict(context)
                    local[parts[1]] = item
                    _render(body, local, out)
                i = nxt
            else:
                i += 1
    return out


def render_template(template, context):
    nodes, pos = [], 0
    for m in _TOKEN.finditer(template or ""):
        if m.start() > pos:
            nodes.append(("text", template[pos:m.start()]))
        if m.group(1) is not None:
            nodes.append(("var", m.group(1).strip()))
        else:
            nodes.append(("tag", m.group(2).strip()))
        pos = m.end()
    if pos < len(template or ""):
        nodes.append(("text", template[pos:]))
    return "".join(_render(nodes, context or {}, []))
''',
        "constraints": "仅使用标准库；标签不做空白吞并；缺失路径替换为空字符串。",
    },
    {
        "task_id": "L4-003",
        "difficulty": "L4",
        "task_type": "调试修复",
        "description": (
            "下面这段代码实现了一个 LRU（最近最少使用）缓存，但存在两处 bug：\n"
            "① get 命中后没有把该键移到末尾，导致「最近使用」记录不正确；\n"
            "② put 在容量已满时直接丢弃新键，而不是插入后淘汰最久未使用的键。\n\n"
            "```python\n"
            "from collections import OrderedDict\n"
            "\n"
            "class LRUCache:\n"
            "    def __init__(self, capacity):\n"
            "        self.capacity = capacity\n"
            "        self._data = OrderedDict()\n"
            "\n"
            "    def get(self, key):\n"
            "        if key not in self._data:\n"
            "            return -1\n"
            "        return self._data[key]\n"
            "\n"
            "    def put(self, key, value):\n"
            "        if key in self._data:\n"
            "            self._data[key] = value\n"
            "            return\n"
            "        if len(self._data) < self.capacity:\n"
            "            self._data[key] = value\n"
            "```\n\n"
            "请修复后提交完整类实现。行为约定：\n"
            "- get(key)：存在则返回对应值并将该键标记为最近使用；不存在返回 -1。\n"
            "- put(key, value)：键已存在则更新值并标记为最近使用；否则插入新键，"
            "若插入后条目数超过 capacity，则删除最久未使用的键。\n"
            "- 构造函数 capacity <= 0 时抛出 ValueError。\n"
            "键可以是任意可哈希值，值为整数。"
        ),
        "entry_point": "LRUCache",
        "test_cases": [
            {"class": "LRUCache", "ctor_args": [2],
             "steps": [["put", 1, 10], ["put", 2, 20], ["get", 1]], "expected": 10},
            {"class": "LRUCache", "ctor_args": [2],
             "steps": [["put", 1, 10], ["put", 2, 20], ["put", 3, 30], ["get", 1]],
             "expected": -1},
            {"class": "LRUCache", "ctor_args": [2],
             "steps": [["put", 1, 10], ["put", 2, 20], ["get", 1], ["put", 3, 30],
                       ["get", 2]], "expected": -1},
            {"class": "LRUCache", "ctor_args": [2],
             "steps": [["put", 1, 10], ["put", 2, 20], ["get", 1], ["put", 3, 30],
                       ["get", 1]], "expected": 10},
            {"class": "LRUCache", "ctor_args": [1],
             "steps": [["put", 1, 10], ["put", 1, 99], ["get", 1]], "expected": 99},
            {"class": "LRUCache", "ctor_args": [3],
             "steps": [["put", "a", 1], ["put", "b", 2], ["put", "c", 3], ["put", "d", 4],
                       ["get", "a"]], "expected": -1},
        ],
        "reference_solution": '''from collections import OrderedDict


class LRUCache:
    def __init__(self, capacity):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self._data = OrderedDict()

    def get(self, key):
        if key not in self._data:
            return -1
        self._data.move_to_end(key)
        return self._data[key]

    def put(self, key, value):
        if key in self._data:
            self._data[key] = value
            self._data.move_to_end(key)
            return
        self._data[key] = value
        if len(self._data) > self.capacity:
            self._data.popitem(last=False)
''',
        "constraints": "get/put 平均时间复杂度 O(1)；不得使用 functools.lru_cache 直接代劳。",
    },
    {
        "task_id": "L4-004",
        "difficulty": "L4",
        "task_type": "算法",
        "description": (
            "实现函数 shortest_path_with_breaks(grid, max_breaks)。\n"
            "grid 是二维 0/1 列表，0 表示可通行空地，1 表示墙壁；"
            "从左上角 (0,0) 出发走到右下角 (m-1, n-1)，每步只能上下左右移动一格。\n"
            "允许穿墙，但整个路径上最多只能穿过 max_breaks 面墙（max_breaks 为非负整数）。\n"
            "返回最短路径的步数（进入的每个格子都算一步，起点不计）；若无法到达则返回 -1。\n"
            "grid 保证非空且每行长度相同。\n"
            "示例：grid=[[0,0,0],[1,1,0],[0,0,0]], max_breaks=1 时，"
            "路径 (0,0)→(0,1)→(0,2)→(1,2)→(2,2) 共 4 步，返回 4。"
        ),
        "entry_point": "shortest_path_with_breaks",
        "test_cases": [
            {"args": [[[0, 0, 0], [1, 1, 0], [0, 0, 0]], 1], "expected": 4},
            {"args": [[[0, 1], [1, 0]], 1], "expected": 2},
            {"args": [[[0, 1], [1, 0]], 0], "expected": -1},
            {"args": [[[0]], 0], "expected": 0},
            {"args": [[[0, 0], [0, 0]], 0], "expected": 2},
        ],
        "reference_solution": '''from collections import deque


def shortest_path_with_breaks(grid, max_breaks):
    if not grid or not grid[0]:
        return -1
    rows, cols = len(grid), len(grid[0])
    if max_breaks < 0:
        return -1
    best = {}
    queue = deque()
    best[(0, 0)] = 0
    queue.append((0, 0, 0, 0))
    while queue:
        r, c, used, steps = queue.popleft()
        if r == rows - 1 and c == cols - 1:
            return steps
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if not (0 <= nr < rows and 0 <= nc < cols):
                continue
            nu = used + grid[nr][nc]
            if nu > max_breaks:
                continue
            key = (nr, nc)
            if key in best and best[key] <= nu:
                continue
            best[key] = nu
            queue.append((nr, nc, nu, steps + 1))
    return -1
''',
        "constraints": "时间复杂度 O(rows × cols × max_breaks)；使用 BFS，不得使用递归回溯。",
    },
    {
        "task_id": "L4-005",
        "difficulty": "L4",
        "task_type": "重构优化",
        "description": (
            "下面这个问卷统计函数由一堆重复的 if/elif 与散落的变量拼成，"
            "可读性与可扩展性都很差。请重构它，函数签名保持为 analyze_survey(responses)。\n\n"
            "```python\n"
            "def analyze_survey(responses):\n"
            "    c1 = 0\n"
            "    c2 = 0\n"
            "    c3 = 0\n"
            "    c4 = 0\n"
            "    c5 = 0\n"
            "    missing = 0\n"
            "    total = 0\n"
            "    for r in responses:\n"
            "        if r == 1:\n"
            "            c1 = c1 + 1\n"
            "            total = total + 1\n"
            "        elif r == 2:\n"
            "            c2 = c2 + 1\n"
            "            total = total + 2\n"
            "        elif r == 3:\n"
            "            c3 = c3 + 1\n"
            "            total = total + 3\n"
            "        elif r == 4:\n"
            "            c4 = c4 + 1\n"
            "            total = total + 4\n"
            "        elif r == 5:\n"
            "            c5 = c5 + 1\n"
            "            total = total + 5\n"
            "        else:\n"
            "            missing = missing + 1\n"
            "    count = c1 + c2 + c3 + c4 + c5\n"
            "    if count > 0:\n"
            "        average = round(total / count, 2)\n"
            "    else:\n"
            "        average = 0.0\n"
            "    result = {}\n"
            "    result['count'] = count\n"
            "    result['average'] = average\n"
            "    result['missing'] = missing\n"
            "    result['distribution'] = {'1': c1, '2': c2, '3': c3, '4': c4, '5': c5}\n"
            "    return result\n"
            "```\n\n"
            "规格（重构后必须完全满足）：\n"
            "- 输入 responses 为列表，元素为 1~5 的整数或 None（None 表示缺答），也可能为 None 本身；\n"
            "- 返回 dict，含四个键：'count'（有效答卷数 int）、'average'（平均分 float，"
            "round(total/count, 2)，无有效答卷时为 0.0）、'distribution'（dict，键为字符串 "
            "'1'~'5'，值为对应分数出现次数 int，必须为全部 5 个键）、'missing'（缺答数 int）；\n"
            "- 不在 1~5 范围内的非 None 元素既不计入有效答卷，也不计入缺答。"
        ),
        "entry_point": "analyze_survey",
        "test_cases": [
            {"args": [[5, 4, 3, None]],
             "expected": {"count": 3, "average": 4.0,
                          "distribution": {"1": 0, "2": 0, "3": 1, "4": 1, "5": 1},
                          "missing": 1}},
            {"args": [[]],
             "expected": {"count": 0, "average": 0.0,
                          "distribution": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
                          "missing": 0}},
            {"args": [[None, None]],
             "expected": {"count": 0, "average": 0.0,
                          "distribution": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
                          "missing": 2}},
            {"args": [[1, 1, 2]],
             "expected": {"count": 3, "average": 1.33,
                          "distribution": {"1": 2, "2": 1, "3": 0, "4": 0, "5": 0},
                          "missing": 0}},
            {"args": [[3, 3, 3, 3]],
             "expected": {"count": 4, "average": 3.0,
                          "distribution": {"1": 0, "2": 0, "3": 4, "4": 0, "5": 0},
                          "missing": 0}},
            {"args": [[5, None, 5, None, 5]],
             "expected": {"count": 3, "average": 5.0,
                          "distribution": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 3},
                          "missing": 2}},
        ],
        "reference_solution": '''VALID_SCORES = (1, 2, 3, 4, 5)


def analyze_survey(responses):
    distribution = {str(score): 0 for score in VALID_SCORES}
    total = 0
    count = 0
    missing = 0
    for value in responses or []:
        if value is None:
            missing += 1
            continue
        key = str(value)
        if key not in distribution:
            continue
        distribution[key] += 1
        total += value
        count += 1
    average = round(total / count, 2) if count else 0.0
    return {
        "count": count,
        "average": average,
        "distribution": distribution,
        "missing": missing,
    }
''',
        "constraints": "必须消除重复的 if/elif 链；返回 dict 结构固定，distribution 必须包含 '1'~'5' 全部键。",
    },
    {
        "task_id": "L4-006",
        "difficulty": "L4",
        "task_type": "功能实现",
        "description": (
            "实现类 TextBuffer，一个支持撤销/重做的简易文本缓冲区。\n"
            "构造函数 __init__(self, text=\"\")：初始文本为 text。\n"
            "方法：\n"
            "- insert(pos, s)：在下标 pos 处插入字符串 s，返回插入后的完整文本；"
            "pos 越界（pos < 0 或 pos > 当前长度）时抛出 IndexError。\n"
            "- delete(pos, length)：删除从下标 pos 开始的 length 个字符，"
            "返回被删除的字符串；范围越界时抛出 IndexError。\n"
            "- undo()：撤销最近一次 insert/delete，返回撤销后的完整文本；"
            "无历史可撤销时不做任何改动，直接返回当前文本。\n"
            "- redo()：恢复最近一次被撤销的操作，返回恢复后的完整文本；"
            "无可重做时直接返回当前文本。\n"
            "- get_text()：返回当前完整文本。\n"
            "额外约定：执行新的 insert 或 delete 后，redo 历史必须被清空。"
        ),
        "entry_point": "TextBuffer",
        "test_cases": [
            {"class": "TextBuffer", "ctor_args": ["hello"],
             "steps": [["insert", 5, " world"], ["get_text"]], "expected": "hello world"},
            {"class": "TextBuffer", "ctor_args": ["hello"],
             "steps": [["delete", 1, 3], ["get_text"]], "expected": "ho"},
            {"class": "TextBuffer", "ctor_args": ["hello"],
             "steps": [["insert", 5, " world"], ["undo"], ["get_text"]], "expected": "hello"},
            {"class": "TextBuffer", "ctor_args": ["hello"],
             "steps": [["insert", 5, " world"], ["undo"], ["redo"], ["get_text"]],
             "expected": "hello world"},
            {"class": "TextBuffer", "ctor_args": ["hello"],
             "steps": [["insert", 5, "!"], ["insert", 6, "?"], ["undo"], ["undo"],
                       ["get_text"]], "expected": "hello"},
            {"class": "TextBuffer", "ctor_args": ["abc"],
             "steps": [["undo"], ["get_text"]], "expected": "abc"},
        ],
        "reference_solution": '''class TextBuffer:
    def __init__(self, text=""):
        self._text = text
        self._undo_stack = []
        self._redo_stack = []

    def insert(self, pos, s):
        if pos < 0 or pos > len(self._text):
            raise IndexError("insert position out of range")
        self._undo_stack.append(self._text)
        self._redo_stack.clear()
        self._text = self._text[:pos] + s + self._text[pos:]
        return self._text

    def delete(self, pos, length):
        if pos < 0 or length < 0 or pos + length > len(self._text):
            raise IndexError("delete range out of range")
        removed = self._text[pos:pos + length]
        self._undo_stack.append(self._text)
        self._redo_stack.clear()
        self._text = self._text[:pos] + self._text[pos + length:]
        return removed

    def undo(self):
        if not self._undo_stack:
            return self._text
        self._redo_stack.append(self._text)
        self._text = self._undo_stack.pop()
        return self._text

    def redo(self):
        if not self._redo_stack:
            return self._text
        self._undo_stack.append(self._text)
        self._text = self._redo_stack.pop()
        return self._text

    def get_text(self):
        return self._text
''',
        "constraints": "undo/redo 语义须与常见编辑器一致；新增操作后清空 redo 栈。",
    },
    {
        "task_id": "L4-007",
        "difficulty": "L4",
        "task_type": "算法",
        "description": (
            "实现函数 max_submatrix_sum(matrix)，求一个整数矩阵中「元素和最大的连续子矩阵」的和。\n"
            "连续子矩阵指行、列均连续的一块矩形区域，至少包含一个元素。\n"
            "输入 matrix 为二维整数列表（可能含负数），行等长；若 matrix 为空或首行为空则返回 0。\n"
            "返回该最大和（整数）。\n"
            "要求：时间复杂度 O(rows^2 × cols)（枚举上下边界 + 一维最大子段和），"
            "不得使用 O(rows^2 × cols^2) 的暴力枚举。\n"
            "示例：matrix=[[1,2,-1],[-3,4,5],[2,-1,3]] 时返回 12"
            "（取第 1~2 列、全部 3 行）。"
        ),
        "entry_point": "max_submatrix_sum",
        "test_cases": [
            {"args": [[[1, 2, -1], [-3, 4, 5], [2, -1, 3]]], "expected": 12},
            {"args": [[[-5]]], "expected": -5},
            {"args": [[]], "expected": 0},
            {"args": [[[1, 2], [3, 4]]], "expected": 10},
            {"args": [[[-1, -2], [-3, -4]]], "expected": -1},
            {"args": [[[2, -1, 2], [1, -3, 4]]], "expected": 6},
        ],
        "reference_solution": '''def max_submatrix_sum(matrix):
    if not matrix or not matrix[0]:
        return 0
    rows, cols = len(matrix), len(matrix[0])
    best = None
    for top in range(rows):
        col_sums = [0] * cols
        for bottom in range(top, rows):
            for c in range(cols):
                col_sums[c] += matrix[bottom][c]
            cur = col_sums[0]
            local = col_sums[0]
            for c in range(1, cols):
                cur = max(col_sums[c], cur + col_sums[c])
                local = max(local, cur)
            if best is None or local > best:
                best = local
    return best
''',
        "constraints": "时间复杂度 O(rows^2 × cols)；禁止暴力枚举所有子矩阵。",
    },
    {
        "task_id": "L4-008",
        "difficulty": "L4",
        "task_type": "业务逻辑",
        "description": (
            "实现类 Ledger，一个支持幂等记账的交易台账（金额单位统一为「分」的整数）。\n"
            "构造函数 __init__(self)：无参数，创建空台账。\n"
            "方法：\n"
            "- charge(txn_id, amount)：记账。若 txn_id 已存在则返回字符串 'DUPLICATE'；"
            "若 amount 不是 int 或 amount <= 0 则返回 'INVALID'；否则记录该笔交易并返回 'OK'。\n"
            "- refund(txn_id)：退款。若 txn_id 不存在返回 'NOT_FOUND'；"
            "若该交易已退款返回 'DUPLICATE'；否则标记为已退款并返回 'OK'。\n"
            "- balance()：返回所有「未退款」交易的金额之和（int）。\n"
            "- count()：返回「未退款」交易的笔数（int）。\n"
            "约定：同一 txn_id 重复 charge 时不得重复计入余额；退款后再 charge 同一 txn_id 仍返回 DUPLICATE。"
        ),
        "entry_point": "Ledger",
        "test_cases": [
            {"class": "Ledger", "ctor_args": [],
             "steps": [["charge", "t1", 1000], ["balance"]], "expected": 1000},
            {"class": "Ledger", "ctor_args": [],
             "steps": [["charge", "t1", 1000], ["charge", "t1", 1000], ["balance"]],
             "expected": 1000},
            {"class": "Ledger", "ctor_args": [],
             "steps": [["charge", "t1", 1000], ["refund", "t1"], ["balance"]], "expected": 0},
            {"class": "Ledger", "ctor_args": [],
             "steps": [["refund", "zz"], ["balance"]], "expected": 0},
            {"class": "Ledger", "ctor_args": [],
             "steps": [["charge", "t1", 1000], ["charge", "t2", 500], ["refund", "t1"],
                       ["balance"]], "expected": 500},
            {"class": "Ledger", "ctor_args": [],
             "steps": [["charge", "t1", 0], ["count"]], "expected": 0},
        ],
        "reference_solution": '''class Ledger:
    def __init__(self):
        self._txns = {}

    def charge(self, txn_id, amount):
        if txn_id in self._txns:
            return "DUPLICATE"
        if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
            return "INVALID"
        self._txns[txn_id] = {"amount": int(amount), "refunded": False}
        return "OK"

    def refund(self, txn_id):
        txn = self._txns.get(txn_id)
        if txn is None:
            return "NOT_FOUND"
        if txn["refunded"]:
            return "DUPLICATE"
        txn["refunded"] = True
        return "OK"

    def balance(self):
        return sum(t["amount"] for t in self._txns.values() if not t["refunded"])

    def count(self):
        return sum(1 for t in self._txns.values() if not t["refunded"])
''',
        "constraints": "金额均为 int（分）；退款为幂等操作；balance/count 只统计未退款交易。",
    },
    {
        "task_id": "L4-009",
        "difficulty": "L4",
        "task_type": "重构优化",
        "description": (
            "下面这个订单状态机函数用层层 if/elif 硬编码状态转移，新增状态就要改动判断链，"
            "可维护性差。请重构为「状态转移表驱动」的实现，函数签名保持为 "
            "handle_order_event(state, event)。\n\n"
            "```python\n"
            "def handle_order_event(state, event):\n"
            "    if state == 'PENDING':\n"
            "        if event == 'PAY':\n"
            "            return 'PAID'\n"
            "        elif event == 'CANCEL':\n"
            "            return 'CANCELLED'\n"
            "        else:\n"
            "            return 'INVALID'\n"
            "    elif state == 'PAID':\n"
            "        if event == 'SHIP':\n"
            "            return 'SHIPPED'\n"
            "        elif event == 'CANCEL':\n"
            "            return 'CANCELLED'\n"
            "        else:\n"
            "            return 'INVALID'\n"
            "    elif state == 'SHIPPED':\n"
            "        if event == 'DELIVER':\n"
            "            return 'DELIVERED'\n"
            "        else:\n"
            "            return 'INVALID'\n"
            "    else:\n"
            "        return 'INVALID'\n"
            "```\n\n"
            "转移规则（重构后须完全等价）：\n"
            "PENDING + PAY → PAID；PENDING + CANCEL → CANCELLED；\n"
            "PAID + SHIP → SHIPPED；PAID + CANCEL → CANCELLED；\n"
            "SHIPPED + DELIVER → DELIVERED；\n"
            "其余所有 (state, event) 组合（含 DELIVERED、CANCELLED 出发的任意事件）返回 'INVALID'。\n"
            "要求：把转移规则集中写成一个模块级 dict 常量，函数体只做查表。"
        ),
        "entry_point": "handle_order_event",
        "test_cases": [
            {"args": ["PENDING", "PAY"], "expected": "PAID"},
            {"args": ["PENDING", "CANCEL"], "expected": "CANCELLED"},
            {"args": ["PAID", "SHIP"], "expected": "SHIPPED"},
            {"args": ["SHIPPED", "DELIVER"], "expected": "DELIVERED"},
            {"args": ["DELIVERED", "CANCEL"], "expected": "INVALID"},
            {"args": ["CANCELLED", "PAY"], "expected": "INVALID"},
        ],
        "reference_solution": '''INVALID = "INVALID"

ORDER_TRANSITIONS = {
    ("PENDING", "PAY"): "PAID",
    ("PENDING", "CANCEL"): "CANCELLED",
    ("PAID", "SHIP"): "SHIPPED",
    ("PAID", "CANCEL"): "CANCELLED",
    ("SHIPPED", "DELIVER"): "DELIVERED",
}


def handle_order_event(state, event):
    return ORDER_TRANSITIONS.get((state, event), INVALID)
''',
        "constraints": "转移规则必须以模块级常量字典表达；函数不得出现状态名的字符串比较。",
    },
    {
        "task_id": "L4-010",
        "difficulty": "L4",
        "task_type": "调试修复",
        "description": (
            "下面这段代码实现「项目构建顺序」求解（拓扑排序），但存在一个 bug："
            "当依赖图中存在环时，它不会报告环，而是静默返回一个只含部分项目的列表，"
            "调用方无法区分「正常完成」与「存在循环依赖」。\n\n"
            "```python\n"
            "def build_order(projects, deps):\n"
            "    graph = {}\n"
            "    indeg = {}\n"
            "    for p in projects:\n"
            "        graph[p] = []\n"
            "        indeg[p] = 0\n"
            "    for a, b in deps:\n"
            "        graph[b].append(a)\n"
            "        indeg[a] += 1\n"
            "    ready = []\n"
            "    for p in projects:\n"
            "        if indeg[p] == 0:\n"
            "            ready.append(p)\n"
            "    order = []\n"
            "    while len(ready) > 0:\n"
            "        ready.sort()\n"
            "        cur = ready.pop(0)\n"
            "        order.append(cur)\n"
            "        for nxt in graph[cur]:\n"
            "            indeg[nxt] -= 1\n"
            "            if indeg[nxt] == 0:\n"
            "                ready.append(nxt)\n"
            "    return order\n"
            "```\n\n"
            "请修复后提交完整实现。约定：\n"
            "- 参数 projects 为项目名字符串列表（无重复）；\n"
            "- 参数 deps 为 [a, b] 列表，表示 a 依赖 b，因此 b 必须排在 a 之前；"
            "deps 可能为 None；\n"
            "- 返回满足全部依赖的一个合法顺序（字符串列表）；"
            "当多个项目同时可执行时，取字典序最小者，以保证结果唯一；\n"
            "- 若存在循环依赖（无法排完所有项目），返回 [\"CYCLE\"]。"
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


def build_order(projects, deps):
    projects = list(projects or [])
    graph = {p: [] for p in projects}
    indeg = {p: 0 for p in projects}
    for a, b in (deps or []):
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
    if len(order) != len(projects):
        return ["CYCLE"]
    return order
''',
        "constraints": "结果必须唯一确定（同级按字典序最小）；存在环时必须返回 [\"CYCLE\"]。",
    },
    {
        "task_id": "L4-011",
        "difficulty": "L4",
        "task_type": "算法",
        "description": (
            "实现函数 min_wiring_cost(n, links)，求解「机房布线最小成本」："
            "把 n 个机柜（编号 0 ~ n-1）全部连通所需的最小布线总成本。\n"
            "参数 links 为候选线路列表，元素形如 [u, v, w]，表示在机柜 u 与 v 之间布线的成本为 w"
            "（u、v 为有效机柜编号，w 为非负整数；线路为无向）。\n"
            "返回最小总成本（整数）；若无法使所有机柜连通则返回 -1。n <= 1 时返回 0。\n"
            "要求使用 Kruskal 算法（并查集 + 按权值升序排序），"
            "并在已选边数达到 n-1 时提前结束。\n"
            "示例：n=4, links=[[0,1,1],[1,2,2],[2,3,3],[0,3,4],[1,3,5]] 时返回 6。"
        ),
        "entry_point": "min_wiring_cost",
        "test_cases": [
            {"args": [4, [[0, 1, 1], [1, 2, 2], [2, 3, 3], [0, 3, 4], [1, 3, 5]]],
             "expected": 6},
            {"args": [3, [[0, 1, 5]]], "expected": -1},
            {"args": [1, []], "expected": 0},
            {"args": [4, [[0, 1, 3], [0, 2, 1], [1, 2, 2], [2, 3, 4], [1, 3, 5]]],
             "expected": 7},
            {"args": [5, [[0, 1, 2], [1, 2, 3], [3, 4, 1], [2, 3, 4]]], "expected": 10},
        ],
        "reference_solution": '''class _DSU:
    def __init__(self, n):
        self._parent = list(range(n))
        self._rank = [0] * n

    def find(self, x):
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        if self._rank[ra] < self._rank[rb]:
            ra, rb = rb, ra
        self._parent[rb] = ra
        if self._rank[ra] == self._rank[rb]:
            self._rank[ra] += 1
        return True


def min_wiring_cost(n, links):
    if n <= 1:
        return 0
    dsu = _DSU(n)
    total = 0
    used = 0
    for u, v, w in sorted(links or [], key=lambda e: (e[2], e[0], e[1])):
        if dsu.union(u, v):
            total += w
            used += 1
            if used == n - 1:
                return total
    return -1
''',
        "constraints": "必须使用 Kruskal（按权值升序 + 并查集判环）；选满 n-1 条边后立即返回。",
    },
    {
        "task_id": "L4-012",
        "difficulty": "L4",
        "task_type": "重构优化",
        "description": (
            "下面这个通知下发函数把渠道选择逻辑硬编码成一串 if/elif，"
            "每新增渠道就要复制一遍分支。请重构它，函数签名保持为 "
            "dispatch_notification(profile, message)。\n\n"
            "```python\n"
            "def dispatch_notification(profile, message):\n"
            "    if message == None or message == '':\n"
            "        ok = False\n"
            "    else:\n"
            "        ok = True\n"
            "    if profile.get('quiet_hours') == True:\n"
            "        ok = False\n"
            "    if profile.get('preferred') == 'email':\n"
            "        if profile.get('email') != None:\n"
            "            return {'channel': 'email', 'target': profile.get('email'), 'delivered': ok}\n"
            "        elif profile.get('phone') != None:\n"
            "            return {'channel': 'sms', 'target': profile.get('phone'), 'delivered': ok}\n"
            "        else:\n"
            "            return {'channel': 'push', 'target': '', 'delivered': ok}\n"
            "    elif profile.get('preferred') == 'sms':\n"
            "        if profile.get('phone') != None:\n"
            "            return {'channel': 'sms', 'target': profile.get('phone'), 'delivered': ok}\n"
            "        elif profile.get('email') != None:\n"
            "            return {'channel': 'email', 'target': profile.get('email'), 'delivered': ok}\n"
            "        else:\n"
            "            return {'channel': 'push', 'target': '', 'delivered': ok}\n"
            "    else:\n"
            "        return {'channel': 'push', 'target': '', 'delivered': ok}\n"
            "```\n\n"
            "规格（重构后须完全等价）：\n"
            "- profile 为 dict，可能包含键 'email'（str 或 None）、'phone'（str 或 None）、"
            "'preferred'（'email'/'sms'/'push' 之一）、'quiet_hours'（bool）；缺失的键按不存在处理；"
            "profile 也可能为 None；\n"
            "- 渠道选择：优先使用 preferred 指定的渠道；若该渠道缺少地址，"
            "则按固定顺序 email → sms → push 依次回退，取第一个有地址的渠道；"
            "push 渠道不需要地址，其 target 为空字符串 ''；\n"
            "- delivered：仅当 message 非 None 且非空字符串、且 quiet_hours 不为 True 时为 True，否则 False；\n"
            "- 返回 dict，固定包含三个键：'channel'、'target'、'delivered'。\n"
            "要求：把渠道回退顺序表达为模块级常量序列，函数体只做一次线性查找。"
        ),
        "entry_point": "dispatch_notification",
        "test_cases": [
            {"args": [{"email": "a@b.c", "phone": "13800000000",
                       "preferred": "email", "quiet_hours": False}, "hi"],
             "expected": {"channel": "email", "target": "a@b.c", "delivered": True}},
            {"args": [{"email": None, "phone": "13800000000",
                       "preferred": "email", "quiet_hours": False}, "hi"],
             "expected": {"channel": "sms", "target": "13800000000", "delivered": True}},
            {"args": [{"email": None, "phone": None,
                       "preferred": "sms", "quiet_hours": False}, "hi"],
             "expected": {"channel": "push", "target": "", "delivered": True}},
            {"args": [{"email": "a@b.c", "phone": None,
                       "preferred": "push", "quiet_hours": False}, "hi"],
             "expected": {"channel": "push", "target": "", "delivered": True}},
            {"args": [{"email": "a@b.c", "phone": None,
                       "preferred": "email", "quiet_hours": True}, "hi"],
             "expected": {"channel": "email", "target": "a@b.c", "delivered": False}},
            {"args": [{"email": "a@b.c", "phone": None,
                       "preferred": "email", "quiet_hours": False}, ""],
             "expected": {"channel": "email", "target": "a@b.c", "delivered": False}},
        ],
        "reference_solution": '''CHANNEL_FALLBACK = ("email", "sms", "push")
ADDRESS_FIELD = {"email": "email", "sms": "phone"}


def dispatch_notification(profile, message):
    profile = profile or {}
    delivered = (message is not None and str(message) != ""
                 and not profile.get("quiet_hours", False))
    preferred = profile.get("preferred")
    order = [preferred] if preferred in CHANNEL_FALLBACK else []
    order += [c for c in CHANNEL_FALLBACK if c != preferred]
    for channel in order:
        if channel == "push":
            return {"channel": "push", "target": "", "delivered": delivered}
        address = profile.get(ADDRESS_FIELD[channel])
        if address:
            return {"channel": channel, "target": address, "delivered": delivered}
    return {"channel": "push", "target": "", "delivered": delivered}
''',
        "constraints": "渠道回退顺序必须写成模块级常量；不得保留原有的 if/elif 渠道分支链。",
    },
]


def main():
    ap = argparse.ArgumentParser(description="补齐 48 题测试集的缺失题目")
    ap.add_argument("--check", action="store_true", help="只校验不写文件")
    args = ap.parse_args()

    with open(OUT_PATH, encoding="utf-8") as f:
        payload = json.load(f)
    have = {t["task_id"] for t in payload["tasks"]}

    ok, bad = [], []
    for task in TASKS:
        errs = validate_task_schema(task) + validate_reference_passes(task)
        if errs:
            bad.append((task["task_id"], errs))
            print(f"❌ {task['task_id']}: {errs}")
        else:
            status = "覆盖" if task["task_id"] in have else "新增"
            ok.append(task)
            print(f"✅ {task['task_id']} [{status}] {task['task_type']} "
                  f"entry={task['entry_point']} 用例={len(task['test_cases'])}")

    print(f"\n校验结果: {len(ok)}/{len(TASKS)} 通过")
    if bad:
        print("存在未过门题目，未写入文件")
        sys.exit(1)
    if args.check:
        return

    by_id = {t["task_id"]: t for t in payload["tasks"]}
    for task in ok:
        by_id[task["task_id"]] = task
    merged = sorted(by_id.values(), key=lambda t: (t["difficulty"], t["task_id"]))
    for t in merged:
        idx = int(t["task_id"].split("-")[1])
        t["split"] = "rule_dev" if idx <= 6 else "holdout"

    meta = payload["metadata"]
    meta["built_at"] = __import__("datetime").datetime.now().isoformat(timespec="seconds")
    meta.setdefault("manual_fill", {})
    meta["manual_fill"] = {
        "editor": "DeepSeek-V4-Pro（对话内直接出题）",
        "task_ids": [t["task_id"] for t in ok],
        "note": ("补齐自动构建未过门的 L3/L4 题目；与自动构建共用同一套质量门"
                 "（schema 校验 + 参考实现须通过自有测试）"),
    }
    payload["tasks"] = merged
    tmp = OUT_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT_PATH)

    from collections import Counter
    print(f"\n已写入 {OUT_PATH}")
    print(f"题目总数: {len(merged)} / 48 | 分布: {dict(sorted(Counter(t['difficulty'] for t in merged).items()))}")
    print(f"划分: {dict(Counter(t['split'] for t in merged))}")


if __name__ == "__main__":
    main()

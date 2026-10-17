"""L4 题目升级（v3 第三批）：DeepSeek-V4-Pro 直接出题，不调 API。

诊断：L4 有 6 题功能分 std=0（003/007/008/009/010/011）→ 全部替换为疑难算法/框架级题，
保留 L4-001/002/004/005/006/012（std 12.7~33.6 有区分度）。
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

_DEC = list(range(30000, 0, -1))

L4_NEW = [
    {
        "task_id": "L4-003", "difficulty": "L4", "task_type": "调试修复",
        "description": (
            "下面这个 KMP 字符串匹配函数本意是在 text 中找 pattern 的首次出现下标（找不到返回 -1）。"
            "但 next（前缀函数）数组的构建有 bug：失配回退时索引写错，导致部分重叠 pattern 漏匹配。\n\n"
            "```python\n"
            "def kmp_search(text, pattern):\n"
            "    if not pattern:\n"
            "        return 0\n"
            "    nxt = [0] * len(pattern)\n"
            "    j = 0\n"
            "    for i in range(1, len(pattern)):\n"
            "        while j > 0 and pattern[i] != pattern[j]:\n"
            "            j = nxt[j]\n"
            "        if pattern[i] == pattern[j]:\n"
            "            j += 1\n"
            "        nxt[i] = j\n"
            "    j = 0\n"
            "    for i in range(len(text)):\n"
            "        while j > 0 and text[i] != pattern[j]:\n"
            "            j = nxt[j]\n"
            "        if text[i] == pattern[j]:\n"
            "            j += 1\n"
            "        if j == len(pattern):\n"
            "            return i - j + 1\n"
            "    return -1\n"
            "```\n\n"
            "请修复并提交完整函数（找首次出现下标）。"
        ),
        "entry_point": "kmp_search",
        "test_cases": [
            {"args": ["hello world", "world"], "expected": 6},
            {"args": ["aaaa", "aa"], "expected": 0},
            {"args": ["abc", "d"], "expected": -1},
            {"args": ["abc", ""], "expected": 0},
            {"args": ["ababcabcab", "abcab"], "expected": 2},
            {"args": ["mississippi", "issip"], "expected": 4},
        ],
        "reference_solution": '''def kmp_search(text, pattern):
    if not pattern:
        return 0
    nxt = [0] * len(pattern)
    j = 0
    for i in range(1, len(pattern)):
        while j > 0 and pattern[i] != pattern[j]:
            j = nxt[j - 1]
        if pattern[i] == pattern[j]:
            j += 1
        nxt[i] = j
    j = 0
    for i in range(len(text)):
        while j > 0 and text[i] != pattern[j]:
            j = nxt[j - 1]
        if text[i] == pattern[j]:
            j += 1
        if j == len(pattern):
            return i - j + 1
    return -1
''',
        "constraints": "O(n+m) 时间；正确构建前缀函数；处理重叠 pattern。",
    },
    {
        "task_id": "L4-007", "difficulty": "L4", "task_type": "算法",
        "description": (
            "实现函数 max_sliding_window(nums, k)，返回每个长度为 k 的滑动窗口内的最大值列表。\n"
            "nums 为整数列表（可能很大），k 为正整数且 k <= len(nums)。\n"
            "要求：用单调双端队列，时间复杂度 O(n)；禁止对每个窗口求 max（O(nk) 大数据量超时）。\n"
            "示例：max_sliding_window([1,3,-1,-3,5,3,6,7], 3) 返回 [3,3,5,5,6,7]。"
        ),
        "entry_point": "max_sliding_window",
        "test_cases": [
            {"args": [[1, 3, -1, -3, 5, 3, 6, 7], 3], "expected": [3, 3, 5, 5, 6, 7]},
            {"args": [[1], 1], "expected": [1]},
            {"args": [[4, 3, 2, 1], 2], "expected": [4, 3, 2]},
            {"args": [[1, 2, 3, 4], 2], "expected": [2, 3, 4]},
            {"args": [_DEC, 1], "expected": _DEC},
            {"args": [list(range(1, 10001)), 3],
             "expected": list(range(3, 10001))},
        ],
        "reference_solution": '''from collections import deque


def max_sliding_window(nums, k):
    if not nums:
        return []
    dq = deque()
    result = []
    for i, x in enumerate(nums):
        while dq and nums[dq[-1]] <= x:
            dq.pop()
        dq.append(i)
        if dq[0] <= i - k:
            dq.popleft()
        if i >= k - 1:
            result.append(nums[dq[0]])
    return result
''',
        "constraints": "单调队列 O(n)；禁止 O(nk)。",
    },
    {
        "task_id": "L4-008", "difficulty": "L4", "task_type": "业务逻辑",
        "description": (
            "实现类 TaskScheduler，一个带依赖与优先级的任务调度器。构造无参数。\n"
            "方法：\n"
            "- add_task(task_id, priority, deps=None)：注册任务；priority 为整数（越小优先级越高）；"
            "deps 为依赖的 task_id 列表（默认为空），任务须等所有依赖 complete 后才能被调度；\n"
            "- next_task()：返回当前「可调度」任务中优先级最高（priority 最小）者的 task_id；"
            "无可调度任务返回 None；依赖未满足或已完成的返回 None 跳过；\n"
            "- complete(task_id)：标记任务完成（不存在则忽略）。\n"
            "若存在循环依赖，相关任务永远无法调度（next_task 返回 None）。"
        ),
        "entry_point": "TaskScheduler",
        "test_cases": [
            {"class": "TaskScheduler", "ctor_args": [],
             "steps": [["add_task", "A", 2], ["add_task", "B", 1], ["next_task"]], "expected": "B"},
            {"class": "TaskScheduler", "ctor_args": [],
             "steps": [["add_task", "A", 1, ["C"]], ["add_task", "C", 3], ["next_task"]],
             "expected": "C"},
            {"class": "TaskScheduler", "ctor_args": [],
             "steps": [["add_task", "A", 1, ["C"]], ["add_task", "C", 3], ["next_task"],
                       ["complete", "C"], ["next_task"]], "expected": "A"},
            {"class": "TaskScheduler", "ctor_args": [],
             "steps": [["add_task", "A", 1], ["complete", "A"], ["next_task"]], "expected": None},
            {"class": "TaskScheduler", "ctor_args": [],
             "steps": [["add_task", "A", 1, ["B"]], ["add_task", "B", 2, ["A"]], ["next_task"]],
             "expected": None},
            {"class": "TaskScheduler", "ctor_args": [],
             "steps": [["add_task", "A", 2], ["add_task", "B", 2], ["next_task"], ["complete", "A"],
                       ["next_task"]], "expected": "B"},
        ],
        "reference_solution": '''import heapq


class TaskScheduler:
    def __init__(self):
        self._tasks = {}      # id -> dict(priority, deps)
        self._done = set()

    def add_task(self, task_id, priority, deps=None):
        self._tasks[task_id] = {"priority": priority, "deps": set(deps or [])}

    def _ready(self, task_id):
        t = self._tasks[task_id]
        return all(d in self._done for d in t["deps"])

    def next_task(self):
        ready = [tid for tid in self._tasks if tid not in self._done and self._ready(tid)]
        if not ready:
            return None
        ready.sort(key=lambda tid: (self._tasks[tid]["priority"], tid))
        return ready[0]

    def complete(self, task_id):
        if task_id in self._tasks:
            self._done.add(task_id)
''',
        "constraints": "依赖满足才可调度；优先级（小值）优先；循环依赖永不可调度。",
    },
    {
        "task_id": "L4-009", "difficulty": "L4", "task_type": "重构优化",
        "description": (
            "下面这个 CSV 行解析函数用状态机硬写、可读性差、扩展难。请重构为清晰实现，"
            "函数签名保持 parse_csv_line(line)，行为完全等价：\n\n"
            "```python\n"
            "def parse_csv_line(line):\n"
            "    res = []\n"
            "    cur = ''\n"
            "    q = False\n"
            "    for i in range(len(line)):\n"
            "        c = line[i]\n"
            "        if q:\n"
            "            if c == '\"':\n"
            "                if i + 1 < len(line) and line[i+1] == '\"':\n"
            "                    cur += '\"'\n"
            "                    i += 1\n"
            "                else:\n"
            "                    q = False\n"
            "            else:\n"
            "                cur += c\n"
            "        else:\n"
            "            if c == '\"':\n"
            "                q = True\n"
            "            elif c == ',':\n"
            "                res.append(cur)\n"
            "                cur = ''\n"
            "            else:\n"
            "                cur += c\n"
            "    res.append(cur)\n"
            "    return res\n"
            "```\n\n"
            "CSV 规则：逗号分隔字段；双引号包裹的字段可含逗号；字段内连续两个双引号表示一个字面双引号。"
            "要求：逻辑清晰、可读，保持完全一致的结果。"
        ),
        "entry_point": "parse_csv_line",
        "test_cases": [
            {"args": ["a,b,c"], "expected": ["a", "b", "c"]},
            {"args": ["\"a,b\",c"], "expected": ["a,b", "c"]},
            {"args": ["\"a\"\"b\",c"], "expected": ["a\"b", "c"]},
            {"args": ["a,,c"], "expected": ["a", "", "c"]},
            {"args": ["\"\""], "expected": [""]},
            {"args": ["\"x\"\"y\"\"z\""], "expected": ["x\"y\"z"]},
        ],
        "reference_solution": '''def parse_csv_line(line):
    fields = []
    current = []
    in_quotes = False
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if in_quotes:
            if ch == '"':
                if i + 1 < n and line[i + 1] == '"':
                    current.append('"')
                    i += 1
                else:
                    in_quotes = False
            else:
                current.append(ch)
        else:
            if ch == '"':
                in_quotes = True
            elif ch == ',':
                fields.append(''.join(current))
                current = []
            else:
                current.append(ch)
        i += 1
    fields.append(''.join(current))
    return fields
''',
        "constraints": "正确处理引号包裹、转义引号、空字段；逻辑清晰。",
    },
    {
        "task_id": "L4-010", "difficulty": "L4", "task_type": "调试修复",
        "description": (
            "下面这个 Dijkstra 最短路径函数本意是返回 source 到各点的最短距离（不可达填 -1）。"
            "但当前实现缺少「懒删除」判断：从堆中弹出的节点可能已被更新过，导致重复处理"
            "并把错误距离再次传播。\n\n"
            "```python\n"
            "def dijkstra(n, edges, source):\n"
            "    import heapq\n"
            "    graph = [[] for _ in range(n)]\n"
            "    for u, v, w in edges:\n"
            "        graph[u].append((v, w))\n"
            "    dist = [float('inf')] * n\n"
            "    dist[source] = 0\n"
            "    heap = [(0, source)]\n"
            "    while heap:\n"
            "        d, u = heapq.heappop(heap)\n"
            "        for v, w in graph[u]:\n"
            "            if dist[u] + w < dist[v]:\n"
            "                dist[v] = dist[u] + w\n"
            "                heapq.heappush(heap, (dist[v], v))\n"
            "    return [-1 if d == float('inf') else d for d in dist]\n"
            "```\n\n"
            "请修复并提交完整函数（边权非负；n 为节点数，edges 为 [u,v,w] 列表）。"
        ),
        "entry_point": "dijkstra",
        "test_cases": [
            {"args": [5, [[0, 1, 2], [0, 2, 4], [1, 2, 1], [1, 3, 7], [2, 4, 3], [3, 4, 1]], 0],
             "expected": [0, 2, 3, 9, 6]},
            {"args": [3, [[0, 1, 1]], 0], "expected": [0, 1, -1]},
            {"args": [1, [], 0], "expected": [0]},
            {"args": [4, [[0, 1, 5], [1, 2, 5], [2, 3, 5], [0, 3, 1]], 0],
             "expected": [0, 5, 10, 1]},
            {"args": [6, [[0, 1, 4], [0, 2, 2], [1, 2, 1], [2, 3, 5], [1, 3, 3], [3, 5, 1], [4, 5, 1]], 0],
             "expected": [0, 4, 2, 7, -1, 8]},
        ],
        "reference_solution": '''import heapq


def dijkstra(n, edges, source):
    graph = [[] for _ in range(n)]
    for u, v, w in edges:
        graph[u].append((v, w))
    dist = [float('inf')] * n
    dist[source] = 0
    heap = [(0, source)]
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]:
            continue
        for v, w in graph[u]:
            if dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
                heapq.heappush(heap, (dist[v], v))
    return [-1 if d == float('inf') else d for d in dist]
''',
        "constraints": "Dijkstra + 最小堆 + 懒删除；不可达填 -1。",
    },
    {
        "task_id": "L4-011", "difficulty": "L4", "task_type": "算法",
        "description": (
            "实现类 MedianFinder，支持数据流中位数。构造无参数。\n"
            "方法：\n"
            "- add_num(num)：加入一个数；\n"
            "- find_median()：返回当前所有数的中位数（float）。偶数个时返回中间两数的平均值。\n"
            "要求：用两个堆（最大堆存较小一半、最小堆存较大一半），"
            "add_num O(log n)、find_median O(1)。\n"
            "示例：依次 add 1,2,3 后 find_median 返回 2.0；add 1,2 后返回 1.5。"
        ),
        "entry_point": "MedianFinder",
        "test_cases": [
            {"class": "MedianFinder", "ctor_args": [],
             "steps": [["add_num", 1], ["add_num", 2], ["add_num", 3], ["find_median"]],
             "expected": 2.0},
            {"class": "MedianFinder", "ctor_args": [],
             "steps": [["add_num", 1], ["find_median"]], "expected": 1.0},
            {"class": "MedianFinder", "ctor_args": [],
             "steps": [["add_num", 1], ["add_num", 2], ["find_median"]], "expected": 1.5},
            {"class": "MedianFinder", "ctor_args": [],
             "steps": [["add_num", 5], ["add_num", 15], ["add_num", 1], ["add_num", 3],
                       ["find_median"]], "expected": 4.0},
            {"class": "MedianFinder", "ctor_args": [],
             "steps": [["add_num", -1], ["add_num", -2], ["add_num", -3], ["find_median"]],
             "expected": -2.0},
        ],
        "reference_solution": '''import heapq


class MedianFinder:
    def __init__(self):
        self.low = []   # 最大堆（存负数）
        self.high = []  # 最小堆

    def add_num(self, num):
        heapq.heappush(self.low, -num)
        heapq.heappush(self.high, -heapq.heappop(self.low))
        if len(self.low) < len(self.high):
            heapq.heappush(self.low, -heapq.heappop(self.high))

    def find_median(self):
        if len(self.low) > len(self.high):
            return float(-self.low[0])
        return (-self.low[0] + self.high[0]) / 2.0
''',
        "constraints": "对顶堆；add_num O(log n)、find_median O(1)。",
    },
]


def main():
    ap = argparse.ArgumentParser(description="L4 题目升级（v3 第三批）")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    with open(SRC_PATH, encoding="utf-8") as f:
        src = json.load(f)

    ok, bad = [], []
    for task in L4_NEW:
        errs = validate_task_schema(task) + validate_reference_passes(task)
        if errs:
            bad.append((task["task_id"], errs))
            print(f"❌ {task['task_id']}: {errs}")
        else:
            ok.append(task)
            print(f"✅ {task['task_id']} [{task['task_type']}] entry={task['entry_point']}")

    print(f"\n校验结果: {len(ok)}/{len(L4_NEW)} 通过")
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
    meta["version"] = "v3-full"
    meta["built_at"] = __import__("datetime").datetime.now().isoformat(timespec="seconds")
    meta.setdefault("upgrade_log", []).append({
        "scope": "L4",
        "reason": "L4 6 题功能分标准差=0，升级为疑难算法/框架级题（KMP/单调队列/Dijkstra/对顶堆）",
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
    print(f"题目总数: {len(merged)} | L1~L4 全部升级完成")
    print(f"分布: {dict(sorted(Counter(t['difficulty'] for t in merged).items()))}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""多模型智能路由原型（母/子 Agent 运行时）

母 Agent（Router）：难度分类 + 模型选择（复用 code-task-router 实测规则）
子 Agent（Worker）：调用选中模型生成代码 + 质量校验（语法 + 单元测试）
回退控制：首选失败 → 备选链 → 连续失败升旗舰 → 跨平台故障转移

复用 eval_kit：clients（双平台客户端，含超时/指数退避重试）、
scoring（语法+单测）、code_extract（代码提取）、config（配置加载）。

安全与健壮：
  - API Key 仅从环境变量读取（load_dotenv），不落盘、不进代码
  - 每次外部调用有显式超时 + 指数退避重试（DualPlatformClient）
  - 回退链有界（每难度 ≤3 层），连续失败升旗舰后仍失败则终止
  - trace_id 贯穿每次分派，日志脱敏（不打印密钥/完整代码）

用法：
  python router_agent.py --task task.json [--classify] [--budget 0.1] [--dry-run]

task.json 字段（与 code-task-router/route.py 一致，但增加代码任务本体）：
  task_id        任务标识（可选，缺省自动生成）
  description    代码任务描述（必填）
  entry_point    入口函数/类名（必填）
  test_cases     单元测试用例列表（必填，用于质量校验）
  difficulty     L1~L4（可选；缺省时用 --classify 让轻量模型分类）

输出：JSON 分派轨迹（决策 + 每次尝试 + 最终结果 + 成本 + 时延）
"""
import argparse
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from eval_kit.config import load_dotenv, load_yaml, ModelRegistry  # noqa: E402
from eval_kit.clients import DualPlatformClient  # noqa: E402
from eval_kit.scoring import syntax_check, run_unit_tests  # noqa: E402
from eval_kit.code_extract import extract_code  # noqa: E402

# ============ 数据层（与 models.yaml / code-task-router 实测版同步） ============
# 规范模型 ID -> (平台, 实际调用快照, 关闭思考链 extra_body)
MODEL_TABLE = {
    "qwen3.7-flash": {
        "platform": "aliyun", "snapshot": "qwen3.7-flash-2026-07-15",
        "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
        "price": (0.2, 0.8),
    },
    "qwen3-coder-flash": {
        "platform": "aliyun", "snapshot": "qwen3-coder-flash",
        "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
        "price": (1.0, 4.0),
    },
    "qwen3.7-plus": {
        "platform": "aliyun", "snapshot": "qwen3.7-plus-2026-05-26",
        "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
        "price": (2.0, 8.0),
    },
    "qwen3.8-max": {
        "platform": "aliyun", "snapshot": "qwen3.8-max-0902",
        "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
        "price": (12.0, 36.0),
    },
    "doubao-seed-2-0-mini-260428": {
        "platform": "volcengine", "snapshot": "doubao-seed-2-0-mini-260428",
        "extra_body": {"thinking": {"type": "disabled"}},
        "price": (0.2, 2.0),
    },
    "doubao-seed-2-1-lite-260915": {
        "platform": "volcengine", "snapshot": "doubao-seed-2-1-lite-260915",
        "extra_body": {"thinking": {"type": "disabled"}},
        "price": (0.8, 2.7),
    },
    "doubao-seed-2-1-pro-260915": {
        "platform": "volcengine", "snapshot": "doubao-seed-2-1-pro-260915",
        "extra_body": {"thinking": {"type": "disabled"}},
        "price": (6.0, 30.0),
    },
    "doubao-seed-2-0-code-preview-260215": {
        "platform": "volcengine", "snapshot": "doubao-seed-2-0-code-preview-260215",
        "extra_body": {"thinking": {"type": "disabled"}},
        "price": (3.2, 16.0),
    },
}

# 实测路由规则（code-task-router 实测版）
ROUTE_RULES = {
    "L1": ["qwen3.7-flash", "doubao-seed-2-0-mini-260428", "doubao-seed-2-1-lite-260915"],
    "L2": ["qwen3.7-flash", "doubao-seed-2-0-mini-260428", "doubao-seed-2-1-lite-260915"],
    "L3": ["qwen3.7-flash", "doubao-seed-2-1-lite-260915", "qwen3-coder-flash"],
    "L4": ["qwen3.8-max", "doubao-seed-2-1-pro-260915", "doubao-seed-2-1-lite-260915"],
}
FLAGSHIP = "qwen3.8-max"

# 难度分类 prompt（H4 假设的验证对象）
CLASSIFY_PROMPT = """请判断以下编程任务的难度等级，只输出 JSON，不要任何解释。

任务描述：
{description}

难度标准：
- L1 入门级：单函数、短代码、常见API、无复杂逻辑
- L2 进阶级：多函数协作、完整类/模块、中等算法、基础业务逻辑
- L3 高级：复杂算法、系统设计片段、调试重构、多模块
- L4 专家级：框架级代码、疑难算法、性能敏感、复杂业务

输出格式：{{"difficulty": "L1|L2|L3|L4", "confidence": 0.0~1.0}}"""

CODE_PROMPT = """你是一名资深Python工程师。请根据题目要求编写完整、可独立运行的Python代码。
要求：遵循PEP8规范，命名清晰，包含必要注释，对输入参数做基本校验与异常处理。
只输出代码本身，不要任何额外解释。

题目描述：
{description}
"""


@dataclass
class Attempt:
    """一次生成+校验的轨迹"""
    model: str
    platform: str
    cost_yuan: float
    latency_seconds: float
    syntax_score: float
    tests_passed: int
    tests_total: int
    passed: bool
    error: Optional[str] = None


@dataclass
class DispatchOutcome:
    """一次分派的完整结果"""
    trace_id: str
    task_id: str
    difficulty: str
    decision_chain: List[str]
    attempts: List[Attempt] = field(default_factory=list)
    success: bool = False
    final_model: Optional[str] = None
    final_code: str = ""
    total_cost_yuan: float = 0.0
    total_latency: float = 0.0
    reason: str = ""

    def to_dict(self):
        return {
            "trace_id": self.trace_id,
            "task_id": self.task_id,
            "difficulty": self.difficulty,
            "decision_chain": self.decision_chain,
            "attempts": [
                {k: v for k, v in a.__dict__.items()} for a in self.attempts
            ],
            "success": self.success,
            "final_model": self.final_model,
            "total_cost_yuan": round(self.total_cost_yuan, 6),
            "total_latency": round(self.total_latency, 3),
            "reason": self.reason,
        }


class RouterAgent:
    """母/子 Agent 路由运行时"""

    def __init__(self, registry, client, pass_line: int = 85,
                 budget_yuan: Optional[float] = None):
        self.registry = registry
        self.client = client
        self.pass_line = pass_line
        self.budget = budget_yuan

    def classify(self, description: str):
        """母 Agent：用最便宜的 T3 模型判断难度。返回 (difficulty, confidence, cost_yuan, latency)。"""
        resp = self.client.chat(
            platform="aliyun", model="qwen3.7-flash",
            messages=[{"role": "user", "content": CLASSIFY_PROMPT.format(description=description)}],
            temperature=0, max_tokens=64, timeout=15,
            extra_body=MODEL_TABLE["qwen3.7-flash"]["extra_body"],
        )
        cost = self._cost("qwen3.7-flash", resp.input_tokens, resp.output_tokens)
        if resp.error:
            return "L2", 0.5, cost, resp.latency  # 分类失败降级为中等难度 + 低置信度
        try:
            data = json.loads(extract_code(resp.content).strip("`").strip())
            d = data.get("difficulty", "L2")
            conf = float(data.get("confidence", 0.5))
            return (d if d in ("L1", "L2", "L3", "L4") else "L2"), conf, cost, resp.latency
        except Exception:
            return "L2", 0.5, cost, resp.latency

    def decide(self, difficulty: str, confidence: float) -> List[str]:
        """母 Agent：低置信度升档 + 选首选与备选链"""
        d = difficulty
        if confidence < 0.7 and d != "L4":
            d = {"L1": "L2", "L2": "L3", "L3": "L4"}[d]
        return ROUTE_RULES.get(d, ROUTE_RULES["L2"])

    def _cost(self, model: str, inp: int, out: int) -> float:
        """简化成本：token × 0-32K 档单价（精确阶梯价见 eval_kit.pricing）"""
        ip, op = MODEL_TABLE[model]["price"]
        return inp / 1_000_000 * ip + out / 1_000_000 * op

    def generate(self, description: str, model: str):
        """子 Agent：调用指定模型生成代码，返回 (code, cost, latency, error)"""
        cfg = MODEL_TABLE[model]
        resp = self.client.chat(
            platform=cfg["platform"], model=cfg["snapshot"],
            messages=[{"role": "user", "content": CODE_PROMPT.format(description=description)}],
            temperature=0.2, top_p=0.9, max_tokens=4096, timeout=30,
            extra_body=cfg["extra_body"],
        )
        code = extract_code(resp.content)
        cost = self._cost(model, resp.input_tokens, resp.output_tokens)
        return code, cost, resp.latency, resp.error

    def check(self, code: str, entry_point: str, test_cases: List[Dict]):
        """子 Agent：质量校验（语法 + 单元测试），返回 (通过?, 语法分, 通过数, 总数)"""
        syn, _errs = syntax_check(code)
        if syn < 100:
            return False, syn, 0, len(test_cases)
        passed, total, _details = run_unit_tests(code, entry_point, test_cases, timeout=30)
        return (syn == 100 and passed == total), syn, passed, total

    def dispatch(self, task: Dict) -> DispatchOutcome:
        """主流程：分类 → 决策 → 生成+校验 → 回退（有界）"""
        trace_id = uuid.uuid4().hex[:12]
        task_id = task.get("task_id", f"task-{trace_id}")
        description = task["description"]
        entry_point = task.get("entry_point", "solution")
        test_cases = task.get("test_cases", [])

        # 难度：优先用任务自带标签，否则调分类器
        difficulty = task.get("difficulty")
        confidence = task.get("confidence", 1.0)
        if difficulty is None:
            difficulty, confidence, classify_cost, classify_latency = self.classify(description)
            outcome.total_cost_yuan += classify_cost
            outcome.total_latency += classify_latency

        chain = self.decide(difficulty, confidence)
        outcome = DispatchOutcome(
            trace_id=trace_id, task_id=task_id,
            difficulty=difficulty, decision_chain=chain,
        )

        # 有界回退：链上逐级尝试，连续 2 个失败直接升旗舰
        consecutive_fail = 0
        for idx, model in enumerate(chain):
            if self.budget and outcome.total_cost_yuan >= self.budget:
                outcome.reason = "预算熔断"
                break
            code, cost, latency, err = self.generate(description, model)
            outcome.total_cost_yuan += cost
            outcome.total_latency += latency
            if err:
                # 平台级故障（5xx/限流/超时）→ 换平台同梯队，这里记为失败
                outcome.attempts.append(Attempt(
                    model=model, platform=MODEL_TABLE[model]["platform"],
                    cost_yuan=cost, latency_seconds=latency,
                    syntax_score=0, tests_passed=0, tests_total=len(test_cases),
                    passed=False, error=err,
                ))
                consecutive_fail += 1
                continue

            ok, syn, passed, total = self.check(code, entry_point, test_cases)
            outcome.attempts.append(Attempt(
                model=model, platform=MODEL_TABLE[model]["platform"],
                cost_yuan=cost, latency_seconds=latency,
                syntax_score=syn, tests_passed=passed, tests_total=total,
                passed=ok,
            ))
            if ok:
                outcome.success = True
                outcome.final_model = model
                outcome.final_code = code
                outcome.reason = f"{model} 首选一次通过" if idx == 0 else f"回退后 {model} 通过"
                break
            consecutive_fail += 1
            # 连续 2 个失败 → 跳过剩余备选，直接旗舰
            if consecutive_fail >= 2 and model != FLAGSHIP:
                if FLAGSHIP in chain[idx + 1:]:
                    continue
                # 旗舰不在剩余链中，直接尝试旗舰
                outcome.decision_chain.append(FLAGSHIP)
                code, cost, latency, err = self.generate(description, FLAGSHIP)
                outcome.total_cost_yuan += cost
                outcome.total_latency += latency
                if not err:
                    ok, syn, passed, total = self.check(code, entry_point, test_cases)
                    outcome.attempts.append(Attempt(
                        model=FLAGSHIP, platform=MODEL_TABLE[FLAGSHIP]["platform"],
                        cost_yuan=cost, latency_seconds=latency,
                        syntax_score=syn, tests_passed=passed, tests_total=total,
                        passed=ok,
                    ))
                    if ok:
                        outcome.success = True
                        outcome.final_model = FLAGSHIP
                        outcome.final_code = code
                        outcome.reason = "连续失败升级旗舰通过"
                break

        if not outcome.success and not outcome.reason:
            outcome.reason = "回退链耗尽，全部模型未通过校验"
        return outcome


def main():
    ap = argparse.ArgumentParser(description="多模型智能路由原型（母/子 Agent）")
    ap.add_argument("--task", required=True, help="任务 JSON 文件路径")
    ap.add_argument("--classify", action="store_true", help="强制用轻量模型分类（忽略 task.difficulty）")
    ap.add_argument("--budget", type=float, default=None, help="单任务成本上限（元）")
    ap.add_argument("--dry-run", action="store_true", help="用 MockClient 干跑，不调用真实 API")
    args = ap.parse_args()

    load_dotenv(os.path.join(ROOT, ".env.local"))
    models_cfg = load_yaml(os.path.join(ROOT, "config", "models.yaml"))
    registry = ModelRegistry(models_cfg)

    if args.dry_run:
        from eval_kit.clients import MockClient
        client = MockClient(response="def solution(*args):\n    return 0\n")
    else:
        client = DualPlatformClient(registry)

    with open(args.task, "r", encoding="utf-8") as f:
        task = json.load(f)
    if args.classify:
        task.pop("difficulty", None)

    agent = RouterAgent(registry, client, budget_yuan=args.budget)
    outcome = agent.dispatch(task)
    print(json.dumps(outcome.to_dict(), ensure_ascii=False, indent=2))
    sys.exit(0 if outcome.success else 1)


if __name__ == "__main__":
    main()

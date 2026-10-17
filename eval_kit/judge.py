"""LLM-as-Judge 裁判：规范性与健壮性评分（附录A Prompt）。"""

import json
import re
from typing import Dict, Optional

JUDGE_PROMPT_TEMPLATE = """你是一名严格的资深代码评审专家，只负责评审代码的「规范性」和「健壮性」两个维度。
（语法正确性与功能正确性已由自动化测试另行判定，无需你评估，grammar_score 与 function_score 固定填 100 占位。）

请严格按以下锚点打分，拉开梯度，好代码与差代码必须有明显分差，禁止集中在高分区间：

【规范性 style_score】（0-100）
- 90~100：命名精准、结构清晰、符合 PEP8、注释恰到好处，几乎无可挑剔
- 75~89：整体规范，但有少量瑕疵（命名含糊、缺注释、结构可优化）
- 60~74：有明显问题（命名随意、逻辑混乱、大量重复、无注释）
- 0~59：难以阅读、风格极差

【健壮性 robustness_score】（0-100）
- 90~100：充分处理边界条件、异常输入、空值、类型校验，防御性编程到位
- 75~89：主要路径健壮，但遗漏部分边界或异常场景
- 60~74：仅处理正常输入，边界和异常基本未考虑
- 0~59：对异常输入会崩溃或产生错误结果

题目描述：
{task_description}

待评审代码：
{generated_code}

输出要求：
- 只输出 JSON，不要任何额外解释
- 格式：{{"grammar_score": 100, "function_score": 100, "style_score": int, "robustness_score": int, "total_score": int}}
- grammar_score 与 function_score 固定填 100；style_score 与 robustness_score 按上述锚点严格评分；total_score 为 style 与 robustness 的合理加权合成（style 占 45%、robustness 占 55%）"""

_FIELDS = ("grammar_score", "function_score", "style_score", "robustness_score", "total_score")


def build_judge_messages(task_description: str, generated_code: str):
    prompt = JUDGE_PROMPT_TEMPLATE.format(
        task_description=task_description,
        generated_code=generated_code,
    )
    return [{"role": "user", "content": prompt}]


def parse_judge_response(text: str) -> Optional[Dict[str, int]]:
    """解析裁判输出为分数字典；非法输出返回 None（调用方记0并标注）。"""
    if not text:
        return None
    m = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    scores = {}
    for f in _FIELDS:
        v = data.get(f)
        if not isinstance(v, (int, float)) or not (0 <= v <= 100):
            return None
        scores[f] = int(v)
    return scores

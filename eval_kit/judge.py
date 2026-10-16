"""LLM-as-Judge 裁判：规范性与健壮性评分（附录A Prompt）。"""

import json
import re
from typing import Dict, Optional

JUDGE_PROMPT_TEMPLATE = """你是一名严格的代码质量评审专家，请从以下4个维度对给定的Python代码进行打分，每个维度满分100分，最终输出JSON格式。

评分维度：
1. 语法正确性（30%权重）：是否存在语法错误、导入缺失、类型错误等无法运行的问题
2. 功能正确性（40%权重）：是否正确实现了题目要求，边界条件处理是否合理
3. 代码规范性（20%权重）：命名是否规范、可读性如何、是否符合PEP8、注释是否恰当
4. 健壮性（10%权重）：是否有异常处理、输入校验，鲁棒性如何

题目描述：
{task_description}

待评审代码：
{generated_code}

输出要求：
- 只输出JSON，不要任何额外解释
- 格式：{{"grammar_score": int, "function_score": int, "style_score": int, "robustness_score": int, "total_score": int}}"""

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

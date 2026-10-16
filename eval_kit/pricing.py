"""阶梯计价成本计算。

两平台均按「单次请求输入 Token 数」分档计价，成本统计必须基于每次
请求的实际输入长度查档，不能用单一均价近似（计划书 3.4）。
"""


def select_tier(pricing, input_tokens):
    """按输入 token 数选择计价档，返回 (input_price, output_price) 元/百万token。"""
    for tier in pricing:
        if input_tokens <= tier["upto_input"]:
            return tier["input"], tier["output"]
    last = pricing[-1]
    return last["input"], last["output"]


def cost_yuan(model_cfg, input_tokens, output_tokens):
    """单次任务成本（元）。model_cfg 为 models.yaml 中该模型的配置段。"""
    in_price, out_price = select_tier(model_cfg["pricing"], input_tokens)
    return input_tokens / 1_000_000 * in_price + output_tokens / 1_000_000 * out_price


def tier_name(model_cfg, input_tokens):
    """返回输入所属阶梯档位名称（用于数据记录）。"""
    for tier in model_cfg["pricing"]:
        if input_tokens <= tier["upto_input"]:
            bound = tier["upto_input"]
            if bound >= 1_048_576:
                return "256K-1M"
            if bound >= 262_144:
                return "128-256K"
            if bound >= 131_072:
                return "32-128K"
            return "0-32K"
    return "256K-1M"

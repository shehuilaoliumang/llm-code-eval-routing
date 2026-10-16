"""百炼平台连通性验证（不依赖完整评测流程）。

用法: python scripts_check_aliyun.py
- 从 .env 读取 DASHSCOPE_API_KEY（.env 已被 gitignore）
- 1) 尝试列出可用模型（免费，不耗 token）
- 2) 用最便宜的 qwen3.7-flash 做最小生成调用（成本约 0.0002 元）
- 全程不打印密钥
"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from eval_kit.clients import DualPlatformClient
from eval_kit.config import ModelRegistry, load_yaml


def load_dotenv(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def main():
    load_dotenv(os.path.join(ROOT, ".env"))
    key = os.environ.get("DASHSCOPE_API_KEY", "")
    print(f"DASHSCOPE_API_KEY: {'已读取（长度 %d）' % len(key) if key else '❌ 未设置'}")

    registry = ModelRegistry(load_yaml(os.path.join(ROOT, "config", "models.yaml")))
    client = DualPlatformClient(registry)

    # 1) 模型列表（免费）
    print("\n=== 1) 可用模型列表（/compatible-mode/v1/models）===")
    try:
        from openai import OpenAI

        oai = OpenAI(api_key=key,
                     base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
        models = [m.id for m in oai.models.list().data]
        print(f"共 {len(models)} 个可用模型")
        core = ["qwen3.8-max", "qwen3-coder-plus", "qwen3.7-plus", "qwen3.7-flash"]
        for m in core:
            hits = [x for x in models if m in x]
            print(f"  {m}: {'✅ ' + ', '.join(hits[:3]) if hits else '⚠️ 未在列表'}")
    except Exception as e:  # noqa: BLE001
        print(f"模型列表获取失败（不影响调用）: {type(e).__name__}: {e}")

    # 2) 最小生成调用
    print("\n=== 2) 最小生成调用（qwen3.7-flash, max_tokens=32）===")
    result = client.chat(
        platform="aliyun",
        model="qwen3.7-flash",
        messages=[{"role": "user", "content": "回复：连通性测试OK"}],
        max_tokens=32,
        timeout=20,
    )
    if result.error:
        print(f"❌ 调用失败: {result.error}")
        sys.exit(1)
    print(f"✅ 调用成功")
    print(f"  回复: {result.content[:60]!r}")
    print(f"  用量: 输入 {result.input_tokens} / 输出 {result.output_tokens} tokens")
    print(f"  耗时: {result.latency:.2f}s")
    cfg = registry.get("qwen3.7-flash")
    from eval_kit.pricing import cost_yuan

    print(f"  本次成本: {cost_yuan(cfg, result.input_tokens, result.output_tokens):.6f} 元")


if __name__ == "__main__":
    main()

"""火山方舟 Key 连通性验证 + 模型可用性核实 + 思考链机制测试

用法:
    python check_volcengine.py

验证内容:
    1. Key 有效性（模型列表 API）
    2. 五款核心模型可用性（直接以模型名调用）
    3. 思考链关闭机制（doubao 官方为 thinking:{"type":"disabled"}）
    4. max_tokens 限制是否生效
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv

load_dotenv()

from openai import OpenAI

KEY = os.environ.get("VOLCENGINE_API_KEY")
if not KEY:
    print("❌ VOLCENGINE_API_KEY 未配置（.env）")
    sys.exit(1)

client = OpenAI(api_key=KEY, base_url="https://ark.cn-beijing.volces.com/api/v3")

print("=" * 60)
print("1. Key 有效性 / 模型列表")
print("=" * 60)
try:
    models = client.models.list()
    ids = sorted(m.id for m in models.data)
    print(f"✅ Key 有效，账号可见 {len(ids)} 个接入点/模型")
    for m in ids[:40]:
        print("  -", m)
except Exception as e:
    print(f"⚠️ 模型列表 API 不可用: {type(e).__name__}: {e}")
    print("   （方舟部分账号不支持 models.list，改用直接调用验证）")

CORE = [
    "doubao-seed-2.1-pro",
    "doubao-seed-evolving",
    "doubao-seed-2.1-lite",
    "doubao-seed-2.0-mini",
    "deepseek-v4-pro",
]

print()
print("=" * 60)
print("2. 核心模型可用性 + 思考链机制（每题1次，最小token）")
print("=" * 60)

for model in CORE:
    for label, kwargs in [
        ("默认", {}),
        ("关思考", {"extra_body": {"thinking": {"type": "disabled"}}}),
    ]:
        try:
            r = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "1+1=? 只回答数字"}],
                max_tokens=32,
                timeout=30,
                **kwargs,
            )
            u = r.usage
            print(
                f"  ✅ {model:28s} [{label}] "
                f"输入{u.prompt_tokens} 输出{u.completion_tokens} "
                f"| {r.choices[0].message.content[:30]!r}"
            )
        except Exception as e:
            msg = str(e)[:110].replace("\n", " ")
            print(f"  ❌ {model:28s} [{label}] {type(e).__name__}: {msg}")

print()
print("=" * 60)
print("3. 已下线模型复核（确认状态）")
print("=" * 60)
for model in ["doubao-seed-code", "doubao-seed-2.1-turbo", "doubao-seed-2.0-code"]:
    try:
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=8,
            timeout=20,
        )
        print(f"  ⚠️ {model}: 仍可调用（输出 {r.usage.completion_tokens} tokens）")
    except Exception as e:
        print(f"  ❌ {model}: {type(e).__name__}: {str(e)[:100]}")

"""双平台统一客户端（OpenAI 兼容协议封装）。

平台差异仅体现在 base_url / api_key / model 三个配置项（计划书 3.2）。
API Key 从环境变量读取，不落盘、不进代码。
重试策略：指数退避，应对 429 / 5xx / 超时。
"""

import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .recorder import JSONLRecorder


@dataclass
class ChatResult:
    platform: str
    model: str
    content: str
    input_tokens: int
    output_tokens: int
    latency: float
    attempts: int = 1
    error: Optional[str] = None
    extra: Dict = field(default_factory=dict)


class DualPlatformClient:
    def __init__(self, registry, retry_cfg: Optional[Dict] = None,
                 recorder: Optional[JSONLRecorder] = None):
        self.registry = registry
        self.retry_cfg = retry_cfg or {"max_attempts": 5,
                                       "backoff_base_seconds": 2,
                                       "backoff_max_seconds": 60}
        self.recorder = recorder
        self._clients = {}

    def _get_openai_client(self, platform: str):
        if platform in self._clients:
            return self._clients[platform]
        cfg = self.registry.platform_cfg(platform)
        key = os.environ.get(cfg["api_key_env"])
        if not key:
            raise RuntimeError(
                f"缺少环境变量 {cfg['api_key_env']}（{cfg['display']} API Key）。"
                "请通过环境变量提供，不要在代码中硬编码。"
            )
        from openai import OpenAI  # 延迟导入，未安装时其余模块仍可用

        client = OpenAI(api_key=key, base_url=cfg["base_url"])
        self._clients[platform] = client
        return client

    def chat(self, platform: str, model: str, messages: List[Dict],
             temperature: float = 0.2, top_p: float = 0.9,
             max_tokens: int = 4096, timeout: float = 30,
             extra_body: Optional[Dict] = None) -> ChatResult:
        client = self._get_openai_client(platform)
        attempts = 0
        last_error = None
        while attempts < self.retry_cfg["max_attempts"]:
            attempts += 1
            start = time.perf_counter()
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    top_p=top_p,
                    max_tokens=max_tokens,
                    timeout=timeout,
                    extra_body=extra_body or None,
                )
                latency = time.perf_counter() - start
                usage = resp.usage
                result = ChatResult(
                    platform=platform,
                    model=model,
                    content=resp.choices[0].message.content or "",
                    input_tokens=getattr(usage, "prompt_tokens", 0),
                    output_tokens=getattr(usage, "completion_tokens", 0),
                    latency=latency,
                    attempts=attempts,
                )
                self._record_call(result)
                return result
            except Exception as e:  # noqa: BLE001 —— 需捕获所有网络/限流异常做退避
                last_error = f"{type(e).__name__}: {e}"
                if attempts >= self.retry_cfg["max_attempts"]:
                    break
                time.sleep(self._backoff(attempts))
        result = ChatResult(
            platform=platform, model=model, content="",
            input_tokens=0, output_tokens=0, latency=0.0,
            attempts=attempts, error=last_error,
        )
        self._record_call(result)
        return result

    def _backoff(self, attempt: int) -> float:
        base = self.retry_cfg["backoff_base_seconds"]
        cap = self.retry_cfg["backoff_max_seconds"]
        return min(base * (2 ** (attempt - 1)), cap)

    def _record_call(self, result: ChatResult) -> None:
        if self.recorder is None:
            return
        self.recorder.write({
            "type": "api_call",
            "platform": result.platform,
            "model": result.model,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "latency_seconds": round(result.latency, 3),
            "attempts": result.attempts,
            "error": result.error,
        })


class MockClient:
    """无 key 的干跑客户端：返回预置响应，用于管线自检。"""

    def __init__(self, response: str = "def solution(*args):\n    return None\n"):
        self.response = response

    def chat(self, platform, model, messages, **kwargs) -> ChatResult:
        return ChatResult(
            platform=platform, model=model, content=self.response,
            input_tokens=len(str(messages)) // 4,
            output_tokens=len(self.response) // 4,
            latency=0.01,
        )
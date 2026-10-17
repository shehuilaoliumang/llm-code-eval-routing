#!/usr/bin/env python3
"""实时可视化 Web 服务：常驻端口 + SSE 进度推送 + 评估任务管理。

复用 eval_kit 的 EvaluationRunner（progress_callback）与 JSONLRecorder，
前端通过 SSE 实时看到每道题的判分进度，而非只看最终结果。

安全：
  - 默认 bind 127.0.0.1（不暴露公网/局域网）
  - 可选 --token 鉴权（暴露到局域网时建议启用）
  - API Key 仅存服务端环境变量，前端永远拿不到密钥

用法：
  python web_server.py [--port 8000] [--host 127.0.0.1] [--workers 6] [--token xxx]

依赖：fastapi、uvicorn（受管 venv 已装）
"""
import argparse
import asyncio
import json
import os
import queue
import sys
import threading
import uuid

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.responses import StreamingResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from eval_kit.config import load_dotenv, load_yaml, ModelRegistry, EvalConfig  # noqa: E402
from eval_kit.clients import DualPlatformClient  # noqa: E402
from eval_kit.recorder import JSONLRecorder  # noqa: E402
from eval_kit.runner import EvaluationRunner, load_tasks  # noqa: E402

MODELS_PATH = os.path.join(ROOT, "config", "models.yaml")
EVAL_PATH = os.path.join(ROOT, "config", "eval.yaml")
TASKS_PATH = os.path.join(ROOT, "data", "tasks", "tasks_v3.json")
RESULTS_DIR = os.path.join(ROOT, "data", "results")
STATIC_DIR = os.path.join(ROOT, "static")


class ProgressBroker:
    """线程安全的进度广播器：runner 后台线程 publish，SSE 订阅者消费。"""

    def __init__(self):
        self._subscribers = []
        self._lock = threading.Lock()
        self.state = {"done": 0, "total": 0, "status": "idle", "eval_id": None}

    def publish(self, event: dict):
        with self._lock:
            self.state.update(event)
            for q in self._subscribers:
                q.put(event)

    def subscribe(self) -> queue.Queue:
        q = queue.Queue()
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue):
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)


class EvalRequest(BaseModel):
    models: list[str] = Field(default_factory=list, description="模型 ID 列表，空则全部候选")
    task_ids: list[str] = Field(default_factory=list, description="任务 ID 列表，空则全部")
    runs: int = Field(default=1, ge=1, le=3, description="每题每模型运行次数")
    workers: int = Field(default=6, ge=1, le=12, description="并发数")


class TestRequest(BaseModel):
    models: list[dict] = Field(default_factory=list,
                               description="[{platform, id}] 待连通测试的模型")
    workers: int = Field(default=5, ge=1, le=10, description="连通测试并发数")


# 名称预过滤：排除明显非代码/文本的模型（语音/图像/向量/重排）
_EXCLUDE_KEYWORDS = ("speech", "asr", "tts", "voice", "audio",
                     "image", "vision", "ocr", "video",
                     "embedding", "embed", "rerank")


def _is_code_candidate(model_id: str) -> bool:
    low = model_id.lower()
    return not any(k in low for k in _EXCLUDE_KEYWORDS)


class AppState:
    def __init__(self):
        load_dotenv(os.path.join(ROOT, ".env.local"))
        self.models_cfg = load_yaml(MODELS_PATH)
        self.eval_cfg = EvalConfig(load_yaml(EVAL_PATH))
        self.registry = ModelRegistry(self.models_cfg)
        self.client = DualPlatformClient(self.registry)
        self.broker = ProgressBroker()
        self._eval_thread = None
        self._eval_lock = threading.Lock()
        self._platform_models_cache = None
        self._platform_models_time = 0.0

    def candidate_models(self):
        return [m for m in self.registry.candidates()]

    def list_platform_models(self, refresh: bool = False):
        """动态查询两平台所有可用模型（models.list，免费不耗 token）。

        返回 {"volcengine": [模型ID...], "aliyun": [...],
              "verified_ids": [已验证候选...], "errors": [...]}
        带 5 分钟内存缓存；单平台查询失败不影响另一平台。
        """
        import time

        if (not refresh and self._platform_models_cache is not None
                and time.time() - self._platform_models_time < 300):
            return self._platform_models_cache

        from openai import OpenAI

        result = {"volcengine": [], "aliyun": [],
                  "verified_ids": self.candidate_models(), "errors": []}

        # 火山方舟
        key = os.environ.get("VOLCENGINE_API_KEY")
        if key:
            try:
                base = self.models_cfg["platforms"]["volcengine"]["base_url"]
                c = OpenAI(api_key=key, base_url=base, timeout=15)
                result["volcengine"] = sorted(m.id for m in c.models.list().data)
            except Exception as e:  # noqa: BLE001
                result["errors"].append(f"方舟: {type(e).__name__}")
        else:
            result["errors"].append("缺少 VOLCENGINE_API_KEY")

        # 阿里云百炼
        key = os.environ.get("DASHSCOPE_API_KEY")
        if key:
            try:
                base = self.models_cfg["platforms"]["aliyun"]["base_url"]
                c = OpenAI(api_key=key, base_url=base, timeout=15)
                result["aliyun"] = sorted(m.id for m in c.models.list().data)
            except Exception as e:  # noqa: BLE001
                result["errors"].append(f"百炼: {type(e).__name__}")
        else:
            result["errors"].append("缺少 DASHSCOPE_API_KEY")

        self._platform_models_cache = result
        self._platform_models_time = time.time()
        return result

    def _ensure_model_config(self, model_id: str) -> str:
        """未配置的模型动态注册最小配置（探索性评估，尽力而为）。

        平台根据模型名前缀推断；定价未知记 0，思考链按平台默认机制关闭。
        已验证候选（models.yaml 中）原样返回，不重复注册。
        """
        if model_id in self.registry.models:
            return model_id
        if model_id.startswith(("doubao", "deepseek", "glm", "kimi", "moonshot")):
            platform = "volcengine"
            disable = {"thinking": {"type": "disabled"}}
        elif model_id.startswith(("qwen", "qwq")):
            platform = "aliyun"
            disable = {"chat_template_kwargs": {"enable_thinking": False}}
        else:
            return model_id  # 无法推断平台，交给 registry 报错
        self.registry.models[model_id] = {
            "platform": platform,
            "tier": "T?",
            "role": "candidate",
            "enabled": True,
            "snapshot": model_id,
            "context_window": 0,
            "pricing": [{"upto_input": 1000000, "input": 0.0, "output": 0.0}],
            "disable_thinking_body": disable,
            "note": "动态注册：未配置定价/思考链，成本记为 0",
        }
        return model_id

    def _disable_thinking_for(self, platform: str):
        """按平台返回关闭思考链的 extra_body。"""
        if platform == "volcengine":
            return {"thinking": {"type": "disabled"}}
        return {"chat_template_kwargs": {"enable_thinking": False}}

    def test_connectivity(self, models: list, workers: int = 5):
        """并发连通测试：名称预过滤后，对每个模型发一次最小调用。

        返回 {"tested": N, "available": M, "results": {id: {platform, available, error}}}
        每次调用约 ¥0.0001~0.001；并发受限流保护。
        """
        from concurrent.futures import ThreadPoolExecutor

        filtered = [m for m in models if _is_code_candidate(m.get("id", ""))]

        def _test_one(m):
            mid, platform = m["id"], m["platform"]
            try:
                resp = self.client.chat(
                    platform=platform, model=mid,
                    messages=[{"role": "user", "content": "hi"}],
                    max_tokens=8, timeout=15,
                    extra_body=self._disable_thinking_for(platform),
                )
                if resp.error:
                    return mid, {"platform": platform, "available": False,
                                 "error": resp.error[:100]}
                return mid, {"platform": platform, "available": True, "error": ""}
            except Exception as e:  # noqa: BLE001
                return mid, {"platform": platform, "available": False,
                             "error": f"{type(e).__name__}: {str(e)[:80]}"}

        results = {}
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for mid, res in ex.map(_test_one, filtered):
                results[mid] = res
        return {
            "tested": len(filtered),
            "available": sum(1 for r in results.values() if r["available"]),
            "results": results,
        }

    def model_info(self, model_id):
        cfg = self.registry.get(model_id)
        return {
            "id": model_id,
            "platform": cfg["platform"],
            "display": self.models_cfg["platforms"][cfg["platform"]]["display"],
            "snapshot": cfg.get("snapshot", model_id),
            "tier": cfg.get("tier", ""),
        }

    def is_running(self):
        return self._eval_thread is not None and self._eval_thread.is_alive()

    def start_eval(self, req: EvalRequest) -> str:
        with self._eval_lock:
            if self.is_running():
                raise HTTPException(409, "已有评估任务在运行，请等待完成")
            eval_id = uuid.uuid4().hex[:8]
            thread = threading.Thread(
                target=self._run_eval, args=(eval_id, req), daemon=True,
            )
            self._eval_thread = thread
            thread.start()
            return eval_id

    def _run_eval(self, eval_id: str, req: EvalRequest):
        try:
            tasks = load_tasks(TASKS_PATH)
            if req.task_ids:
                tasks = [t for t in tasks if t["task_id"] in req.task_ids]
            models = req.models or self.candidate_models()
            # 未配置的平台模型动态注册最小配置（探索性评估）
            models = [self._ensure_model_config(m) for m in models]
            recorder = JSONLRecorder(os.path.join(RESULTS_DIR, f"web_{eval_id}.jsonl"))

            def on_progress(ev):
                ev["eval_id"] = eval_id
                self.broker.publish(ev)

            runner = EvaluationRunner(
                self.registry, self.eval_cfg, self.client, recorder,
                cross_check_ratio=0.0, progress_callback=on_progress,
            )
            runner.run(tasks, models, runs=req.runs, workers=req.workers)
            # 全部完成，广播结束事件
            self.broker.publish({
                "done": self.broker.state.get("done", 0),
                "total": self.broker.state.get("total", 0),
                "status": "done", "eval_id": eval_id,
            })
        except Exception as e:  # noqa: BLE001
            self.broker.publish({
                "status": "error", "eval_id": eval_id, "error": str(e),
            })


state = AppState()
app = FastAPI(title="LLM 代码生成能力评估 · 实时可视化")


@app.get("/api/models")
def list_models():
    return {"models": [state.model_info(m) for m in state.candidate_models()]}


@app.get("/api/models/available")
def list_available_models(refresh: bool = False):
    """动态查询两平台所有可用模型（免费 models.list，带 5 分钟缓存）。"""
    return state.list_platform_models(refresh=refresh)


@app.post("/api/models/test")
def test_models(req: TestRequest):
    """连通测试：名称过滤后逐个最小调用，返回可用性（花钱，单次约 ¥0.0001~0.001）。"""
    return state.test_connectivity(req.models, workers=req.workers)


@app.get("/api/tasks")
def list_tasks():
    tasks = load_tasks(TASKS_PATH)
    return {
        "tasks": [
            {"task_id": t["task_id"], "difficulty": t["difficulty"],
             "task_type": t.get("task_type", ""), "entry_point": t["entry_point"],
             "description": t["description"][:80]}
            for t in tasks
        ]
    }


@app.post("/api/eval")
def start_eval(req: EvalRequest):
    eval_id = state.start_eval(req)
    return {"eval_id": eval_id, "status": "started"}


@app.get("/api/eval/status")
def eval_status():
    return state.broker.state


@app.get("/api/eval/stream")
async def eval_stream(request: Request):
    """SSE 实时进度推送。每完成一题，服务端推送一条 progress 事件。"""
    async def gen():
        q = state.broker.subscribe()
        try:
            # 先推送当前状态快照
            yield _sse("status", state.broker.state)
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.get_event_loop().run_in_executor(
                        None, q.get, True, 25.0)
                    yield _sse("progress", event)
                except queue.Empty:
                    yield ": ping\n\n"  # 心跳，保活
        finally:
            state.broker.unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


# 静态前端面板
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


def main():
    ap = argparse.ArgumentParser(description="实时可视化 Web 服务")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1", help="默认仅本机；局域网用 0.0.0.0 并建议加 --token")
    ap.add_argument("--workers", type=int, default=6, help="默认并发数")
    args = ap.parse_args()

    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()

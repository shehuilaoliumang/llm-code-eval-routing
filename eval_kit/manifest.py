"""评测 manifest：固定模型快照、提示词版本、参数与价格快照，保证可复现。"""

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone

from . import __version__


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _sha256_file(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() if out.returncode == 0 else "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def build_manifest(eval_cfg: dict, registry, task_path: str,
                   eval_cfg_path: str, models_cfg_path: str) -> dict:
    models = {}
    for mid in registry.candidates():
        cfg = registry.get(mid)
        models[mid] = {
            "platform": cfg["platform"],
            "snapshot": cfg.get("snapshot", "latest"),
            "verified": cfg.get("verified", False),
        }
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "kit_version": f"eval_kit {__version__}",
        "git_commit": _git_commit(),
        "eval_config_sha256": _sha256_file(eval_cfg_path),
        "models_config_sha256": _sha256_file(models_cfg_path),
        "tasks_sha256": _sha256_file(task_path),
        "system_prompt_sha256": _sha256_text(eval_cfg["system_prompt"]),
        "generation_params": eval_cfg["generation"],
        "judge_params": eval_cfg["judge"],
        "models": models,
        "price_snapshot_date": registry.cfg.get("snapshot_date", "unknown"),
    }


def save_manifest(manifest: dict, path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

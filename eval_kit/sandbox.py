"""沙箱执行：在独立子进程中运行候选代码，带超时与输出捕获。

Windows 兼容（subprocess + sys.executable -I 隔离模式）。
注意：个人研究场景，不启用内存/文件系统硬隔离；评测代码来自主流
商业模型 API，风险可控。如需硬隔离可后续接入容器化执行。
"""

import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class RunResult:
    returncode: int
    stdout: str
    stderr: str
    duration: float
    timed_out: bool
    errors: List[str] = field(default_factory=list)


def run_python(source: str, timeout: float = 30, cwd: Optional[str] = None) -> RunResult:
    """在临时文件中执行 Python 源码，返回 RunResult。"""
    fd, path = tempfile.mkstemp(suffix=".py", prefix="eval_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(source)
        start = time.perf_counter()
        try:
            proc = subprocess.run(
                [sys.executable, "-I", path],
                capture_output=True,
                timeout=timeout,
                cwd=cwd,
            )
            duration = time.perf_counter() - start
            return RunResult(
                returncode=proc.returncode,
                stdout=proc.stdout.decode("utf-8", errors="replace"),
                stderr=proc.stderr.decode("utf-8", errors="replace"),
                duration=duration,
                timed_out=False,
            )
        except subprocess.TimeoutExpired as e:
            return RunResult(
                returncode=-1,
                stdout=(e.stdout or b"").decode("utf-8", errors="replace")
                if isinstance(e.stdout, bytes)
                else (e.stdout or ""),
                stderr=((e.stderr or b"").decode("utf-8", errors="replace")
                        if isinstance(e.stderr, bytes) else (e.stderr or ""))
                + f"\n[TIMEOUT after {timeout}s]",
                duration=timeout,
                timed_out=True,
                errors=[f"执行超时（>{timeout}s）"],
            )
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

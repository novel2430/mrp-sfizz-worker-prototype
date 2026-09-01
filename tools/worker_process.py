#!/usr/bin/env python3
"""Safe host wrapper for the persistent worker subprocess.

The worker may emit libsfizz diagnostics from background loading threads. stderr
must therefore be drained continuously: leaving stderr=PIPE unread can block a
loader thread once the pipe fills, which in turn can make renderBlock wait
forever for background loading.
"""
from __future__ import annotations

import collections
import subprocess
import sys
import threading
from typing import Sequence


class WorkerProcess:
    """Persistent worker process with a continuously drained stderr pipe.

    Diagnostics are retained in a bounded tail for failures. They remain silent
    by default; debug=True mirrors them to this host process' stderr in real
    time.
    """

    def __init__(
        self,
        command: Sequence[str],
        *,
        debug: bool = False,
        diagnostic_lines: int = 200,
    ) -> None:
        if diagnostic_lines <= 0:
            raise ValueError("diagnostic_lines must be > 0")

        self._debug = debug
        self._diagnostics: collections.deque[str] = collections.deque(maxlen=diagnostic_lines)
        self._diagnostics_lock = threading.Lock()
        self.proc = subprocess.Popen(
            list(map(str, command)),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        if self.proc.stdin is None or self.proc.stdout is None or self.proc.stderr is None:
            self._terminate_best_effort()
            raise RuntimeError("failed to create worker stdio pipes")

        self._stderr_thread = threading.Thread(
            target=self._drain_stderr,
            name=f"worker-stderr-{self.proc.pid}",
            daemon=True,
        )
        self._stderr_thread.start()

    @property
    def pid(self) -> int:
        return self.proc.pid

    def _drain_stderr(self) -> None:
        # readline()/iteration continues pulling data from the OS pipe even when
        # the producer is noisy; storing only a bounded tail keeps host memory
        # usage bounded as well.
        assert self.proc.stderr is not None
        try:
            for line in self.proc.stderr:
                line = line.rstrip("\r\n")
                if not line:
                    continue
                with self._diagnostics_lock:
                    self._diagnostics.append(line)
                if self._debug:
                    print(f"[worker:{self.proc.pid} stderr] {line}", file=sys.stderr, flush=True)
        except (OSError, ValueError):
            # The stream can be closed while cleaning up an already-failed
            # worker. The process status/recent diagnostics remain authoritative.
            pass

    def recent_diagnostics(self) -> str:
        with self._diagnostics_lock:
            return "\n".join(self._diagnostics)

    def _failure_context(self) -> str:
        rc = self.proc.poll()
        status = f"returncode={rc}" if rc is not None else "returncode=unknown"
        diagnostics = self.recent_diagnostics()
        if diagnostics:
            return f"{status}\nrecent worker stderr:\n{diagnostics}"
        return f"{status}\nrecent worker stderr: <empty>"

    def send(self, command: str) -> None:
        assert self.proc.stdin is not None
        try:
            self.proc.stdin.write(command.rstrip("\n") + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError, ValueError) as exc:
            raise RuntimeError(f"failed to send worker command: {exc}\n{self._failure_context()}") from exc

    def read_reply(self) -> str:
        assert self.proc.stdout is not None
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError(f"worker exited unexpectedly\n{self._failure_context()}")
        line = line.rstrip("\r\n")
        if line.startswith("ERR\t"):
            raise RuntimeError(f"{line}\n{self._failure_context()}")
        return line

    def wait(self, timeout: float | None = None) -> int:
        rc = self.proc.wait(timeout=timeout)
        self._stderr_thread.join(timeout=1.0)
        return rc

    def _terminate_best_effort(self) -> None:
        try:
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait(timeout=2)
        except Exception:
            pass

    def close(self) -> None:
        self._terminate_best_effort()
        try:
            if self.proc.stdin is not None:
                self.proc.stdin.close()
        except Exception:
            pass
        try:
            if self.proc.stdout is not None:
                self.proc.stdout.close()
        except Exception:
            pass
        # Let the drain thread observe EOF before force-closing stderr.
        self._stderr_thread.join(timeout=1.0)
        try:
            if self.proc.stderr is not None:
                self.proc.stderr.close()
        except Exception:
            pass

    def __enter__(self) -> "WorkerProcess":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

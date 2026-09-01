from __future__ import annotations

import concurrent.futures
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from worker_process import WorkerProcess


class WorkerProcessTests(unittest.TestCase):
    def test_stderr_is_drained_while_waiting_for_stdout_reply(self):
        # This payload is deliberately much larger than a typical pipe buffer.
        # Without a concurrent stderr drain, the child blocks before printing OK.
        code = r'''
import sys
print("READY", flush=True)
for i in range(4096):
    sys.stderr.write(f"warning-{i:04d} " + ("x" * 512) + "\n")
sys.stderr.flush()
print("OK\tDONE", flush=True)
'''
        with WorkerProcess(
            [sys.executable, "-u", "-c", code],
            diagnostic_lines=8,
        ) as worker:
            self.assertEqual(worker.read_reply(), "READY")
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(worker.read_reply)
                self.assertEqual(future.result(timeout=5), "OK\tDONE")
            self.assertEqual(worker.wait(timeout=5), 0)
            diagnostics = worker.recent_diagnostics().splitlines()

        self.assertLessEqual(len(diagnostics), 8)
        self.assertTrue(any("warning-4095" in line for line in diagnostics))

    def test_unexpected_exit_reports_recent_stderr(self):
        code = r'''
import sys
print("fatal diagnostic", file=sys.stderr, flush=True)
'''
        with WorkerProcess([sys.executable, "-u", "-c", code]) as worker:
            with self.assertRaises(RuntimeError) as ctx:
                worker.read_reply()
        self.assertIn("fatal diagnostic", str(ctx.exception))
        self.assertIn("recent worker stderr", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

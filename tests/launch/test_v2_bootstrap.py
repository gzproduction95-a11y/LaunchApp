import importlib.util
import sys
import types
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2] / "PythonApps" / "Launch"


class V2BootstrapTests(unittest.TestCase):
    def test_logs_the_stage_when_startup_raises_and_preserves_original_exception(self):
        logs = []
        matrixos = types.SimpleNamespace(
            Logging=types.SimpleNamespace(info=lambda *args: logs.append(args)))

        def fail_startup():
            raise RuntimeError("simulated device startup failure")

        saved = {name: sys.modules.get(name) for name in
                 ("MatrixOS", "main_v2", "launch_bootstrap_test")}
        sys.modules["MatrixOS"] = matrixos
        sys.modules["main_v2"] = types.SimpleNamespace(startup=fail_startup)
        try:
            spec = importlib.util.spec_from_file_location(
                "launch_bootstrap_test", APP_DIR / "bootstrap_v2.py")
            module = importlib.util.module_from_spec(spec)
            with self.assertRaisesRegex(RuntimeError, "simulated device startup failure"):
                spec.loader.exec_module(module)
        finally:
            for name, previous in saved.items():
                if previous is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = previous

        self.assertTrue(any("startup" in str(args) and "RuntimeError" in str(args)
                            for args in logs), logs)

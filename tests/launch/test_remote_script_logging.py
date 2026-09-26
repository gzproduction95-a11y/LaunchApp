import importlib
import unittest

launch_module = importlib.import_module("RemoteScripts.Launch")


class FakeControlSurface:
    def __init__(self, live):
        self._c_instance = live

    def schedule_message(self, *_args):
        pass


class FakeLiveInstance:
    def __init__(self, has_logger=True):
        self.logs = []
        if has_logger:
            self.log_message = self.logs.append


class RemoteScriptLoggingTests(unittest.TestCase):
    def test_launch_initializes_and_logs_using_live_c_instance(self):
        live = FakeLiveInstance()
        original_bases = launch_module.Launch.__bases__
        launch_module.Launch.__bases__ = (FakeControlSurface,)
        try:
            launch_module.create_instance(live)
        finally:
            launch_module.Launch.__bases__ = original_bases

        self.assertEqual(live.logs, ["Launch Remote Script initialized"])

    def test_missing_optional_logger_does_not_abort_initialization(self):
        live = FakeLiveInstance(has_logger=False)
        original_bases = launch_module.Launch.__bases__
        launch_module.Launch.__bases__ = (FakeControlSurface,)
        try:
            launch_module.create_instance(live)
        finally:
            launch_module.Launch.__bases__ = original_bases


if __name__ == "__main__":
    unittest.main()

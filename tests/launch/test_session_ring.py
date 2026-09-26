import importlib
import unittest

launch_module = importlib.import_module("RemoteScripts.Launch")


class FakeControlSurface:
    def __init__(self, live):
        self._c_instance = live
        self.registered_components = []

    def component_guard(self):
        from contextlib import nullcontext
        return nullcontext()

    def _register_component(self, component):
        self.registered_components.append(component)

    def schedule_message(self, *_args):
        pass


class FakeLiveInstance:
    def __init__(self):
        self.logs = []
        self.highlights = []

    def log_message(self, message):
        self.logs.append(message)

    def set_session_highlight(self, *args):
        self.highlights.append(args)


class FakeSessionRing:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.offsets = None

    def set_offsets(self, track_offset, scene_offset):
        self.offsets = (track_offset, scene_offset)


class SessionRingTests(unittest.TestCase):
    def test_creates_registers_and_shows_fixed_eight_by_eight_session_ring(self):
        live = FakeLiveInstance()
        constructed = []

        def make_ring(**kwargs):
            ring = FakeSessionRing(**kwargs)
            constructed.append(ring)
            return ring

        original_bases = launch_module.Launch.__bases__
        original_ring = getattr(launch_module, "SessionRingComponent", None)
        launch_module.Launch.__bases__ = (FakeControlSurface,)
        launch_module.SessionRingComponent = make_ring
        try:
            surface = launch_module.create_instance(live)
            self.assertEqual(len(constructed), 1)
            ring = constructed[0]
            self.assertEqual(ring.kwargs["num_tracks"], 8)
            self.assertEqual(ring.kwargs["num_scenes"], 8)
            self.assertEqual(ring.offsets, (0, 0))
            self.assertEqual(surface.registered_components, [ring])
            self.assertEqual(ring.kwargs["set_session_highlight"], surface._set_session_highlight)

            ring.kwargs["set_session_highlight"](0, 0, 8, 8, True)
            self.assertEqual(live.highlights, [(0, 0, 8, 8, True)])
        finally:
            launch_module.Launch.__bases__ = original_bases
            if original_ring is None:
                del launch_module.SessionRingComponent
            else:
                launch_module.SessionRingComponent = original_ring


if __name__ == "__main__":
    unittest.main()

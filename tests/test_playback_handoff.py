import unittest

from kodi_stubs import install

install()

from resources.lib import atv  # noqa: E402


class RecordingMonitor:
    def __init__(self, events):
        self.events = events

    def waitForAbort(self, timeout):
        self.events.append(("wait", timeout))
        return False

    def abortRequested(self):
        return False


class StoppedPlayer:
    def __init__(self, owner, events, stop_after_plays):
        self.owner = owner
        self.events = events
        self.stop_after_plays = stop_after_plays
        self.play_count = 0

    def play(self, item, windowed=False):
        self.play_count += 1
        self.events.append(("play", item, windowed))
        if self.play_count >= self.stop_after_plays:
            self.owner.active = False

    def isPlaying(self):
        self.events.append(("isPlaying", False))
        return False


class PlaybackHandoffContractTests(unittest.TestCase):
    def make_screensaver(self, playlist_items, stop_after_plays):
        events = []
        subject = object.__new__(atv.Screensaver)
        subject.active = True
        subject.video_playlist = playlist_items
        subject.atv4player = StoppedPlayer(subject, events, stop_after_plays)
        return subject, events

    def test_waits_before_observing_stop_and_requesting_successor(self):
        subject, events = self.make_screensaver(["first.mov", "second.mov"], 2)
        original_monitor = atv.monitor
        atv.monitor = RecordingMonitor(events)
        try:
            subject.start_playback()
        finally:
            atv.monitor = original_monitor

        self.assertEqual([
            ("play", "first.mov", True),
            ("wait", 1),
            ("isPlaying", False),
            ("play", "second.mov", True),
        ], events)

    def test_cycles_the_once_randomized_session_order(self):
        subject, events = self.make_screensaver(["first.mov", "second.mov"], 3)
        original_monitor = atv.monitor
        atv.monitor = RecordingMonitor(events)
        try:
            subject.start_playback()
        finally:
            atv.monitor = original_monitor

        played_items = [event[1] for event in events if event[0] == "play"]
        self.assertEqual(["first.mov", "second.mov", "first.mov"], played_items)


if __name__ == "__main__":
    unittest.main()

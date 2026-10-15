import unittest
from unittest.mock import patch

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


class RecordingDiagnostics:
    def __init__(self):
        self.events = []

    def record(self, event, **fields):
        self.events.append((event, fields))


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
        subject.transition_diagnostics = RecordingDiagnostics()
        return subject, events, subject.transition_diagnostics.events

    def test_waits_before_observing_stop_and_requesting_successor(self):
        subject, events, diagnostic_events = self.make_screensaver(
            ["first.mov", "second.mov"], 2
        )
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
        self.assertEqual([
            ("playback-loop-start", {"playlist_count": 2}),
            ("play-requested", {"index": 0, "source": "local"}),
            ("play-returned", {"index": 0}),
            ("stopped-observed", {"index": 0}),
            ("play-requested", {"index": 1, "source": "local"}),
            ("play-returned", {"index": 1}),
        ], diagnostic_events)

    def test_cycles_the_once_randomized_session_order(self):
        subject, events, _ = self.make_screensaver(
            ["first.mov", "second.mov"], 3
        )
        original_monitor = atv.monitor
        atv.monitor = RecordingMonitor(events)
        try:
            subject.start_playback()
        finally:
            atv.monitor = original_monitor

        played_items = [event[1] for event in events if event[0] == "play"]
        self.assertEqual(["first.mov", "second.mov", "first.mov"], played_items)

    def test_player_callbacks_are_recorded_without_controlling_playback(self):
        diagnostics = RecordingDiagnostics()
        player = atv.TransitionPlayer(diagnostics)

        player.onAVStarted()
        player.onPlayBackEnded()
        player.onPlayBackStopped()
        player.onPlayBackError()

        self.assertEqual([
            ("av-started", {}),
            ("playback-ended", {}),
            ("playback-stopped", {}),
            ("playback-error", {}),
        ], diagnostics.events)

    def test_source_classification_does_not_log_the_media_location(self):
        self.assertEqual("stream", atv.playback_source("https://example.test/a.mov"))
        self.assertEqual("stream", atv.playback_source("http://example.test/a.mov"))
        self.assertEqual("local", atv.playback_source("/storage/aerials/a.mov"))

    def test_diagnostics_emit_a_parseable_monotonic_timeline(self):
        timestamps = iter([1_000_000_000, 1_250_000_000])
        diagnostics = atv.TransitionDiagnostics(clock=lambda: next(timestamps))

        with patch.object(atv.xbmc, "log") as kodi_log:
            diagnostics.record("play-requested", index=4, source="stream")

        kodi_log.assert_called_once_with(
            msg=(
                "[Aerial transition] seq=1 elapsed_ms=250.000 "
                "event=play-requested index=4 source=stream"
            ),
            level=atv.xbmc.LOGINFO,
        )


if __name__ == "__main__":
    unittest.main()

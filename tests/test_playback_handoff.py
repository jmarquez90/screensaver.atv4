"""
   Copyright (C) 2026 Jeremiah Steven Marquez <jmarquez90@gmail.com>
   This file is part of screensaver.atv4 - https://github.com/enen92/screensaver.atv4

   SPDX-License-Identifier: GPL-2.0-only
   See LICENSE for more information.
"""

import unittest
from unittest.mock import Mock, patch

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
        self.active_item = None
        self.listitem = None

    def set_active_item(self, item, playback_target=None):
        self.active_item = item
        self.playback_target = playback_target or item

    def play(self, item, listitem=None, windowed=False):
        self.play_count += 1
        self.listitem = listitem
        self.events.append(("play", item, windowed))
        if self.play_count >= self.stop_after_plays:
            self.owner.active = False

    def isPlaying(self):
        self.events.append(("isPlaying", False))
        return False

    def record_progress_sample(self):
        raise AssertionError("progress must not be sampled after playback stops")


class PlaybackHandoffContractTests(unittest.TestCase):
    def make_screensaver(self, playlist_items, stop_after_plays):
        events = []
        subject = object.__new__(atv.Screensaver)
        subject.active = True
        subject.video_playlist = playlist_items
        subject.overlay_requested = False
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
            ("play-requested", {
                "asset_id": atv.playback_asset_id("first.mov"),
                "index": 0,
                "source": "local",
            }),
            ("play-returned", {
                "asset_id": atv.playback_asset_id("first.mov"),
                "index": 0,
            }),
            ("stopped-observed", {
                "asset_id": atv.playback_asset_id("first.mov"),
                "index": 0,
            }),
            ("play-requested", {
                "asset_id": atv.playback_asset_id("second.mov"),
                "index": 1,
                "source": "local",
            }),
            ("play-returned", {
                "asset_id": atv.playback_asset_id("second.mov"),
                "index": 1,
            }),
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

    def test_direct_fallback_starts_fullscreen_when_overlay_is_requested(self):
        subject, events, _ = self.make_screensaver(["first.mov"], 1)
        subject.overlay_requested = True

        subject.start_direct_playback()

        self.assertIn(("play", "first.mov", False), events)

    def test_continuous_transport_starts_fullscreen_when_overlay_is_requested(self):
        subject, events, _ = self.make_screensaver(["first.mov"], 1)
        subject.overlay_requested = True
        continuous_stream = Mock()
        continuous_stream.start.return_value = "udp://127.0.0.1:12345"

        subject.start_continuous_playback(continuous_stream)

        self.assertIn(("play", "udp://127.0.0.1:12345", False), events)
        self.assertEqual("udp://127.0.0.1:12345", subject.atv4player.listitem.path)
        self.assertEqual("video/mp2t", subject.atv4player.listitem.mime_type)
        self.assertFalse(subject.atv4player.listitem.content_lookup)

    def test_continuous_transport_stays_windowed_without_an_overlay(self):
        subject, events, _ = self.make_screensaver(["first.mov"], 1)
        subject.overlay_requested = False
        continuous_stream = Mock()
        continuous_stream.start.return_value = "udp://127.0.0.1:12345"

        subject.start_continuous_playback(continuous_stream)

        self.assertIn(("play", "udp://127.0.0.1:12345", True), events)

    def test_ignores_duplicate_init_after_fullscreen_video_exits(self):
        subject = object.__new__(atv.Screensaver)
        subject.atv4player = Mock()
        subject.transition_diagnostics = RecordingDiagnostics()

        subject.onInit()

        self.assertEqual([
            ("duplicate-init-ignored", {}),
        ], subject.transition_diagnostics.events)

    def test_fullscreen_exit_stops_the_continuous_session(self):
        subject = object.__new__(atv.Screensaver)
        subject.active = True
        subject.video_playlist = ["first.mov"]
        subject.overlay_requested = True
        subject.atv4player = Mock()
        subject.atv4player.isPlaying.return_value = True
        subject.transition_diagnostics = RecordingDiagnostics()
        subject.clearAll = Mock()
        continuous_stream = Mock()
        continuous_stream.start.return_value = "udp://@127.0.0.1:12345"

        fullscreen_states = iter([False, True, False])
        with patch.object(
            atv.xbmc,
            "getCondVisibility",
            side_effect=lambda _condition: next(fullscreen_states),
            create=True,
        ):
            original_monitor = atv.monitor
            atv.monitor = RecordingMonitor([])
            try:
                subject.start_continuous_playback(continuous_stream)
            finally:
                atv.monitor = original_monitor

        subject.clearAll.assert_called_once_with()
        self.assertIn(
            ("fullscreen-exited", {}),
            subject.transition_diagnostics.events,
        )

    def test_prefers_continuous_transport_when_ffmpeg_is_available(self):
        subject, _, _ = self.make_screensaver(["first.mov", "second.mov"], 1)
        continuous_stream = Mock()
        continuous_stream.is_available.return_value = True
        subject.start_continuous_playback = Mock()
        subject.start_direct_playback = Mock()

        with patch.object(atv, "ContinuousStream", return_value=continuous_stream):
            subject.start_playback()

        subject.start_continuous_playback.assert_called_once_with(continuous_stream)
        subject.start_direct_playback.assert_not_called()

    def test_intentional_shutdown_does_not_start_direct_fallback(self):
        subject, _, _ = self.make_screensaver(["first.mov", "second.mov"], 1)
        continuous_stream = Mock()
        continuous_stream.is_available.return_value = True
        subject.start_direct_playback = Mock()

        def stop_during_continuous_playback(_stream):
            subject.active = False
            raise RuntimeError("continuous FFmpeg process exited")

        subject.start_continuous_playback = stop_during_continuous_playback

        with patch.object(atv, "ContinuousStream", return_value=continuous_stream):
            subject.start_playback()

        continuous_stream.stop.assert_called_once_with()
        subject.start_direct_playback.assert_not_called()

    def test_shutdown_closes_overlay_and_stops_playback_resources(self):
        subject = object.__new__(atv.Screensaver)
        subject.active = True
        subject.overlay_window = Mock()
        subject.atv4player = Mock()
        subject.continuous_stream = Mock()
        subject.close = Mock()

        overlay_window = subject.overlay_window
        subject.clearAll()

        self.assertFalse(subject.active)
        self.assertIsNone(subject.overlay_window)
        overlay_window.close.assert_called_once_with()
        subject.atv4player.stop.assert_called_once_with()
        subject.continuous_stream.stop.assert_called_once_with()
        subject.close.assert_called_once_with()

    def test_external_playback_cleanup_does_not_stop_the_new_movie(self):
        subject = object.__new__(atv.Screensaver)
        subject.active = True
        subject.overlay_window = Mock()
        subject.atv4player = Mock()
        subject.continuous_stream = Mock()
        subject.close = Mock()

        overlay_window = subject.overlay_window
        subject.clearAll(stop_player=False)

        self.assertFalse(subject.active)
        self.assertIsNone(subject.overlay_window)
        overlay_window.close.assert_called_once_with()
        subject.atv4player.stop.assert_not_called()
        subject.continuous_stream.stop.assert_called_once_with()
        subject.close.assert_called_once_with()

    def test_player_callbacks_are_recorded_without_controlling_playback(self):
        diagnostics = RecordingDiagnostics()
        player = atv.TransitionPlayer(diagnostics)
        player.set_active_item("https://example.test/a.mov")
        asset_id = atv.playback_asset_id("https://example.test/a.mov")

        player.onAVStarted()
        player.onPlayBackEnded()
        player.onPlayBackStopped()
        player.onPlayBackError()

        self.assertEqual([
            ("av-started", {"asset_id": asset_id}),
            ("playback-ended", {"asset_id": asset_id}),
            ("playback-stopped", {"asset_id": asset_id}),
            ("playback-error", {"asset_id": asset_id}),
        ], diagnostics.events)

    def test_av_start_opens_the_live_overlay(self):
        show_overlay = Mock()
        player = atv.TransitionPlayer(
            RecordingDiagnostics(),
            show_overlay,
        )

        player.onAVStarted()

        show_overlay.assert_called_once_with()

    def test_player_recognizes_its_current_playback_target(self):
        player = atv.TransitionPlayer(RecordingDiagnostics())
        player.set_active_item(
            "continuous-stream.ts",
            playback_target="udp://127.0.0.1:12345",
        )
        player.getPlayingFile = lambda: "udp://127.0.0.1:12345"

        self.assertTrue(player.owns_current_playback())

    def test_player_rejects_an_external_playback_target(self):
        player = atv.TransitionPlayer(RecordingDiagnostics())
        player.set_active_item(
            "continuous-stream.ts",
            playback_target="udp://127.0.0.1:12345",
        )
        player.getPlayingFile = lambda: "plugin://example/movie/42"

        self.assertFalse(player.owns_current_playback())

    def test_owned_av_start_presents_the_overlay(self):
        subject = object.__new__(atv.Screensaver)
        subject.active = True
        subject.overlay_requested = True
        subject.atv4player = Mock()
        subject.atv4player.owns_current_playback.return_value = True
        subject._present_playback = Mock()
        subject.clearAll = Mock()

        subject._handle_av_started()

        subject._present_playback.assert_called_once_with()
        subject.clearAll.assert_not_called()

    def test_external_av_start_releases_screensaver_without_stopping_movie(self):
        subject = object.__new__(atv.Screensaver)
        subject.active = True
        subject.overlay_requested = True
        subject.atv4player = Mock()
        subject.atv4player.owns_current_playback.return_value = False
        subject.atv4player.isPlayingVideo.return_value = True
        subject.transition_diagnostics = RecordingDiagnostics()
        subject._present_playback = Mock()
        subject.clearAll = Mock()

        with patch.object(atv.xbmc, "executebuiltin") as execute_builtin:
            subject._handle_av_started()

        subject._present_playback.assert_not_called()
        subject.clearAll.assert_called_once_with(stop_player=False)
        execute_builtin.assert_called_once_with(
            "ActivateWindow(fullscreenvideo)"
        )
        self.assertEqual([
            ("external-playback-detected", {}),
            ("external-video-presented", {}),
        ], subject.transition_diagnostics.events)

    def test_external_audio_does_not_activate_fullscreen_video(self):
        subject = object.__new__(atv.Screensaver)
        subject.active = True
        subject.overlay_requested = True
        subject.atv4player = Mock()
        subject.atv4player.owns_current_playback.return_value = False
        subject.atv4player.isPlayingVideo.return_value = False
        subject.transition_diagnostics = RecordingDiagnostics()
        subject._present_playback = Mock()
        subject.clearAll = Mock()

        with patch.object(atv.xbmc, "executebuiltin") as execute_builtin:
            subject._handle_av_started()

        subject._present_playback.assert_not_called()
        subject.clearAll.assert_called_once_with(stop_player=False)
        execute_builtin.assert_not_called()
        self.assertEqual([
            ("external-playback-detected", {}),
        ], subject.transition_diagnostics.events)

    def test_presentation_enters_fullscreen_before_opening_overlay(self):
        subject = object.__new__(atv.Screensaver)
        subject.active = True
        subject._show_overlays = Mock()
        subject.transition_diagnostics = RecordingDiagnostics()
        events = []

        with patch.object(
            atv.xbmc,
            "getCondVisibility",
            side_effect=[False, False, True],
        ), patch.object(atv.xbmc, "executebuiltin") as execute_builtin:
            original_monitor = atv.monitor
            atv.monitor = RecordingMonitor(events)
            try:
                subject._present_playback()
            finally:
                atv.monitor = original_monitor

        execute_builtin.assert_called_once_with("Action(FullScreen)")
        self.assertEqual([("wait", 0.05)], events)
        subject._show_overlays.assert_called_once_with()
        self.assertEqual([
            ("fullscreen-entry-requested", {}),
            ("fullscreen-entered", {}),
        ], subject.transition_diagnostics.events)

    def test_presentation_opens_overlay_without_toggling_when_already_fullscreen(self):
        subject = object.__new__(atv.Screensaver)
        subject.active = True
        subject._show_overlays = Mock()
        subject.transition_diagnostics = RecordingDiagnostics()

        with patch.object(
            atv.xbmc,
            "getCondVisibility",
            return_value=True,
        ), patch.object(atv.xbmc, "executebuiltin") as execute_builtin:
            subject._present_playback()

        execute_builtin.assert_not_called()
        subject._show_overlays.assert_called_once_with()
        self.assertEqual([
            ("fullscreen-entered", {}),
        ], subject.transition_diagnostics.events)

    def test_overlay_actions_close_the_entire_screensaver(self):
        overlay = object.__new__(atv.OverlayWindow)
        overlay.exit_callback = Mock()

        overlay.onAction(Mock())

        overlay.exit_callback.assert_called_once_with()

    def test_any_main_window_action_unlocks_and_closes_screensaver(self):
        subject = object.__new__(atv.Screensaver)
        subject.clearAll = Mock()
        atv.addon.setSettingBool("is_locked", True)

        subject.onAction(Mock())

        self.assertFalse(atv.addon.getSettingBool("is_locked"))
        subject.clearAll.assert_called_once_with()

    def test_native_screensaver_deactivation_closes_aerial(self):
        subject = object.__new__(atv.Screensaver)
        subject.active = True
        subject.transition_diagnostics = RecordingDiagnostics()
        subject.clearAll = Mock()

        subject._handle_screensaver_deactivated()

        subject.clearAll.assert_called_once_with()
        self.assertEqual([
            ("screensaver-deactivated", {}),
        ], subject.transition_diagnostics.events)

    def test_late_native_deactivation_is_ignored_after_cleanup(self):
        subject = object.__new__(atv.Screensaver)
        subject.active = False
        subject.transition_diagnostics = RecordingDiagnostics()
        subject.clearAll = Mock()

        subject._handle_screensaver_deactivated()

        subject.clearAll.assert_not_called()
        self.assertEqual([], subject.transition_diagnostics.events)

    def test_screensaver_run_releases_lock_after_window_closes(self):
        window = Mock()
        atv.addon.setSettingBool("is_locked", False)

        with patch.object(atv, "Screensaver", return_value=window):
            atv.run()

        window.doModal.assert_called_once_with()
        self.assertFalse(atv.addon.getSettingBool("is_locked"))

    def test_screensaver_run_releases_lock_after_window_error(self):
        window = Mock()
        window.doModal.side_effect = RuntimeError("window failed")
        atv.addon.setSettingBool("is_locked", False)

        with patch.object(atv, "Screensaver", return_value=window):
            with self.assertRaises(RuntimeError):
                atv.run()

        self.assertFalse(atv.addon.getSettingBool("is_locked"))

    def test_source_classification_does_not_log_the_media_location(self):
        self.assertEqual("stream", atv.playback_source("https://example.test/a.mov"))
        self.assertEqual("stream", atv.playback_source("http://example.test/a.mov"))
        self.assertEqual("local", atv.playback_source("/storage/aerials/a.mov"))

    def test_asset_id_matches_stream_and_cached_copy_without_exposing_location(self):
        stream = "https://example.test/private/path/A%20Scene.mov?token=secret"
        cached = "/storage/aerial-cache/A Scene.mov"

        self.assertEqual(atv.playback_asset_id(stream), atv.playback_asset_id(cached))
        self.assertNotIn("A Scene", atv.playback_asset_id(stream))
        self.assertEqual(16, len(atv.playback_asset_id(stream)))

    def test_progress_sampling_is_bounded_and_records_player_time(self):
        diagnostics = RecordingDiagnostics()
        player = atv.TransitionPlayer(diagnostics)
        player.set_active_item("https://example.test/a.mov")
        player.isPlayingVideo = lambda: True
        player.getTime = lambda: 2.5
        player.getTotalTime = lambda: 189.0

        player.onAVStarted()
        for _ in range(player.progress_sample_limit + 1):
            player.record_progress_sample()

        progress = [event for event in diagnostics.events
                    if event[0] == "playback-progress"]
        self.assertEqual(player.progress_sample_limit, len(progress))
        self.assertEqual({
            "asset_id": atv.playback_asset_id("https://example.test/a.mov"),
            "sample": 0,
            "time_s": "2.500",
            "total_s": "189.000",
            "video": "true",
        }, progress[0][1])

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

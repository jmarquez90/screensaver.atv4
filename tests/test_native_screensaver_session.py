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

from resources.lib import screensaver  # noqa: E402


class NativeScreensaverSessionTests(unittest.TestCase):
    def test_session_launches_aerial_without_synthetic_input(self):
        exit_monitor = Mock()
        exit_monitor.deactivated = True

        with patch.object(
            screensaver.NativeScreensaverSession,
            "ExitMonitor",
            return_value=exit_monitor,
        ), patch.object(
            screensaver.ScreensaverPreview,
            "runAddon",
        ) as run_addon, patch.object(
            screensaver.ScreensaverPreview,
            "send_input",
        ) as send_input:
            screensaver.NativeScreensaverSession.run()

        run_addon.assert_called_once_with()
        send_input.assert_not_called()

    def test_session_waits_for_native_deactivation(self):
        exit_monitor = Mock()
        exit_monitor.deactivated = False

        def deactivate(_timeout):
            exit_monitor.deactivated = True
            return False

        exit_monitor.waitForAbort.side_effect = deactivate
        exit_monitor.abortRequested.return_value = False

        with patch.object(
            screensaver.NativeScreensaverSession,
            "ExitMonitor",
            return_value=exit_monitor,
        ), patch.object(
            screensaver.ScreensaverPreview,
            "runAddon",
        ):
            screensaver.NativeScreensaverSession.run()

        exit_monitor.waitForAbort.assert_called_once_with(0.1)


if __name__ == "__main__":
    unittest.main()

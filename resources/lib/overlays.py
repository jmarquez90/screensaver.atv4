"""
   Copyright (C) 2026 Jeremiah Steven Marquez <jmarquez90@gmail.com>
   This file is part of screensaver.atv4 - https://github.com/enen92/screensaver.atv4

   SPDX-License-Identifier: GPL-2.0-only
   See LICENSE for more information.
"""


TIME_CONTROL_ID = 32510
DATE_CONTROL_ID = 32511
WEATHER_CONTROL_ID = 32512


def configure_overlays(window, settings):
    """Apply opt-in visibility while Kodi owns the displayed information."""
    visibility = {
        TIME_CONTROL_ID: settings.getSettingBool("show-time-overlay"),
        DATE_CONTROL_ID: settings.getSettingBool("show-date-overlay"),
        WEATHER_CONTROL_ID: settings.getSettingBool("show-weather-overlay"),
    }
    for control_id, visible in visibility.items():
        window.getControl(control_id).setVisible(visible)
    return visibility

"""
   Copyright (C) 2026 Jeremiah Steven Marquez <jmarquez90@gmail.com>
   This file is part of screensaver.atv4 - https://github.com/enen92/screensaver.atv4

   SPDX-License-Identifier: GPL-2.0-only
   See LICENSE for more information.
"""

import unittest
from pathlib import Path
from xml.etree import ElementTree

from resources.lib.overlays import (
    DATE_CONTROL_ID,
    TIME_CONTROL_ID,
    WEATHER_CONTROL_ID,
    configure_overlays,
)


class FakeControl:
    def __init__(self):
        self.visible = None

    def setVisible(self, visible):
        self.visible = visible


class FakeWindow:
    def __init__(self):
        self.controls = {
            TIME_CONTROL_ID: FakeControl(),
            DATE_CONTROL_ID: FakeControl(),
            WEATHER_CONTROL_ID: FakeControl(),
        }

    def getControl(self, control_id):
        return self.controls[control_id]


class FakeSettings:
    def __init__(self, **values):
        self.values = values

    def getSettingBool(self, setting_id):
        return self.values.get(setting_id, False)


class NativeOverlayTests(unittest.TestCase):
    def test_overlays_are_opt_in_and_independent(self):
        window = FakeWindow()
        visibility = configure_overlays(
            window,
            FakeSettings(**{
                "show-time-overlay": True,
                "show-date-overlay": False,
                "show-weather-overlay": True,
            }),
        )

        self.assertEqual({
            TIME_CONTROL_ID: True,
            DATE_CONTROL_ID: False,
            WEATHER_CONTROL_ID: True,
        }, visibility)
        self.assertTrue(window.controls[TIME_CONTROL_ID].visible)
        self.assertFalse(window.controls[DATE_CONTROL_ID].visible)
        self.assertTrue(window.controls[WEATHER_CONTROL_ID].visible)

    def test_missing_settings_keep_both_overlays_hidden(self):
        window = FakeWindow()
        configure_overlays(window, FakeSettings())

        self.assertFalse(window.controls[TIME_CONTROL_ID].visible)
        self.assertFalse(window.controls[DATE_CONTROL_ID].visible)
        self.assertFalse(window.controls[WEATHER_CONTROL_ID].visible)

    def test_public_settings_are_opt_in(self):
        root = Path(__file__).resolve().parents[1]
        settings = ElementTree.parse(root / "resources" / "settings.xml")
        defaults = {
            node.attrib["id"]: node.findtext("default")
            for node in settings.findall(".//setting")
            if node.attrib.get("id") in {
                "show-time-overlay",
                "show-date-overlay",
                "show-weather-overlay",
            }
        }

        self.assertEqual({
            "show-time-overlay": "false",
            "show-date-overlay": "false",
            "show-weather-overlay": "false",
        }, defaults)

    def test_both_layouts_use_kodi_native_labels(self):
        root = Path(__file__).resolve().parents[1]
        for resolution in ("720p", "1080i"):
            layout = ElementTree.parse(
                root / "resources" / "skins" / "default" / resolution
                / "screensaver-atv4.xml"
            )
            labels = {
                int(control.attrib["id"]): control.findtext("label")
                for control in layout.findall(".//control")
                if control.attrib.get("id") in {
                    str(TIME_CONTROL_ID),
                    str(DATE_CONTROL_ID),
                    str(WEATHER_CONTROL_ID),
                }
            }

            self.assertEqual({
                TIME_CONTROL_ID: "$INFO[System.Time]",
                DATE_CONTROL_ID: "$INFO[System.Date]",
                WEATHER_CONTROL_ID: (
                    "$INFO[Weather.Temperature]"
                    "$INFO[Weather.Conditions,  ·  ]"
                ),
            }, labels)


if __name__ == "__main__":
    unittest.main()

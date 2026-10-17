"""
   Copyright (C) 2026 Jeremiah Steven Marquez <jmarquez90@gmail.com>
   This file is part of screensaver.atv4 - https://github.com/enen92/screensaver.atv4

   SPDX-License-Identifier: GPL-2.0-only
   See LICENSE for more information.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree

from resources.lib.overlays import (
    ass_document,
    create_overlay_subtitle,
    overlay_lines,
    overlays_enabled,
    remove_overlay_subtitle,
)


class FakeSettings:
    def __init__(self, **values):
        self.values = values

    def getSettingBool(self, setting_id):
        return self.values.get(setting_id, False)


INFO_LABELS = {
    "System.Time": "9:42 PM",
    "System.Date": "Thursday, October 16, 2026",
    "Weather.Temperature": "68°F",
    "Weather.Conditions": "Mainly Sunny",
}


class NativeOverlayTests(unittest.TestCase):
    def test_overlays_capture_only_enabled_kodi_labels(self):
        lines = overlay_lines(
            FakeSettings(**{
                "show-time-overlay": True,
                "show-date-overlay": False,
                "show-weather-overlay": True,
            }),
            INFO_LABELS.__getitem__,
        )

        self.assertEqual([
            ("weather", "68°F  ·  Mainly Sunny"),
            ("time", "9:42 PM"),
        ], lines)

    def test_missing_settings_create_no_overlay(self):
        self.assertFalse(overlays_enabled(FakeSettings()))
        self.assertEqual([], overlay_lines(FakeSettings(), INFO_LABELS.__getitem__))

    def test_overlay_is_enabled_when_any_setting_is_enabled(self):
        self.assertTrue(overlays_enabled(FakeSettings(**{
            "show-date-overlay": True,
        })))

    def test_ass_document_is_bottom_right_and_long_lived(self):
        document = ass_document([
            ("weather", "68°F"),
            ("time", "9:42 PM"),
            ("date", "October 16"),
        ])

        self.assertIn("Style: Aerial,Arial,34", document)
        self.assertIn(",3,80,80,80,1", document)
        self.assertIn("9:59:59.99", document)
        self.assertIn(
            r"{\fs34}68°F\N{\fs52}9:42 PM\N{\fs34}October 16",
            document,
        )

    def test_subtitle_file_is_written_and_removed(self):
        with TemporaryDirectory() as directory:
            path = create_overlay_subtitle(
                FakeSettings(**{
                    "show-time-overlay": True,
                    "show-date-overlay": True,
                    "show-weather-overlay": True,
                }),
                INFO_LABELS.__getitem__,
                directory=directory,
            )
            subtitle = Path(path)

            self.assertGreater(subtitle.stat().st_size, 0)
            content = subtitle.read_text(encoding="utf-8")
            self.assertIn("Mainly Sunny", content)
            self.assertIn("9:42 PM", content)
            self.assertIn("Thursday, October 16, 2026", content)

            remove_overlay_subtitle(path)
            self.assertFalse(subtitle.exists())

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

    def test_main_video_layouts_remain_free_of_overlay_labels(self):
        root = Path(__file__).resolve().parents[1]
        for resolution in ("720p", "1080i"):
            layout = ElementTree.parse(
                root / "resources" / "skins" / "default" / resolution
                / "screensaver-atv4.xml"
            )
            controls = layout.findall(".//control")
            labels = [control.findtext("label", "") for control in controls]

            self.assertTrue(any(
                control.attrib.get("type") == "videowindow"
                for control in controls
            ))
            self.assertFalse(any(
                "System.Time" in label
                or "System.Date" in label
                or "Weather." in label
                for label in labels
            ))


if __name__ == "__main__":
    unittest.main()

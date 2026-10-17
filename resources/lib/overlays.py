"""
   Copyright (C) 2026 Jeremiah Steven Marquez <jmarquez90@gmail.com>
   This file is part of screensaver.atv4 - https://github.com/enen92/screensaver.atv4

   SPDX-License-Identifier: GPL-2.0-only
   See LICENSE for more information.
"""

import os
import tempfile


TIME_SETTING = "show-time-overlay"
DATE_SETTING = "show-date-overlay"
WEATHER_SETTING = "show-weather-overlay"


def _ass_escape(value):
    return str(value).replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")


def overlay_lines(settings, get_info_label):
    """Capture enabled values from Kodi without owning their source data."""
    lines = []
    if settings.getSettingBool(WEATHER_SETTING):
        weather = [
            get_info_label("Weather.Temperature"),
            get_info_label("Weather.Conditions"),
        ]
        lines.append(("weather", "  ·  ".join(value for value in weather if value)))
    if settings.getSettingBool(TIME_SETTING):
        lines.append(("time", get_info_label("System.Time")))
    if settings.getSettingBool(DATE_SETTING):
        lines.append(("date", get_info_label("System.Date")))
    return [
        (kind, _ass_escape(line))
        for kind, line in lines
        if line
    ]


def overlays_enabled(settings):
    return any(settings.getSettingBool(setting_id) for setting_id in (
        TIME_SETTING,
        DATE_SETTING,
        WEATHER_SETTING,
    ))


def ass_document(lines):
    font_sizes = {"weather": 34, "time": 52, "date": 34}
    text = r"\N".join(
        r"{{\fs{}}}{}".format(font_sizes[kind], value)
        for kind, value in lines
    )
    return """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Aerial,Arial,34,&H00FFFFFF,&H000000FF,&HC0000000,&H00000000,0,0,0,0,100,100,0,0,1,2,1,3,80,80,80,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,9:59:59.99,Aerial,,0,0,0,,{}
""".format(text)


def create_overlay_subtitle(settings, get_info_label, directory=None):
    lines = overlay_lines(settings, get_info_label)
    if not lines:
        return None
    subtitle = tempfile.NamedTemporaryFile(
        mode="w",
        prefix="screensaver-atv4-overlay-",
        suffix=".ass",
        delete=False,
        dir=directory,
        encoding="utf-8",
        newline="\n",
    )
    try:
        subtitle.write(ass_document(lines))
        return subtitle.name
    finally:
        subtitle.close()


def remove_overlay_subtitle(path):
    if not path:
        return
    try:
        os.remove(path)
    except FileNotFoundError:
        pass

"""
   Copyright (C) 2015- enen92
   Copyright (C) 2026 Jeremiah Steven Marquez <jmarquez90@gmail.com>
   This file is part of screensaver.atv4 - https://github.com/enen92/screensaver.atv4

   SPDX-License-Identifier: GPL-2.0-only
   See LICENSE for more information.
"""

import xbmc
import xbmcgui

from .commonatv import translate, addon, addon_path, notification
from .trans import ScreensaverTrans


class ScreensaverPreview(xbmcgui.WindowXMLDialog):
    @staticmethod
    class ExitMonitor(xbmc.Monitor):

        def __init__(self, exit_callback):
            self.exit_callback = exit_callback

        def onScreensaverDeactivated(self):
            self.exit_callback()

    def onInit(self):
        self.exit_monitor = self.ExitMonitor(self.exit)
        self.getControl(32502).setLabel(translate(32025))
        self.setProperty("screensaver-atv4-loading", "true")
        self.runAddon()

    @staticmethod
    def send_input():
        xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "Input.ContextMenu", "id": 1}')

    @staticmethod
    def runAddon():
        xbmc.executebuiltin('RunAddon(screensaver.atv4)')

    def exit(self):
        self.clearProperty("screensaver-atv4-loading")
        self.close()


class NativeScreensaverSession:
    """Keep Kodi's screensaver lifecycle active while Aerial is running."""

    class ExitMonitor(xbmc.Monitor):
        def __init__(self):
            self.deactivated = False

        def onScreensaverDeactivated(self):
            self.deactivated = True

    @classmethod
    def run(cls):
        exit_monitor = cls.ExitMonitor()
        ScreensaverPreview.runAddon()
        while (
            not exit_monitor.deactivated
            and not exit_monitor.abortRequested()
        ):
            exit_monitor.waitForAbort(0.1)


def run():
    if not xbmc.getCondVisibility("Player.HasMedia"):
        if not addon.getSettingBool("is_locked"):
            if addon.getSettingBool("show-notifications"):
                notification(translate(32000), translate(32017))

            if addon.getSettingBool("show-previewwindow"):
                # Start window
                screensaver = ScreensaverPreview(
                    'screensaver-atv4.xml',
                    addon_path,
                    'default',
                    '',
                )
                screensaver.doModal()
                xbmc.sleep(100)
                del screensaver
            else:
                NativeScreensaverSession.run()

        else:
            # Transparent placeholder
            trans = ScreensaverTrans(
                'screensaver-atv4-trans.xml',
                addon_path,
                'default',
                '',
            )
            trans.doModal()
            xbmc.sleep(100)
            del trans
    else:
        # Just call deactivate
        ScreensaverPreview.send_input()

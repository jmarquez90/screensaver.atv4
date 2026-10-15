"""
   Copyright (C) 2015- enen92
   This file is part of screensaver.atv4 - https://github.com/enen92/screensaver.atv4

   SPDX-License-Identifier: GPL-2.0-only
   See LICENSE for more information.
"""

import json
import threading
import time

import xbmc
import xbmcgui

from .commonatv import translate, addon, addon_path
from .offline import offline
from .playlist import AtvPlaylist
from .trans import ScreensaverTrans

monitor = xbmc.Monitor()


class TransitionDiagnostics:
    """Emit a monotonic timeline without changing playback decisions."""

    log_prefix = "[Aerial transition]"

    def __init__(self, clock=time.monotonic_ns):
        self._clock = clock
        self._started_at = clock()
        self._sequence = 0
        self._lock = threading.Lock()

    def record(self, event, **fields):
        with self._lock:
            self._sequence += 1
            elapsed_ms = (self._clock() - self._started_at) / 1_000_000
            details = " ".join(
                f"{key}={value}" for key, value in sorted(fields.items())
            )
            message = (
                f"{self.log_prefix} seq={self._sequence} "
                f"elapsed_ms={elapsed_ms:.3f} event={event}"
            )
            if details:
                message = f"{message} {details}"
            xbmc.log(msg=message, level=xbmc.LOGINFO)


class TransitionPlayer(xbmc.Player):
    """Observe Kodi lifecycle callbacks for the transition timeline."""

    def __init__(self, diagnostics):
        super().__init__()
        self._diagnostics = diagnostics

    def onAVStarted(self):
        self._diagnostics.record("av-started")

    def onPlayBackEnded(self):
        self._diagnostics.record("playback-ended")

    def onPlayBackStopped(self):
        self._diagnostics.record("playback-stopped")

    def onPlayBackError(self):
        self._diagnostics.record("playback-error")


def playback_source(item):
    value = str(item).lower()
    if value.startswith(("http://", "https://")):
        return "stream"
    return "local"


class Screensaver(xbmcgui.WindowXML):

    def __init__(self, *args, **kwargs):
        self.DPMStime = json.loads(xbmc.executeJSONRPC(
            '{"jsonrpc":"2.0","method":"Settings.GetSettingValue","params":{"setting":"powermanagement.displaysoff"},"id":2}'))[
                            'result']['value'] * 60
        self.isDPMSactive = bool(self.DPMStime > 0)
        self.active = True
        self.atv4player = None
        self.transition_diagnostics = TransitionDiagnostics()
        self.video_playlist = AtvPlaylist().compute_playlist_array()
        xbmc.log(msg=f"kodi dpms time: {self.DPMStime}", level=xbmc.LOGDEBUG)
        xbmc.log(msg=f"kodi dpms active: {self.isDPMSactive}", level=xbmc.LOGDEBUG)

    def onInit(self):
        self.getControl(32502).setLabel(translate(32008))
        self.setProperty("screensaver-atv4-loading", "true")

        if self.video_playlist:
            self.setProperty("screensaver-atv4-loading", "false")
            self.atv4player = TransitionPlayer(self.transition_diagnostics)

            # Start player thread
            threading.Thread(target=self.start_playback).start()

            # DPMS logic
            self.max_allowed_time = None

            if self.isDPMSactive and addon.getSettingInt("check-dpms") == 1:
                self.max_allowed_time = self.DPMStime

            elif addon.getSettingInt("check-dpms") == 2:
                self.max_allowed_time = addon.getSettingInt("manual-dpms") * 60

            xbmc.log(msg=f"check dpms: {addon.getSetting('check-dpms')}",
                     level=xbmc.LOGDEBUG)
            xbmc.log(msg=f"before supervision: {self.max_allowed_time}",
                     level=xbmc.LOGDEBUG)

            if self.max_allowed_time:
                delta = 0
                while self.active:
                    if delta >= self.max_allowed_time:
                        self.activateDPMS()
                        break
                    monitor.waitForAbort(1)
                    delta += 1
        else:
            self.novideos()

    def activateDPMS(self):
        xbmc.log(msg="[Aerial Screensaver] Manually activating DPMS!", level=xbmc.LOGDEBUG)
        self.active = False

        # Take action on the video
        enable_window_placeholder = False
        if addon.getSettingInt("dpms-action") == 0:
            self.atv4player.pause()
        else:
            self.clearAll()
            enable_window_placeholder = True

        if addon.getSettingBool("toggle-displayoff") or addon.getSettingBool("toggle-cecoff"):
            monitor.waitForAbort(1)

        if addon.getSettingBool("toggle-displayoff"):
            try:
                xbmc.executebuiltin('ToggleDPMS')
            except Exception as e:
                xbmc.log(msg=f"[Aerial Screensaver] Failed to toggle DPMS: {e}",
                         level=xbmc.LOGDEBUG)

        if addon.getSetting("toggle-cecoff") == "true":
            try:
                xbmc.executebuiltin('CECStandby')
            except Exception as e:
                xbmc.log(msg=f"[Aerial Screensaver] Failed to toggle device off via CEC: {e}",
                         level=xbmc.LOGDEBUG)

        # Enable placeholder window
        if enable_window_placeholder:
            self.toTransparent()

    def novideos(self):
        self.setProperty("screensaver-atv4-loading", "false")
        self.getControl(32503).setLabel(translate(32048))
        self.getControl(32503).setVisible(True)

    @classmethod
    def toTransparent(cls):
        trans = ScreensaverTrans(
            'screensaver-atv4-trans.xml',
            addon_path,
            'default',
            '',
        )
        trans.doModal()
        xbmc.sleep(100)
        del trans

    def clearAll(self, close=True):
        self.active = False
        if self.atv4player:
            self.atv4player.stop()
        self.close()

    def onAction(self, action):
        addon.setSettingBool("is_locked", False)
        self.clearAll()

    def start_playback(self):
        self.playindex = 0
        self.transition_diagnostics.record(
            "playback-loop-start", playlist_count=len(self.video_playlist)
        )
        self.transition_diagnostics.record(
            "play-requested",
            index=self.playindex,
            source=playback_source(self.video_playlist[self.playindex]),
        )
        self.atv4player.play(self.video_playlist[self.playindex], windowed=True)
        self.transition_diagnostics.record("play-returned", index=self.playindex)
        while self.active and not monitor.abortRequested():
            monitor.waitForAbort(1)
            # If we finish playing the video
            if not self.atv4player.isPlaying() and self.active:
                self.transition_diagnostics.record(
                    "stopped-observed", index=self.playindex
                )
                # Increment the iterator used to access the array or reset to 0
                if self.playindex < len(self.video_playlist) - 1:
                    self.playindex += 1
                else:
                    self.playindex = 0
                # Using the updated iterator, start playing the next video
                self.transition_diagnostics.record(
                    "play-requested",
                    index=self.playindex,
                    source=playback_source(self.video_playlist[self.playindex]),
                )
                self.atv4player.play(self.video_playlist[self.playindex], windowed=True)
                self.transition_diagnostics.record("play-returned", index=self.playindex)


def run(params=False):
    if not params:
        addon.setSettingBool("is_locked", True)
        screensaver = Screensaver(
            'screensaver-atv4.xml',
            addon_path,
            'default',
            '',
        )
        screensaver.doModal()
        xbmc.sleep(100)
        del screensaver

    else:
        # Params existed or was true when calling run(), so download files locally
        offline()

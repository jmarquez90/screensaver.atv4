# Smooth random transitions: engineering baseline

Status: diagnostic checkpoint deployed; no transition fix is implemented here.

## Non-negotiable behavior

- Choose Aerial videos randomly. A fixed or pre-generated reel is not an acceptable substitute.
- Show moving Aerial footage continuously across a transition. Hiding a spinner while the video surface is black is not a fix.
- Preserve streaming and local-cache playback.
- Preserve Kodi exit/input behavior, DPMS/CEC behavior, audio behavior, and the rest of the media-center regression surface.
- Leave room for time, date, weather, and shared-family-calendar overlays.

## Current component boundaries

| Responsibility | Current owner | Evidence |
| --- | --- | --- |
| Fetch and parse the Aerial catalog | `resources/lib/playlist.py` | Source-demonstrated |
| Apply location and quality filters | `resources/lib/playlist.py` | Source-demonstrated |
| Substitute a cached path for a network URL | `resources/lib/playlist.py` | Source-demonstrated |
| Randomize a screensaver session | `shuffle(self.playlist)` in `resources/lib/playlist.py` | Source-demonstrated |
| Start each selected item | `Screensaver.start_playback()` in `resources/lib/atv.py` | Source-demonstrated |
| Decode, buffer, render, and tear down an item | Kodi `xbmc.Player` / VideoPlayer | Source-demonstrated in Kodi; not controlled by this add-on |
| Loading and video-window presentation | the add-on skin XML | Source-demonstrated |
| Screensaver lifecycle, exit, DPMS, and CEC | `resources/lib/atv.py`, `resources/lib/screensaver.py`, and `resources/lib/trans.py` | Source-demonstrated |

The smallest replaceable playback boundary is therefore the consumer of the
already-filtered, already-randomized list returned by `AtvPlaylist`. Catalog,
filtering, cache selection, and system lifecycle are outside that boundary.

## Established failure mechanism

The following statements have different evidence levels and must not be blended:

### Demonstrated by this add-on's source

1. The add-on starts one URL with `xbmc.Player.play(..., windowed=True)`.
2. It waits in one-second intervals and polls `isPlaying()`.
3. Only after a poll reports that playback has stopped does it call `play()` for
   the next URL.

This design necessarily creates a scheduling interval between Kodi reaching the
stopped state and the add-on requesting the successor. The interval can approach
one second. The regression harness records this ordering without requiring Kodi.

### Demonstrated by the prior experiments

- Supplying the randomized videos as a Kodi playlist did not eliminate the
  visible inter-item gap.
- Substituting locally cached media did not eliminate the gap.
- The attempted screenshot did not produce a PNG, so it is not visual evidence
  of which Kodi surface was black.

These results rule out network download time and this add-on's explicit
per-item `play()` call as complete explanations. They do not prove that storage
and network latency are irrelevant to startup time.

### Demonstrated by the inspected Kodi 21.3 source

Kodi's item transition tears down or flushes player state before preparing the
next item, including demux/input and render-buffer state. A Kodi playlist still
crosses that item boundary; it does not provide two simultaneously prepared
video frames for a moving crossfade.

### Demonstrated by the target-Pi diagnostic checkpoint

The committed diagnostic build (`5dd818a`) was deployed to LibreELEC 12.2.1 / Kodi 21.3. Its
`resources/lib/atv.py` SHA-256 was verified as
`e10e010a772003d438e68ba3544af0a6b08abb632400e96ea64e63e71348449a` before activation. A natural
transition between two locally cached H.264 Aerial videos produced this timeline:

| Event | Session time | Delta |
| --- | ---: | ---: |
| `playback-ended` | 190196.588 ms | — |
| `stopped-observed` | 190452.682 ms | 256.094 ms |
| `play-requested` | 190452.884 ms | 0.202 ms |
| `play-returned` | 190452.999 ms | 0.115 ms |
| `av-started` | 190904.298 ms | 451.414 ms from request |

Kodi logged demuxer EOF at `16:45:32.212`, followed by queue drain, video-thread exit, codec
deletion, and file close. After the add-on requested the successor, Kodi opened the local file,
created a new input stream and demuxer, opened the DRM PRIME V4L2 H.264 decoder, and created a new
video thread before `onAVStarted()` fired.

The result demonstrates two independent contributors with network transfer absent: 256 ms in the
add-on's polling handoff and 451 ms between the next request and Kodi reporting A/V available. The
total was 708 ms from `playback-ended` and approximately 1.12 seconds from demuxer EOF. Removing
the polling delay alone therefore cannot produce a continuous transition.

No resolution or HDMI mode change was logged. `CVideoSyncGbm::Setup` did reopen during the
boundary, so the display path cannot yet be excluded entirely.

The user reports that the visible black interval in the prior equivalent test felt slightly under
one second and lasted only a split second. That observation is consistent with the measured 708 ms
callback-to-A/V interval, but it is not a frame-accurate display measurement.

### Not yet demonstrated on the target Pi

- The frame-accurate relationship between `onAVStarted()` and the first frame actually visible on
  the television. The user-observed duration is already consistent with the measured timeline.
- Whether any portion of the visible interval occurs in display synchronization despite no logged
  resolution or HDMI mode change.
- How a streamed transition compares with the measured cached transition.
- Whether identical codec, resolution, frame-rate, color-space, and HDR metadata
  materially reduce the gap on this exact display chain.
- Whether Kodi exposes a usable final decoded frame during teardown.
- Whether a continuously fed custom renderer can meet hardware-decoding and
  overlay requirements on the Pi.

## Candidate implementation boundaries

These are alternatives, not decisions:

1. **Long-lived dynamic stream.** Keep one Kodi media item open while a local
   process selects random clips at runtime and feeds a continuous stream. This
   avoids Kodi's media-item boundary, but introduces a stream producer and may
   constrain codec changes, seeking, and hardware decoding.
2. **Frame bridge inside the add-on.** Hold a real last or first frame over the
   Kodi teardown interval. This retains `xbmc.Player` and is smaller, but it is a
   visual bridge rather than a moving-video crossfade and depends on obtaining a
   reliable frame.
3. **Independent renderer.** Replace `xbmc.Player` at the playback boundary with
   a renderer that can prebuffer two clips and composite the transition. This is
   the only candidate that naturally supports a true moving crossfade and rich
   overlays, but it has the largest hardware-decoding, lifecycle, and packaging
   surface.

No candidate should be implemented until the cached result is compared with one streamed
transition. External frame-accurate recording remains useful for validating a final implementation,
but it is not a prerequisite for architecture selection.

## Regression harness

Run from the repository root:

```text
python -m unittest discover -s tests -v
```

The baseline tests are intentionally Kodi-independent. They characterize the
current contract at the future replacement seam:

- eligible items are collected before the session list is shuffled;
- cached paths replace URLs without changing selection membership;
- forced-offline mode excludes only unavailable files; and
- the successor `play()` request happens only after the polling loop observes a
  stopped player.

The instrumented Pi checkpoint is complete. Retain these tests as protection for randomness,
cache behavior, and item selection while the visual and streamed comparison checkpoints proceed.

## Diagnostic event timeline

The diagnostic build emits Kodi log entries at `LOGINFO` prefixed with
`[Aerial transition]`. Each entry contains a session-relative monotonic time, a
sequence number, an event name, and only the minimum metadata needed for the
test. It records whether an item is streamed or local, but deliberately does not
record its URL or filesystem path.

The relevant intervals are:

| Start event | End event | What the interval measures |
| --- | --- | --- |
| `playback-ended` | `stopped-observed` | The add-on's polling/scheduling contribution |
| `stopped-observed` | `play-requested` | The add-on's selection and dispatch contribution |
| `play-requested` | `av-started` | Kodi input, demux, decode, and renderer startup |

`play-returned` only records when the Python call returns; it does not claim that
a decoded frame is visible. Kodi callbacks likewise cannot prove what the display
is showing. The Pi test must pair this timeline with an external recording of the
screen, because the prior screenshot path did not capture a PNG and may not see
the hardware video plane.

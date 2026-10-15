# Smooth random transitions: engineering baseline

Status: baseline checkpoint; no transition fix is implemented here.

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

### Not yet demonstrated on the target Pi

- Whether the visible black interval is wholly inside Kodi's renderer teardown,
  or renderer teardown plus display-mode/HDMI resynchronization.
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

No candidate should be implemented until the target-Pi measurement separates
the add-on polling delay, Kodi item teardown, and any HDMI/display-mode delay.

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

Later checkpoints should add an instrumented Pi test before changing the
playback implementation, then retain these tests as protection for randomness,
cache behavior, and item selection.

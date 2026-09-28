"""Listen for the receiver's transport buttons on RI and act on them.

With DOCK selected, an Onkyo receiver forwards the play/pause, next and
previous buttons of its own remote to the dock over RI. phonkyo is that dock,
so it can hand those presses to whichever player is playing.

Only Plexamp can be controlled today. Its headless build has a local HTTP API
on port 32500. AirPlay 2 senders offer shairport-sync no remote-control
channel, and librespot has no local control interface; presses while either
of those is playing are logged and ignored. See install/MANIFEST.md.

RI is a single wire used in both directions, so one object has to own the
GPIO. RILine listens by default and pauses listening while it transmits, which
also keeps phonkyo from hearing its own frames.
"""

from __future__ import annotations

import collections
import logging
import re
import threading
import time
import urllib.error
import urllib.request
from typing import Callable

import lgpio

from .ri import (DEFAULT_TIMING, DOCK_RX_COMMANDS, GPIO_CHIP, RI_GPIO, RITiming,
                 RITransmitter, decode)

LOG = logging.getLogger("phonkyo.remote")

Frame = list[tuple[int, int]]


class RILine:
    """Owns the RI GPIO: listens for frames, and pauses listening to transmit.

    Edges are timestamped by the kernel through lgpio alerts, so decoding does
    not depend on Python's scheduling. A worker thread cuts the edge stream
    into frames once the line has been quiet for `quiet_s` and passes each
    frame to `on_frame`.
    """

    def __init__(self, on_frame: Callable[[Frame], None], gpio: int = RI_GPIO,
                 chip: int = GPIO_CHIP, timing: RITiming = DEFAULT_TIMING,
                 idle_gap_us: int = 20000, quiet_s: float = 0.03):
        self.gpio = gpio
        self.chip = chip
        self.timing = timing
        self.idle_gap_us = idle_gap_us
        self.quiet_s = quiet_s
        self._on_frame = on_frame
        self._events: collections.deque[tuple[int, int]] = collections.deque()
        self._lock = threading.Lock()  # serialises switching between listen and transmit
        self._stop = threading.Event()
        self._cb = None
        self._handle = lgpio.gpiochip_open(chip)
        self._listen()
        self._worker = threading.Thread(target=self._assemble, name="ri-rx", daemon=True)
        self._worker.start()

    def _listen(self) -> None:
        lgpio.gpio_claim_alert(self._handle, self.gpio, lgpio.BOTH_EDGES)
        self._cb = lgpio.callback(self._handle, self.gpio, lgpio.BOTH_EDGES,
                                  lambda _c, _g, level, tick: self._events.append((level, tick)))

    def _unlisten(self) -> None:
        if self._cb is not None:
            self._cb.cancel()
            self._cb = None
        try:
            lgpio.gpio_free(self._handle, self.gpio)
        except Exception:
            pass

    def send(self, code: int, repeat: int = 3) -> list[float] | None:
        """Transmit a command; listening resumes afterwards. Returns edge errors in us."""
        with self._lock:
            self._unlisten()
            try:
                with RITransmitter(gpio=self.gpio, chip=self.chip, timing=self.timing) as tx:
                    return tx.send(code, repeat=repeat, verify=True)
            finally:
                self._listen()

    def _pulses_to_frames(self, edges: list[tuple[int, int]]) -> list[Frame]:
        # Each edge's level lasts until the next edge. The last one has no end
        # yet; it is the idle low after the trailer, which decoding ignores.
        pulses = [(edges[i][0], (edges[i + 1][1] - edges[i][1]) // 1000)
                  for i in range(len(edges) - 1)]
        pulses.append((edges[-1][0], self.idle_gap_us + 1))
        frames: list[Frame] = []
        current: Frame = []
        for level, duration in pulses:
            current.append((level, duration))
            if duration > self.idle_gap_us:
                frames.append(current)
                current = []
        if current:
            frames.append(current)
        # A frame has to start on a high pulse; a stray leading low is line noise.
        return [f if f[0][0] == 1 else f[1:] for f in frames if len(f) > 1]

    def _assemble(self) -> None:
        edges: list[tuple[int, int]] = []
        last_arrival = 0.0
        while not self._stop.is_set():
            while self._events:
                edges.append(self._events.popleft())
                last_arrival = time.monotonic()
            if edges and time.monotonic() - last_arrival >= self.quiet_s:
                batch, edges = edges, []
                for frame in self._pulses_to_frames(batch):
                    try:
                        self._on_frame(frame)
                    except Exception:
                        LOG.exception("error handling an RI frame")
            time.sleep(0.005)

    def close(self) -> None:
        self._stop.set()
        self._worker.join(timeout=1)
        with self._lock:
            self._unlisten()
            lgpio.gpiochip_close(self._handle)


class PressDetector:
    """Folds the repeated frames of one button press into a single press.

    The receiver sends each press as 3 frames about 50 ms apart. A frame counts
    as a new press only if the same code hasn't been seen for `window_s`.

    Codes in `repeating` (fast-forward and rewind) should keep acting while the
    button is held, so a continuous burst of frames fires again every
    `repeat_s` instead of counting as one press.
    """

    def __init__(self, window_s: float = 0.3, repeating: frozenset[int] = frozenset(),
                 repeat_s: float = 0.4):
        self.window_s = window_s
        self.repeating = repeating
        self.repeat_s = repeat_s
        self._last_seen: dict[int, float] = {}
        self._last_fired: dict[int, float] = {}

    def is_new_press(self, code: int, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        last = self._last_seen.get(code)
        self._last_seen[code] = now
        fire = last is None or now - last > self.window_s
        if not fire and code in self.repeating:
            fire = now - self._last_fired.get(code, 0.0) >= self.repeat_s
        if fire:
            self._last_fired[code] = now
        return fire


class Plexamp:
    """Plexamp headless's local player API (the one Plex apps use for remote control)."""

    ACTIONS = {
        "play_pause": "playPause",
        "track_forward": "skipNext",
        "track_back": "skipPrevious",
    }
    # Plexamp lists stepForward/stepBack as supported but answers 404, so
    # fast-forward and rewind seek relative to the current position instead.
    SEEK_MS = {"fast_forward": 10000, "rewind": -10000}
    # Repeat cycles like Plexamp's own button: off (0) -> all (2) -> one (1) -> off.
    NEXT_REPEAT = {"0": 2, "2": 1, "1": 0}
    # setParameters accepts shuffle but ignores it (Plexamp doesn't list it as
    # controllable), so there is no way to toggle it locally.
    UNSUPPORTED = {"shuffle"}

    def __init__(self, base: str = "http://127.0.0.1:32500", timeout: float = 2.0):
        self.base = base
        self.timeout = timeout
        self._command_id = 0

    def _get(self, path: str) -> str:
        self._command_id += 1
        sep = "&" if "?" in path else "?"
        url = f"{self.base}{path}{sep}commandID={self._command_id}"
        with urllib.request.urlopen(url, timeout=self.timeout) as resp:
            return resp.read().decode("utf-8", "replace")

    def _timeline(self) -> dict[str, str]:
        body = self._get("/player/timeline/poll?wait=0")
        timeline = re.search(r'<Timeline\b[^>]*\btype="music"[^>]*>', body)
        return dict(re.findall(r'(\w+)="([^"]*)"', timeline.group(0))) if timeline else {}

    def state(self) -> str | None:
        """'playing', 'paused', 'stopped', or None if Plexamp isn't reachable."""
        try:
            return self._timeline().get("state")
        except (urllib.error.URLError, OSError):
            return None

    def do(self, action: str) -> None:
        if action == "repeat":
            current = self._timeline().get("repeat", "0")
            self._get(f"/player/playback/setParameters?type=music&repeat={self.NEXT_REPEAT.get(current, 0)}")
            return
        if action in self.SEEK_MS:
            timeline = self._timeline()
            position = int(timeline.get("time", 0)) + self.SEEK_MS[action]
            duration = int(timeline.get("duration", 0))
            if duration:
                position = min(position, duration - 1000)
            self._get(f"/player/playback/seekTo?type=music&offset={max(position, 0)}")
            return
        self._get(f"/player/playback/{self.ACTIONS[action]}?type=music")


STATUS_PATH = "/proc/asound/card{card}/pcm{device}p/sub{sub}/status"
UNCONTROLLABLE = {"shairport-sync": "AirPlay", "librespot": "Spotify"}
# Buttons the receiver forwards that deliberately do nothing (yet).
UNASSIGNED = {"menu"}


def pcm_owner(card: int = 0, device: int = 0, sub: int = 0) -> tuple[str, str | None]:
    """The DAC's stream state and the name of the process feeding it."""
    try:
        with open(STATUS_PATH.format(card=card, device=device, sub=sub)) as fh:
            text = fh.read()
    except OSError:
        return "closed", None
    if text.startswith("closed"):
        return "closed", None
    state, pid = "unknown", None
    for line in text.splitlines():
        if line.startswith("state:"):
            state = line.split(":", 1)[1].strip()
        elif line.startswith("owner_pid"):
            pid = line.split(":", 1)[1].strip()
    name = None
    if pid:
        # ALSA records the thread that opened the device (Plexamp's shows up as
        # "libuv-worker"), so resolve it to its process before reading the name.
        try:
            with open(f"/proc/{pid}/status") as fh:
                tgid = next((l.split()[1] for l in fh if l.startswith("Tgid:")), pid)
            with open(f"/proc/{tgid}/comm") as fh:
                name = fh.read().strip()
        except OSError:
            pass
    return state, name


class RemoteRouter:
    """Decides what a button press does, given what is playing."""

    def __init__(self, control: bool = True, plexamp: Plexamp | None = None):
        self.control = control
        self.plexamp = plexamp or Plexamp()

    def handle(self, action: str) -> None:
        state, owner = pcm_owner()
        if state == "RUNNING" and owner in UNCONTROLLABLE:
            LOG.info("remote: %s ignored, %s is playing and can't be controlled",
                     action, UNCONTROLLABLE[owner])
            return
        if action in UNASSIGNED:
            LOG.info("remote: %s has no action assigned", action)
            return
        if action in Plexamp.UNSUPPORTED:
            LOG.info("remote: %s ignored, Plexamp's local API can't do it", action)
            return
        plex_state = self.plexamp.state()
        if plex_state not in ("playing", "paused"):
            LOG.info("remote: %s ignored, nothing controllable is playing (Plexamp: %s)",
                     action, plex_state or "unreachable")
            return
        if not self.control:
            LOG.info("remote: log mode, would send %s to Plexamp (%s)", action, plex_state)
            return
        try:
            self.plexamp.do(action)
            LOG.info("remote: %s -> Plexamp (was %s)", action, plex_state)
        except (urllib.error.URLError, OSError) as exc:
            LOG.warning("remote: %s -> Plexamp failed: %s", action, exc)


class RemoteListener:
    """Turns RI frames from the receiver into button presses and routes them."""

    def __init__(self, router: RemoteRouter, timing: RITiming = DEFAULT_TIMING):
        self.router = router
        self.timing = timing
        seek_codes = frozenset(c for c, a in DOCK_RX_COMMANDS.items() if a in Plexamp.SEEK_MS)
        self.presses = PressDetector(repeating=seek_codes)

    def on_frame(self, frame: Frame) -> None:
        code = decode(frame, self.timing)
        if code is None:
            LOG.debug("remote: undecodable frame (%d pulses)", len(frame))
            return
        if not self.presses.is_new_press(code):
            return
        action = DOCK_RX_COMMANDS.get(code)
        if action is None:
            LOG.info("remote: unmapped code %#05x", code)
            return
        LOG.info("remote: %s (%#05x)", action, code)
        self.router.handle(action)

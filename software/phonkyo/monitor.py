"""Watch the DAC for playback and drive the amplifier over RI.

Turns the receiver on (and selects DOCK) when audio starts, and off again
after a quiet period, so the amp follows AirPlay/Spotify/Plexamp automatically.

Detecting playback is subtler than it looks. The previous phonkyo build keyed
on `subdevices_avail` in /proc/asound -- i.e. "is the PCM device claimed". That
is wrong here: Plexamp opens the device at startup and holds it in PREPARED
state indefinitely while completely idle, which would switch the amp on at boot
and never let it off. We instead require state==RUNNING *and* hw_ptr to have
advanced since the last poll, which distinguishes real playback from a device
that is merely open, or open and stalled.
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from dataclasses import dataclass

from .ri import COMMANDS, RITransmitter, RealTimeUnavailable

LOG = logging.getLogger("phonkyo.monitor")

STATUS_PATH = "/proc/asound/card{card}/pcm{device}p/sub{sub}/status"


@dataclass
class PlaybackState:
    running: bool
    hw_ptr: int | None


class PlaybackDetector:
    def __init__(self, card: int = 0, device: int = 0, sub: int = 0):
        self.path = STATUS_PATH.format(card=card, device=device, sub=sub)
        self._last_ptr: int | None = None

    def _read(self) -> PlaybackState:
        try:
            with open(self.path) as fh:
                text = fh.read()
        except FileNotFoundError:
            return PlaybackState(False, None)
        if text.startswith("closed"):
            return PlaybackState(False, None)
        running = False
        hw_ptr = None
        for line in text.splitlines():
            if line.startswith("state:"):
                running = line.split(":", 1)[1].strip() == "RUNNING"
            elif line.startswith("hw_ptr"):
                try:
                    hw_ptr = int(line.split(":", 1)[1])
                except ValueError:
                    pass
        return PlaybackState(running, hw_ptr)

    def is_playing(self) -> bool:
        """True only if the stream is RUNNING and samples are actually moving."""
        state = self._read()
        if not state.running or state.hw_ptr is None:
            self._last_ptr = state.hw_ptr
            return False
        advanced = self._last_ptr is not None and state.hw_ptr > self._last_ptr
        # First observation of a RUNNING stream counts as playing; we cannot
        # yet know whether the pointer is moving, and a false positive here is
        # far cheaper than a delayed power-on.
        first_sight = self._last_ptr is None
        self._last_ptr = state.hw_ptr
        return advanced or first_sight


class AmpController:
    def __init__(self, gpio: int = 25, repeat: int = 3, dry_run: bool = False):
        self.gpio = gpio
        self.repeat = repeat
        self.dry_run = dry_run
        # Starts False deliberately: phonkyo only ever switches off an amp it
        # switched on. Otherwise turning the receiver on yourself for vinyl or
        # TV would have phonkyo silently kill it after the idle timeout.
        self.powered: bool = False

    def _send(self, name: str) -> None:
        code = COMMANDS[name]
        if self.dry_run:
            LOG.info("dry-run: would send %s (%#05x)", name, code)
            return
        try:
            with RITransmitter(gpio=self.gpio) as tx:
                errors = tx.send(code, repeat=self.repeat, verify=True)
            worst = max(abs(e) for e in errors)
            LOG.info("sent %s (%#05x) x%d, worst edge error %.1f us",
                     name, code, self.repeat, worst)
        except RealTimeUnavailable:
            LOG.error("no SCHED_FIFO: refusing to transmit, timing would be unreliable")
            raise

    def on(self) -> None:
        if self.powered is True:
            return
        LOG.info("playback started -> powering amp on, selecting DOCK")
        self._send("power_on_dock")
        self.powered = True

    def off(self) -> None:
        if not self.powered:
            return
        LOG.info("idle timeout reached -> powering amp off")
        self._send("power_off")
        self.powered = False


def run(poll_interval: float, idle_timeout: float, gpio: int, dry_run: bool) -> int:
    detector = PlaybackDetector()
    amp = AmpController(gpio=gpio, dry_run=dry_run)

    stopping = False

    def _stop(signum, _frame):
        nonlocal stopping
        LOG.info("received signal %s, stopping", signum)
        stopping = True

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    LOG.info("watching %s (poll %.1fs, idle timeout %.0fs)",
             detector.path, poll_interval, idle_timeout)

    quiet_since: float | None = None
    while not stopping:
        playing = detector.is_playing()
        now = time.monotonic()

        if playing:
            quiet_since = None
            amp.on()
        else:
            if quiet_since is None:
                quiet_since = now
            elif now - quiet_since >= idle_timeout:
                amp.off()
                quiet_since = None  # do not re-send until playback resumes

        time.sleep(poll_interval)

    LOG.info("stopped")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--poll", type=float, default=2.0, help="seconds between checks")
    ap.add_argument("--idle-timeout", type=float, default=300.0,
                    help="seconds of silence before powering the amp off")
    ap.add_argument("--gpio", type=int, default=25)
    ap.add_argument("--dry-run", action="store_true",
                    help="log what would be sent without driving the line")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
        stream=sys.stdout,
    )
    return run(args.poll, args.idle_timeout, args.gpio, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())

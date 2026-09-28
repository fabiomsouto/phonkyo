"""Onkyo RI (Remote Interactive) transmitter for the phonkyo HAT.

The RI jack (J4) carries a single-wire baseband signal on GPIO25; tip is
signal, ring/sleeve are ground. There is no level shifting or protection on
the v0.2 board -- GPIO25 goes straight to the tip.

Timing is generated in software via lgpio on /dev/gpiochip0. This deliberately
avoids pigpio, whose DMA timebase defaults to the PCM peripheral -- the same
block the I2S DAC uses. Measured on a Pi Zero 2 W with SCHED_FIFO, worst-case
edge error is ~2.5 us idle and ~48 us with I2S streaming, against a bit period
of 1000 us. Without SCHED_FIFO, CPU contention produces 4 ms errors and every
frame is corrupt, so real-time priority is not optional.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

import lgpio

RI_GPIO = 25
GPIO_CHIP = 0


@dataclass(frozen=True)
class RITiming:
    """Pulse-distance encoding. Line idles low; the transmitter drives it high.

    NOTE: these values come from community reverse-engineering of the RI bus
    and have not yet been confirmed against a real Onkyo unit. Verify with
    `sniff()` against a known-good RI device before trusting them.
    """

    header_high: int = 3000
    header_low: int = 1000
    bit_high: int = 1000
    one_low: int = 2000
    zero_low: int = 1000
    trailer_high: int = 1000
    # The bus needs to sit idle between frames or a repeat is read as noise.
    # Spec floor is ~20 ms; the previous working phonkyo build used 50 ms.
    inter_frame_low: int = 50000
    bits: int = 12


DEFAULT_TIMING = RITiming()

# Codes recovered from the previous working phonkyo install (monitor.py),
# cross-checked against docbender/Onkyo-RI. Verified on a real receiver.
COMMANDS = {
    "power_on_dock": 0x17F,   # power on AND select DOCK
    "select_dock": 0x170,
    "power_off": 0x420,
    "dimmer_high": 0x2B0,
    "dimmer_mid": 0x2B1,
    "dimmer_low": 0x2B2,
    "volume_up": 0x1A2,
    "volume_down": 0x1A3,
    "mute": 0x1A4,
    "unmute": 0x1A5,
    "select_cd": 0x20,
    "power_on_cd": 0x2F,
    "select_tape": 0x70,
    "power_on_tape": 0x7F,
}

# The other direction of the bus. With DOCK selected, the receiver forwards
# its transport buttons to the attached dock -- which is us. These were
# captured from a real receiver (three isolated frames each), not guessed.
#
# Only the low 3 bits carry the command; the upper 9 (0b010111001) identify
# the dock device class, so further transport codes very likely live in the
# same family.
DOCK_RX_COMMANDS = {
    0x5C0: "fast_forward",
    0x5C1: "rewind",
    0x5C8: "track_forward",
    0x5C9: "track_back",
    0x5CB: "play_pause",
    0x5D2: "shuffle",
    0x5D3: "repeat",
    0x5D6: "menu",
}


class RealTimeUnavailable(RuntimeError):
    pass


def _acquire_realtime(priority: int = 50) -> None:
    """Pin this thread to SCHED_FIFO. Without it, timing is unusable under load."""
    try:
        os.sched_setscheduler(0, os.SCHED_FIFO, os.sched_param(priority))
    except (PermissionError, OSError) as exc:
        raise RealTimeUnavailable(
            "SCHED_FIFO unavailable -- run as root or grant CAP_SYS_NICE. "
            "Transmitting without it risks multi-millisecond timing errors."
        ) from exc


def _release_realtime() -> None:
    try:
        os.sched_setscheduler(0, os.SCHED_OTHER, os.sched_param(0))
    except OSError:
        pass


class RITransmitter:
    def __init__(self, gpio: int = RI_GPIO, chip: int = GPIO_CHIP,
                 timing: RITiming = DEFAULT_TIMING, realtime: bool = True):
        self.gpio = gpio
        self.timing = timing
        self.realtime = realtime
        self._handle = lgpio.gpiochip_open(chip)
        lgpio.gpio_claim_output(self._handle, gpio, 0)

    def close(self) -> None:
        if self._handle is not None:
            lgpio.gpio_write(self._handle, self.gpio, 0)
            lgpio.gpio_free(self._handle, self.gpio)
            lgpio.gpiochip_close(self._handle)
            self._handle = None

    def __enter__(self): return self
    def __exit__(self, *exc): self.close(); return False

    def _frame(self, code: int) -> list[tuple[int, int]]:
        """Expand a command into a list of (level, duration_us) edges, MSB first."""
        t = self.timing
        edges = [(1, t.header_high), (0, t.header_low)]
        for i in range(t.bits - 1, -1, -1):
            bit = (code >> i) & 1
            edges.append((1, t.bit_high))
            edges.append((0, t.one_low if bit else t.zero_low))
        edges.append((1, t.trailer_high))
        edges.append((0, t.inter_frame_low))
        return edges

    def send(self, code: int, repeat: int = 3, verify: bool = False) -> list[float] | None:
        """Transmit a 12-bit RI command.

        RI has no acknowledgement, so commands are sent more than once; the
        previous working phonkyo build repeated three times and that is the
        default here.

        With verify=True, returns the per-edge timing error in microseconds,
        measured from the transmitter's own clock. This validates the software
        timing without needing a scope -- it cannot confirm the electrical
        result at the jack.
        """
        max_code = (1 << self.timing.bits) - 1
        if not 0 <= code <= max_code:
            raise ValueError(f"code must fit in {self.timing.bits} bits (0..{max_code:#x})")

        edges = self._frame(code)
        errors: list[float] = [] if verify else None
        h, pin = self._handle, self.gpio

        if self.realtime:
            _acquire_realtime()
        try:
            # Absolute deadlines, so the ~7 us cost of each write does not
            # accumulate into drift across the frame.
            deadline = time.perf_counter_ns()
            for _ in range(repeat):
                for level, duration_us in edges:
                    lgpio.gpio_write(h, pin, level)
                    if duration_us == 0:
                        continue
                    deadline += duration_us * 1000
                    while time.perf_counter_ns() < deadline:
                        pass
                    # the long idle gap is not part of the signal being timed
                    if verify and duration_us != self.timing.inter_frame_low:
                        errors.append((time.perf_counter_ns() - deadline) / 1000.0)
            lgpio.gpio_write(h, pin, 0)
        finally:
            if self.realtime:
                _release_realtime()
        return errors


def decode(frame: list[tuple[int, int]], timing: RITiming = DEFAULT_TIMING,
           tolerance: float = 0.35) -> int | None:
    """Best-effort decode of a captured frame back into a 12-bit code.

    See phonkyo.sniff for capturing frames off a live RI bus.
    """
    def near(actual: int, expected: int) -> bool:
        return abs(actual - expected) <= expected * tolerance

    lows = [d for lvl, d in frame if lvl == 0]
    if len(lows) < timing.bits + 1:
        return None
    code = 0
    for d in lows[1:timing.bits + 1]:
        if near(d, timing.one_low):
            code = (code << 1) | 1
        elif near(d, timing.zero_low):
            code <<= 1
        else:
            return None
    return code

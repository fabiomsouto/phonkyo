"""Passively capture and decode Onkyo RI frames.

Published RI code tables are partial and model-specific, so the reliable way
to learn what a given receiver responds to is to listen to what it emits.
Many Onkyo units transmit on the RI bus when their state changes, precisely
so attached devices can follow.

Edges are timestamped by the kernel via lgpio alerts rather than polled from
Python, which is what makes the timings trustworthy: measured against a real
TX-series receiver, captured pulses land within ~25 us of nominal.
"""

from __future__ import annotations

import argparse
import sys
import time

import lgpio

from .ri import DEFAULT_TIMING, GPIO_CHIP, RI_GPIO, RITiming, decode

Frame = list[tuple[int, int]]


def capture(seconds: float = 12.0, gpio: int = RI_GPIO, chip: int = GPIO_CHIP,
            idle_gap_us: int = 20000) -> list[Frame]:
    """Listen on the RI line and return whole frames as (level, duration_us)."""
    handle = lgpio.gpiochip_open(chip)
    events: list[tuple[int, int]] = []
    try:
        lgpio.gpio_claim_alert(handle, gpio, lgpio.BOTH_EDGES)
        cb = lgpio.callback(handle, gpio, lgpio.BOTH_EDGES,
                            lambda _c, _g, level, tick: events.append((level, tick)))
        time.sleep(seconds)
        cb.cancel()
    finally:
        try:
            lgpio.gpio_free(handle, gpio)
        except Exception:
            pass
        lgpio.gpiochip_close(handle)

    if len(events) < 2:
        return []

    pulses = [(events[i][0], (events[i + 1][1] - events[i][1]) // 1000)
              for i in range(len(events) - 1)]

    frames: list[Frame] = []
    current: Frame = []
    for level, duration in pulses:
        current.append((level, duration))
        if duration > idle_gap_us:
            frames.append(current)
            current = []
    if current:
        frames.append(current)
    return frames


def summarise(frame: Frame, timing: RITiming = DEFAULT_TIMING) -> str:
    code = decode(frame, timing)
    header = frame[0][1] if frame else 0
    return (f"{code:#05x}" if code is not None else "<undecodable>") + \
           f"  ({len(frame)} pulses, header {header} us)"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seconds", type=float, default=12.0)
    ap.add_argument("--gpio", type=int, default=RI_GPIO)
    ap.add_argument("--label", default="", help="what you are about to press")
    ap.add_argument("--raw", action="store_true", help="print every pulse")
    args = ap.parse_args(argv)

    if args.label:
        print(f"=== capturing {args.seconds:.0f}s :: {args.label} ===")
    frames = capture(seconds=args.seconds, gpio=args.gpio)

    if not frames:
        print("  nothing captured - the receiver emitted no RI")
        return 1

    codes = []
    for i, frame in enumerate(frames, 1):
        print(f"  frame {i}: {summarise(frame)}")
        if args.raw:
            print("    " + " ".join(f"{'H' if l else 'L'}{d}" for l, d in frame))
        code = decode(frame)
        if code is not None:
            codes.append(code)

    unique = sorted(set(codes))
    if unique:
        print("  distinct codes: " + ", ".join(f"{c:#05x}" for c in unique))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

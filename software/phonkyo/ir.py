"""Infrared control for the Onkyo receiver.

RI cannot do everything. An exhaustive sweep of the 12-bit RI space (all 256
families in both select forms, plus every command nibble in the families a
TX-8020 responds to) found no TV input select, no volume and no mute -- those
inputs simply have no RI device to coordinate with. Infrared does have them.

Codes below are for the RC-875S remote shipped with the TX-8020, taken from a
published LIRC config. Rather than rely on a protocol decoder agreeing with
LIRC about NEC variants, we emit raw pulse/space sequences built from the
config's own measured timings and hand them to ir-ctl. That removes a whole
class of "which NEC flavour is this" ambiguity.

Requires an IR LED on a GPIO plus one of:
    dtoverlay=pwm-ir-tx,gpio_pin=12    # hardware carrier, preferred
    dtoverlay=gpio-ir-tx,gpio_pin=17   # software carrier
Do NOT use the default gpio_pin=18 -- that is the I2S bit clock for the DAC.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

CARRIER_HZ = 38000


@dataclass(frozen=True)
class NECTiming:
    """Measured timings from the TX-8020 LIRC config (microseconds)."""
    header_pulse: int = 8998
    header_space: int = 4441
    bit_pulse: int = 603
    one_space: int = 1655
    zero_space: int = 526
    trailer_pulse: int = 596
    gap: int = 107490
    bits: int = 32


TX8020 = NECTiming()

# RC-875S, as shipped with the TX-8020 / TX-8040.
COMMANDS = {
    "power":       0x4B36D32C,
    "input_tv":    0x4B403BC4,
    "input_dvd":   0x4B40AB54,
    "input_cd":    0x4B406B94,
    "volume_up":   0x4BB640BF,
    "volume_down": 0x4BB6C03F,
    "mute":        0x4BB6A05F,
    "menu":        0x4B405AA5,
    "play_pause":  0x4B40F807,
    "up":          0x4BB641BE,
    "down":        0x4BB6C13E,
    "left":        0x4BB621DE,
    "right":       0x4BB6A15E,
}


def pulses(code: int, timing: NECTiming = TX8020) -> list[int]:
    """Expand a code into alternating pulse/space durations in microseconds."""
    out = [timing.header_pulse, timing.header_space]
    for i in range(timing.bits - 1, -1, -1):
        out.append(timing.bit_pulse)
        out.append(timing.one_space if (code >> i) & 1 else timing.zero_space)
    out.append(timing.trailer_pulse)
    return out


def to_ir_ctl(code: int, timing: NECTiming = TX8020) -> str:
    """Render as an ir-ctl send file: alternating pulse/space lines."""
    lines = [f"carrier {CARRIER_HZ}"]
    for i, duration in enumerate(pulses(code, timing)):
        lines.append(f"{'pulse' if i % 2 == 0 else 'space'} {duration}")
    return "\n".join(lines) + "\n"


def send(name_or_code: str | int, device: str = "/dev/lirc0",
         repeat: int = 1, timing: NECTiming = TX8020) -> None:
    """Transmit via ir-ctl. Raises if the LED/overlay is not present."""
    if shutil.which("ir-ctl") is None:
        raise RuntimeError("ir-ctl not found -- install v4l-utils")
    code = COMMANDS[name_or_code] if isinstance(name_or_code, str) else name_or_code
    payload = to_ir_ctl(code, timing)
    for _ in range(repeat):
        subprocess.run(["ir-ctl", "-d", device, "--send=/dev/stdin"],
                       input=payload, text=True, check=True)

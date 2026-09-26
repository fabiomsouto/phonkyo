"""Identify the phonkyo board from its HAT ID EEPROM.

When U1 is populated and programmed, the Pi firmware reads it at boot and
publishes the contents under /proc/device-tree/hat/. That gives software a
reliable answer to two questions a shipped product needs to ask:

  - is this actually running on phonkyo hardware, or has someone installed
    the software on a bare Pi and wondered why there is no sound?
  - which board revision is it, so behaviour can adapt without the user
    being asked

Everything degrades gracefully: on a board with no EEPROM (v0.2), or one
not yet programmed, detect() returns None and callers fall back to their current behaviour.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

HAT_DIR = Path("/proc/device-tree/hat")
VENDOR = "obcecado.com"
PRODUCT_ID = 0x0001  # phonkyo; other Obcecado boards use other ids


@dataclass(frozen=True)
class HatInfo:
    vendor: str
    product: str
    product_id: int
    product_ver: int
    uuid: str

    @property
    def is_phonkyo(self) -> bool:
        return self.vendor.lower() == VENDOR and self.product_id == PRODUCT_ID

    @property
    def revision(self) -> str:
        """product_ver 0x0003 -> 'v0.3'."""
        return f"v{self.product_ver // 10}.{self.product_ver % 10}"


def _read(name: str) -> str:
    # device-tree properties are NUL-terminated
    return (HAT_DIR / name).read_bytes().rstrip(b"\x00").decode("utf-8", "replace")


def _read_int(name: str) -> int:
    raw = _read(name).strip()
    return int(raw, 16) if raw.lower().startswith("0x") else int(raw or 0)


def detect() -> HatInfo | None:
    """Return the fitted HAT's identity, or None if no EEPROM is present."""
    if not HAT_DIR.is_dir():
        return None
    try:
        return HatInfo(
            vendor=_read("vendor"),
            product=_read("product"),
            product_id=_read_int("product_id"),
            product_ver=_read_int("product_ver"),
            uuid=_read("uuid"),
        )
    except (OSError, ValueError):
        return None


def alsa_card(name: str = "sndrpihifiberry") -> str | None:
    """Find the DAC by *name* rather than assuming it is card 0.

    Card numbering is not stable across machines -- a buyer who leaves HDMI
    audio enabled will have the DAC land on card 1, and a hardcoded "hw:0"
    then plays into the television. Referencing the card by name removes
    that whole class of support ticket.
    """
    try:
        cards = Path("/proc/asound/cards").read_text()
    except OSError:
        return None
    for line in cards.splitlines():
        # " 0 [sndrpihifiberry]: RPi-simple - ..."  -- the name field is
        # space-padded inside the brackets, so match to the bracket and strip
        m = re.match(r"\s*(\d+)\s+\[([^\]]+)\]", line)
        if m and m.group(2).strip() == name:
            return f"hw:CARD={name}"
    return None


if __name__ == "__main__":
    info = detect()
    if info is None:
        print("no HAT EEPROM detected (expected on v0.2, or an unprogrammed v0.3)")
    else:
        print(f"vendor      {info.vendor}")
        print(f"product     {info.product}")
        print(f"product_id  {info.product_id:#06x}")
        print(f"revision    {info.revision} (product_ver {info.product_ver:#06x})")
        print(f"uuid        {info.uuid}")
        print(f"is phonkyo  {info.is_phonkyo}")
    print(f"dac device  {alsa_card() or 'not found'}")

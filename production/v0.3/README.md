# phonkyo v0.3 production files

Generated from `phonkyo.kicad_pcb` / `phonkyo.kicad_sch` with KiCad 10.

| File | Upload to JLCPCB as |
|---|---|
| `phonkyo-v0.3-gerbers.zip` (Gerbers + drills, not tracked in git) | Gerber file |
| `phonkyo-v0.3-bom-jlcpcb.csv` | BOM |
| `phonkyo-v0.3-cpl-jlcpcb.csv` | CPL / pick-and-place |

Rebuild the zip with:

```sh
cd production/v0.3 && zip phonkyo-v0.3-gerbers.zip *.g* *.drl
```

## Order settings

- 2 layers, 1.6 mm, 65 x 30 mm. ENIG is kinder to the two 0.65 mm-pitch
  TSSOPs; lead-free HASL also works.
- PCB Assembly on the **top side** for every SMD part.
- **J1 (40-pin female header) is not in the JLC BOM or CPL on purpose.**
  It is hand-soldered on the bottom side before each board is programmed.
  JLC does not ship loose parts with an assembly order, so buy the headers
  separately (see below).
- JP1 is a solder jumper, not a part. It ships **open**.

## Parts

LCSC numbers live in each symbol's `LCSC` field in the schematic, so the BOM
regenerates with them. Basic parts carry no loading fee. The 7 extended parts
each carry a one-off fee:

| Extended part | LCSC | Why this one |
|---|---|---|
| PCM5102APWR | C107671 | the DAC |
| CAT24C256YI-GT3 | C146734 | the ID EEPROM the design was checked against |
| PJ-320D-4A, Korean Hroparts | C95562 | matches the jack footprint |
| 2.2 nF 0402 C0G, Murata GRM1555C1H222JA01D | C385029 | C0G for the audio output filter; the basic 2.2 nF is X7R |
| 2.2 uF 0402 X5R 10 V, Samsung CL05A225KP5NSNC | C107369 | the basic 2.2 uF is only 6.3 V |
| 3.9 k 0402 1%, Yageo | C131467 | HAT spec pull-up value, no basic part exists |
| ESD5Z5.0T1G, onsemi, SOD-523 | C82044 | D1, ESD clamp on the RI jack; 5 V standoff so a 5 V receiver is not clipped. No basic ESD diode exists |

## Buy separately

| Part | LCSC | Notes |
|---|---|---|
| J1: 2x20 female header, 2.54 mm, 8.5 mm high, through-hole | C5124634 | one per board, hand-soldered; the usual pHAT height, so check it matches the v0.2 stack height |

The J1 reference stays in the schematic's `LCSC` field. If a JLC BOM is
regenerated from the schematic, delete the J1 line again.

## Before paying

In JLC's placement preview, check pin 1 of U1, U2 and U3, the cathode of D1
(it faces R12 and the via between them), and the orientation of J2/J4. KiCad and JLC often disagree on rotation for SOT-23 and TSSOP
footprints. Rotate them in their tool if needed.

## After the boards arrive

For each board:

1. Solder J1 on the bottom side.
2. Seat the board on a Pi with JP1 open.
3. Run `cd hardware/eeprom && make flash` on the Pi. It builds the image with a
   fresh UUID, writes it, reads it back and compares. The steps are in
   `install/MANIFEST.md`, section 10, on the software branch.
4. Bridge JP1 with solder to write-protect the EEPROM.

## Bring-up checklist for the first boards

1. **Visual:** D1's cathode faces R12. Pin 1 of U1, U2 and U3 is correct. No
   solder bridges on the two TSSOPs.
2. **Before fitting to a Pi,** with a multimeter: +5V, +3V3 and +3.3VA are not
   shorted to ground. GND to GNDA reads about 0 R (the NT1 net tie).
3. **Power:** on a Pi, U3's output (+3.3VA) is about 3.3 V.
4. **EEPROM:** solder J1, JP1 open, `make flash`, then reboot.
   `/proc/device-tree/hat/vendor` reads `obcecado.com`. To prove the overlay
   comes from the EEPROM, remove `dtoverlay=hifiberry-dac` from config.txt:
   the sound card should still appear in `aplay -l`. Then bridge JP1.
5. **Audio:** play through the amplifier and compare noise against v0.2.
6. **RI:** power-on and DOCK from the Pi (transmit through R12), and the sniffer
   (receive). If transmit fails, fit 0 R in place of R12.
7. **Optional:** measure the RI line's high level while the receiver sends, and
   the receiver's pull-down. With a pull-down of 10 k or more, R12 can go up to
   470 R to 1 k for more margin.

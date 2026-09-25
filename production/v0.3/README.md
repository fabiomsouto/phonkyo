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
- **J1 (40-pin female header)** is through-hole on the bottom side. Either
  leave it out of the assembly and solder it by hand, or keep it in the BOM
  and choose through-hole assembly. The CPL places it at its centre, not
  at pin 1.
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
| 2x20 female header, 8.5 mm, BOOMELE | C5124634 | only needed if JLC fits J1 |

## Before paying

In JLC's placement preview, check pin 1 of U1, U2 and U3 and the orientation of
J2/J4. KiCad and JLC often disagree on rotation for SOT-23 and TSSOP
footprints. Rotate them in their tool if needed.

## After the boards arrive

Program the ID EEPROM with JP1 open (`cd hardware/eeprom && make flash` on
the Pi), then bridge JP1 to write-protect it.

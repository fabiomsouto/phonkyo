# phonkyo v0.3 hardware review

**Date:** 2026-09-23, status updated 2026-09-26
**Design reviewed:** `phonkyo.kicad_sch` / `phonkyo.kicad_pcb` at commit `6e10180` ("add: revision 0.3"), KiCad 8 format
**Status reflects:** branch `feat/v0.3-caps-eeprom`, where the design is now in KiCad 10 format
**Board:** 2-layer, 65 x 30 mm pHAT for the Raspberry Pi Zero 2 W

## Scope and method

The review was done on commit `6e10180`. Placement, routing, zones, vias and
silkscreen were extracted with the KiCad API, and circuit findings were checked
against the PCM5102A datasheet (`adc/pcm5102a.pdf`, TI SLAS859C). Distances in
this document are pad edge to pad edge unless stated otherwise.

Each finding carries a **Status** line describing the design on
`feat/v0.3-caps-eeprom`. Measurements in the status lines come from that
branch.

On that branch, KiCad 10 DRC with schematic parity reports **0 unconnected
items, 0 parity errors and no DRC errors**. The only warnings are
library-mismatch warnings on older footprints. ERC still reports 4 missing
`PWR_FLAG`s, on +5V, +3V3, GND and GNDA. These are bookkeeping rather than real
faults.

Only **v0.2** has been built. A v0.2 board was exercised end to end on a Pi Zero
2 W with an Onkyo TX-8020 receiver: DAC output on both channels, RI transmit, and
RI receive, with no audible noise. None of the findings below has been confirmed
or ruled out on fabricated v0.3 hardware, and no EMC measurements have been made.

## Summary

The analog design is sound. The analog/digital partition runs cleanly through
the DAC, the output filter is placed well, and the grounding follows a
deliberate single-point scheme. The issues found were in layout and product
readiness rather than circuit design:

| # | Finding | Status |
|---|---|---|
| 1 | Plot settings wrote to `production/v0.2` | **Fixed** |
| 2 | The I2S bit clock has the longest route and no reference plane | Open |
| 3 | Decoupling capacitors far from their pins; none at AVDD | **Fixed** |
| 4 | XSMT | Withdrawn: leave as designed |
| 5 | Ground topology mixes split and unified approaches | **Decided**: keep the split; the single tie is now a net tie |
| 6 | ID EEPROM drawn but not fitted | **Fixed** |
| 7 | No ESD protection on the RI jack | Open |
| 8 | 470 R output resistors are poor for headphones | Open |
| 9 | Logo silkscreen printed over the RI jack pads | **Fixed** |

## What is done well

- **The analog/digital split runs through U2 itself.** Analog pins 1 to 9
  (CPVDD, CAPP, CPGND, CAPM, VNEG, OUTL, OUTR, AVDD, AGND) sit at x = 148.3 mm,
  inside the GNDA pour. Digital pins 17 to 20 sit at x = 154.0 mm, outside it.
- **Single-point star ground.** One connection joins GNDA and GND: R11 (0 R) at
  review time, now the net tie NT1 (see finding 5).
- **Tight output filter.** R3 and R4 are 0.8 mm from OUTL and OUTR. The RC is
  470 R with 2.2 nF, giving a corner at about 154 kHz. The 2.2 nF capacitors are
  specified as C0G in the v0.3 BOM.
- **No DC-blocking capacitors on the outputs.** This is correct for the
  PCM5102A: its charge pump produces ground-centred outputs, and adding coupling
  capacitors here is a common mistake.
- **22 R series damping** on all three I2S lines (R7, R8, R9).
- **BCK avoids the analog region.** None of its route passes over the GNDA pour.
- **Ground stitching around the DAC.** 7 of the board's 12 GND vias sit around
  U2's digital side (x 149 to 156.5 mm), including one under the body for DGND
  pin 19. Of the rest, one is at the GND/GNDA tie point, two serve the ID
  EEPROM, and two are in the J4 area, one of them on the jack's sleeve.
- **XSMT power sensing.** R5/R6 divide +5V onto XSMT. This is TI's documented
  "External Power Sense Undervoltage Protection Mode" (datasheet §11.3,
  Fig. 39): the DAC mutes as the upstream rail falls, before the regulated
  3.3 V rails collapse. See finding 4 for why it should be left as it is.
- **SCK tied to GND.** This selects the internal PLL, which derives the system
  clock from BCK. That is correct for a slave-only PCM5102A driven by a Pi.
- **Mechanical.** The mounting holes are on the 58 x 23 mm Pi Zero pattern, and
  there is a keepout for the Pi's PoE header.

## Findings

Findings are ordered by value per effort, not by severity.

### 1. Plot output pointed at the v0.2 production folder

The v0.3 board's plot settings had `outputdirectory "production/v0.2"`, so
plotting v0.3 Gerbers would have written over the v0.2 fabrication files, which
are the ones that were actually manufactured. The repo also had no BOM or
position files for v0.3.

**Status: Fixed.** The plot output is now `production/v0.3`. That folder holds
the Gerbers (including F.Paste for the stencil), Excellon drills, a JLCPCB BOM
and CPL with LCSC part numbers kept in the schematic, and a README with the
order settings.

**Correction.** An earlier version of this review said the board had no
functional silkscreen and that the jacks were unlabelled. That was wrong. v0.2
and v0.3 both carry knockout labels: `Remote` by J4, `Audio` by J2, `DAC`, the
board name, and a specs block on the back. The earlier text-extraction step
missed them. Reference designators are hidden, which only matters for rework
and debugging. The jack mix-up during bring-up happened despite the labels.

### 2. The I2S bit clock has the worst route on the board

| | BCK | LRCK | DIN |
|---|---|---|---|
| Header to series resistor | 56.4 mm | 5.9 mm | 5.4 mm |
| Series resistor to U2 | 2.0 mm | 16.0 mm | 16.8 mm |
| **Total** | **58.4 mm** | 21.9 mm | 22.2 mm |

BCK has 54.8 mm on B.Cu, including a 32.8 mm straight run along the top edge at
y = 71.1, and 1.5 mm on F.Cu. GPIO18 (PCM_CLK) enters at header pin 12, at the
opposite end of J1 from the DAC. LRCK and DIN enter at pins 35 and 40, next to
the DAC. An earlier version of this finding compared BCK's header-to-resistor
length with the resistor-to-DAC length of LRCK and DIN; the totals above are
like for like.

B.Cu carries the GND pour, so the BCK trace cuts a 55 mm slot through it. F.Cu
has no pour outside the analog region, so for almost its whole length BCK has no
reference plane on either side. BCK runs at about 3.07 MHz and is driven with
fast Pi GPIO edges, so this trace is the most likely source of radiated emissions
on the board.

Timing is not a concern. The sub-nanosecond skew against LRCK and DIN is
negligible at these rates.

**Recommendation:** Route BCK on F.Cu. B.Cu stays continuous underneath it and
acts as its reference, and the slot goes away. If the route has to stay on B.Cu,
add a ground pour on F.Cu along its path.

**Status: Open.** The route is unchanged in v0.3. The v0.2 prototype has no
audible problem, so this is an EMC concern to weigh for v0.4.

### 3. Decoupling capacitors were too far from the pins

At review time, C7 (100 nF, CPVDD pin 1) and C11 (100 nF, DVDD pin 20) sat 3.7
and 5.6 mm from their pins, and **AVDD (pin 8) had no local capacitor at all**.
It was fed from beside pin 1 through a B.Cu detour, about 9 mm from any
capacitor. The datasheet (§12.1) asks for supply and charge-pump decoupling "as
close as possible to the device". It gives no distance; about 2 mm is a common
rule of thumb. TI's reference layout decouples CPVDD and AVDD separately. On the
datasheet pinout, pin 1 is **CPVDD** and pin 8 is **AVDD**. The review
originally labelled pin 1 as AVDD.

**Status: Fixed.** The right-hand fan-out was reorganised: C11 and C12 moved to
0402, the LDOO loop around pins 19 and 20 was removed, and C14 (100 nF) was
added at AVDD. Distances now:

| Capacitor | Serves | Pad to pad |
|---|---|---|
| C7, 100 nF | CPVDD, pin 1 | **0.78 mm** |
| C14, 100 nF (new) | AVDD, pin 8 | **0.64 mm** |
| C11, 100 nF | DVDD, pin 20 | **0.64 mm** |
| C4, 2.2 uF | CAPP / CAPM, pins 2 / 4 | 1.23 / 1.24 mm |
| C12 / C13 | LDOO, pin 18 | 1.95 / 1.57 mm |
| C10, 2.2 uF | VNEG, pin 5 | 4.6 mm |
| C8, 10 uF | CPVDD / AVDD bulk | 5.0 mm to pin 1 |
| C9, 10 uF | DVDD bulk | 5.5 mm |

C10 is a reservoir on the charge-pump output, and C8/C9 are bulk capacitors.
All three are much less sensitive to a few mm of trace than the 100 nF parts,
so they were left in place.

### 4. XSMT: leave it as designed (finding withdrawn)

An earlier version of this review recommended increasing C6 to about 2.2 uF and
feeding the divider from +3V3. **Both would be mistakes**, and that
recommendation is withdrawn:

- The +5V divider implements TI's **External Power Sense Undervoltage
  Protection Mode** (datasheet §11.3, Fig. 39). If XSMT falls from high to low
  over 6 ms or more, the DAC treats it as an undervoltage event: soft mute starts
  at 2 V and analog mute at 1.2 V. Feeding the divider from +3V3 would defeat
  this.
- A large C6 would make XSMT lag the falling 5 V rail by about 15 ms, delaying
  the mute it exists to trigger. When XSMT is used as a digital control, §9.3.3
  also requires edges faster than 20 ns.
- The power-on pop concern does not hold up. The DAC holds its outputs muted
  until it sees valid I2S clocks, and the Pi does not start those until playback
  begins.

**One real limitation.** With a 2/3 ratio, soft mute begins only once 5 V has
fallen to about 3.0 V. That is already near the dropout of the regulators that
make the 3.3 V rails. On a Pi, 5 V also collapses within a few milliseconds when
power is pulled, so this mode offers limited protection whatever the ratio. A
normal shutdown mutes cleanly anyway, because the DAC mutes when the I2S clocks
stop. No change is recommended.

### 5. Ground topology

There are two pours:

- GNDA on F.Cu, covering only the analog region (x 129 to 151, y 80 to 100)
- GND on B.Cu, covering the whole board, **including beneath the analog region**

The two are joined at a single point. As a result, the analog circuitry sits
directly above the digital ground plane. The planes couple capacitively over
that whole area even though they share only one DC connection. The top layer
has no ground pour at all over the digital two-thirds of the board, which is
what leaves B.Cu signals such as BCK without a reference (see finding 2).

The design follows a coherent split-ground philosophy. TI's own guidance points
the other way, though: *"Most engineers use a shared common ground for an
entire device. GND can be considered AGND and DGND connected"* (§12.1). Many
general references agree, preferring a single unbroken plane with separation
achieved by placement and return-path control.

**Options considered:**

- **Unified:** one GND plane on B.Cu, a ground fill on F.Cu, and the analog
  section kept together by placement. This is the more common choice today.
- **Split:** keep the split, but make B.Cu beneath the analog region GNDA as
  well, so that the analog circuitry is not above digital ground.

**Status: Decided.** The pours stay as they are for v0.3, because the v0.2
prototype has no audible noise. The single tie, R11 (0 R), is replaced by the
net tie **NT1**: a copper bridge in the same place, with no part to place. A
ferrite bead there was considered and rejected. It would put impedance in the
return path of the I2S lines that cross between the two grounds. Revisit the
unified approach if v0.3 shows noise or fails EMC.

### 6. The ID EEPROM was drawn but not fitted

At review time, U1 (CAT24C256), JP1 (write protect), R1/R2 (3.9 k pull-ups) and
C1 were in the schematic but had no footprints and were not on the PCB. Without
the EEPROM the board is not HAT-spec compliant. The Pi cannot identify it or
apply its overlay automatically, so every user has to edit `config.txt` by hand.

**Status: Fixed.** All five are fitted on ID_SD and ID_SC (GPIO0/1, header pins
27/28), with U1 at address 0x50:

- U1 is a TSSOP-8 in the strip above the jacks. Both ID lines run on F.Cu, and
  B.Cu is used only for short hops under the power rails.
- JP1 is a solder jumper on the bottom side, made of copper pads with no part.
  Boards ship with it open so the EEPROM can be programmed; bridge it afterwards
  to write-protect.
- The image in `hardware/eeprom/` is a 906-byte HAT v1 image with vendor
  `obcecado.com`, `product_id` 0x0001 and `product_ver` 0x0003. It embeds the
  sound-card overlay and the GPIO settings. GPIO0/1 are deliberately absent from
  its GPIO map, because the spec reserves them.
- Program it with `make flash` on a Pi. `eepflash.sh` brings up the I2C bus on
  GPIO0/1 itself.

### 7. No ESD or series protection on the RI jack

J4's tip connects directly to GPIO25. J4 is a user-accessible connector, so an
electrostatic discharge into the jack goes straight to a SoC pin.

On a TX-8020 the RI line idles low and has no pull-up, so it presents no DC
hazard. It reads low even against the Pi's internal pull-up. Other receiver
models have not been checked.

**Recommendation:** Add a low-capacitance ESD diode to GND at J4, and a series
resistor between J4 and GPIO25. The receiver holds the line low through an
unknown impedance, and a series resistor forms a divider with it. Measure the
receiver-side pull-down before choosing a value, so that a logic high still
reaches the receiver at a valid level.

**Status: Open.**

### 8. Output impedance

The 470 R series resistors are fine for driving a line input (10 k and above).
With 32 R headphones, though, the attenuation is about 24 dB. People will plug
headphones into a 3.5 mm jack.

**Recommendation:** Make it clear that J2 is a line output; its silkscreen
currently reads `Audio`. If driving headphones matters, reduce the series
resistance and rescale the filter capacitor to keep the corner frequency.

**Status: Open.**

### 9. Logo silkscreen was printed over the RI jack pads

Found after the review. The skull logo's silkscreen covered 60 to 89% of J4's
solder pads (T, R1 and R2). The plot settings did not subtract the solder mask
from the silkscreen, so the silkscreen Gerber printed ink onto those pads,
risking poor solder joints on the RI jack. The project's DRC has
`silk_over_copper` set to ignore, which is why DRC did not report it.

**Status: Fixed.** The plot settings now subtract the mask from the silkscreen,
so the silkscreen is clipped at every pad opening. The logo is unchanged
elsewhere. KiCad's 3D viewer still draws the overlap unless its own "clip
silkscreen at solder mask edges" option is turned on; the Gerbers are what
count.

## Remaining changes for v0.4, in order

1. Route BCK on F.Cu (finding 2).
2. Add an ESD diode and a series resistor on J4, after measuring the
   receiver-side pull-down (finding 7).
3. Decide whether J2 should drive headphones; at least label it as a line
   output (finding 8).
4. Add the 4 missing `PWR_FLAG`s so ERC is clean.
5. Revisit the ground topology only if v0.3 shows noise or fails EMC
   (finding 5).

## Related

- `install/MANIFEST.md`: the software stack, measured RI timing, and verified RI
  codes
- `hardware/eeprom/`: the HAT ID EEPROM image and its build
- `production/v0.3/README.md` (on `feat/v0.3-caps-eeprom`): order settings,
  parts and EEPROM programming for the first v0.3 batch

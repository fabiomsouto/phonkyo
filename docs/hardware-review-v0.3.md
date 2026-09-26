# phonkyo v0.3 hardware review

**Date:** 2026-09-23
**Design reviewed:** `phonkyo.kicad_sch` / `phonkyo.kicad_pcb` at commit `6e10180` ("add: revision 0.3"), KiCad 8 format
**Board:** 2-layer, 65 x 30 mm pHAT for the Raspberry Pi Zero 2 W

## Scope and method

The KiCad files were parsed directly to extract placement, routing, zones, vias
and silkscreen, and distances were computed from pad coordinates. Circuit
findings were checked against the PCM5102A datasheet (`adc/pcm5102a.pdf`, TI
SLAS859C).

A later KiCad 10 ERC/DRC run found **0 unconnected items and 0
schematic-parity errors**. The only ERC errors were 4 missing `PWR_FLAG`s, on
+5V, +3V3, GND and GNDA, which are bookkeeping rather than real faults.

Only **v0.2** has been built. A v0.2 board was exercised end to end on a Pi Zero
2 W with an Onkyo TX-8020 receiver: DAC output on both channels, RI transmit, and
RI receive. None of the findings below has been confirmed or ruled out on
fabricated v0.3 hardware, and no EMC measurements have been made.

## Summary

The analog design is sound. The analog/digital partition runs cleanly through
the DAC, the output filter is placed well, and the grounding follows a
deliberate single-point scheme. The significant issues are in layout and product
readiness rather than circuit design:

1. The plot settings still write to `production/v0.2`, so generating v0.3
   output would overwrite the v0.2 fabrication files.
2. The I2S bit clock, the fastest signal on the board, has the longest route,
   and nearly all of it has no reference plane.
3. The 100 nF decoupling capacitors are 3.7 to 5.6 mm from the pins they serve.
4. AVDD (pin 8) has no local decoupling at all.
5. The ID EEPROM is drawn in the schematic but not fitted, so the board is not
   HAT-spec compliant.
6. There is no ESD protection on the user-accessible RI jack.

## What is done well

- **The analog/digital split runs through U2 itself.** Analog pins 1 to 9 (AVDD,
  CAPP, AGND, CAPM, VNEG, OUTL, OUTR) sit at x = 148.3 mm, inside the GNDA pour.
  Digital pins 17 to 20 sit at x = 154.0 mm, outside it.
- **Single-point star ground.** R11 (0 R) is the only DC connection between GNDA
  and GND.
- **Tight output filter.** R3 and R4 are 1.8 mm from OUTL and OUTR. The RC is
  470 R with 2.2 nF, giving a corner at about 154 kHz.
- **No DC-blocking capacitors on the outputs.** This is correct for the
  PCM5102A: its charge pump produces ground-centred outputs, and adding coupling
  capacitors here is a common mistake.
- **22 R series damping** on all three I2S lines (R7, R8, R9).
- **BCK avoids the analog region.** None of its route passes over the GNDA pour.
- **Ground stitching around the DAC.** Nine GND vias. Most cluster around U2's
  digital pins (x 152 to 156.5 mm), one sits at the R11 star point, and one takes
  U2's DGND pin to the bottom plane.
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

### 1. Plot output points at the v0.2 production folder

The v0.3 board's plot settings still have `outputdirectory "production/v0.2"`.
Plotting v0.3 Gerbers without changing this writes them over the v0.2
fabrication files, which are the ones that were actually manufactured.

**Recommendation:** Set the output directory to `production/v0.3` before
generating fabrication files. The repo also has no BOM or position files for
v0.3 yet.

**Correction.** An earlier version of this review said the board had no
functional silkscreen and that the jacks were unlabelled. That was wrong. v0.2
and v0.3 both carry knockout labels: `Remote` by J4, `Audio` by J2, `DAC`, the
board name, and a specs block on the back. The earlier text-extraction step
missed them. Reference designators are hidden, which only matters for rework
and debugging. The jack mix-up during bring-up happened despite the labels.

### 2. The I2S bit clock has the worst route on the board

| | |
|---|---|
| Total length | 56.4 mm |
| On B.Cu | 54.8 mm, including a 32.8 mm straight run along the top edge at y = 71.1 |
| On F.Cu | 1.5 mm |

GPIO18 (PCM_CLK) enters at header pin 12, at the opposite end of J1 from the
DAC. LRCK and DIN enter at pins 35 and 40, next to the DAC, and are only about
16 mm long.

B.Cu carries the GND pour, so the BCK trace cuts a 55 mm slot through it. F.Cu
has no pour outside the analog region, so for almost its whole length BCK has no
reference plane on either side. BCK runs at about 3.07 MHz and is driven with
fast Pi GPIO edges, so this trace is the most likely source of radiated emissions
on the board.

Timing is not a concern. The 0.3 ns of skew against LRCK and DIN is negligible
at these rates.

**Recommendation:** Route BCK on F.Cu. B.Cu stays continuous underneath it and
acts as its reference, and the slot goes away. If the route has to stay on B.Cu,
add a ground pour on F.Cu along its path.

### 3. Decoupling capacitors are too far from the pins

| Capacitor | Serves | Distance to pin |
|---|---|---|
| C7, 100 nF | CPVDD, pin 1 | **3.69 mm** |
| C11, 100 nF | DVDD, pin 20 | **5.62 mm** |
| C10, 2.2 uF | VNEG, pin 5 | **5.67 mm** |
| C8, 10 uF | CPVDD / AVDD | 5.17 mm |
| none | **AVDD, pin 8** | **~9 mm to the nearest cap** |
| C9, 10 uF | DVDD | 6.77 mm |
| C12 / C13 | LDOO, pin 18 | 2.75 / 2.88 mm |
| C4, 2.2 uF | CAPP / CAPM | 2.28 mm |

The datasheet (§12.1) asks for supply and charge-pump decoupling "as close as
possible to the device". It gives no distance; about 2 mm is a common rule of
thumb. On the datasheet pinout, pin 1 is **CPVDD** (the charge-pump supply) and
pin 8 is **AVDD**. The review originally labelled pin 1 as AVDD.

The 100 nF capacitors handle high-frequency decoupling, where trace inductance
matters most. At 5.6 mm, that inductance undoes most of their benefit. C10 is a
2.2 uF reservoir on the charge-pump output, so a few nH of extra trace matters
far less there, and it can wait for a wider re-layout. The bulk 10 uF
capacitors are also less sensitive to placement.

**AVDD (pin 8) has no local capacitor at all.** It is fed from beside pin 1 via
a B.Cu detour, about 9 mm from any capacitor. TI's reference layout decouples
CPVDD and AVDD separately.

**Recommendation:** Place C7 and C11 at their pins, and add a 100 nF capacitor
at pin 8.

**Status:** Done on `feat/v0.3-caps-eeprom`, DRC clean. Pad-to-pad distances
are now: C7 to pin 1, 0.78 mm; C11 to pin 20, 0.64 mm; and the new C14
(100 nF) to AVDD pin 8, 0.64 mm. To do this, the right-hand fan-out was
reorganised: C11 and C12 moved to 0402, and the LDOO loop around pins 19 and
20 was removed. C10 is unchanged.

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

The two are joined only at R11. As a result, the analog circuitry sits directly
above the digital ground plane. The planes couple capacitively over that whole
area even though they share only one DC connection. The top layer has no ground
pour at all over the digital two-thirds of the board, which is what leaves B.Cu
signals such as BCK without a reference (see finding 2).

The design follows a coherent split-ground philosophy and evidently works. TI's
own guidance points the other way, though: *"Most engineers use a shared common
ground for an entire device. GND can be considered AGND and DGND connected"*
(§12.1). Many general references agree, preferring a single unbroken plane with
separation achieved by placement and return-path control. The current layout
falls between the two approaches.

**Recommendation:** Choose one approach and apply it consistently:

- **Unified:** one GND plane on B.Cu, a ground fill on F.Cu, and the analog
  section kept together by placement. This is the more common choice today.
- **Split:** keep the split, but make B.Cu beneath the analog region GNDA as
  well, so that the analog circuitry is not above digital ground.

### 6. The ID EEPROM is drawn but not fitted

U1 (CAT24C256), JP1 (write protect), R1/R2 (3.9 k pull-ups) and C1 are in the
schematic but have no footprints and are not on the PCB. Without the EEPROM the
board is not HAT-spec compliant. The Pi cannot identify it or apply its overlay
automatically, so every user has to edit `config.txt` by hand.

The EEPROM image is already built and validated in `hardware/eeprom/`: a
906-byte HAT v1 image that embeds the sound-card overlay and the GPIO settings.
Once U1 is fitted, the board configures itself at boot.

**Recommendation:** Assign footprints and place U1, R1, R2, JP1 and C1 on ID_SD
and ID_SC (GPIO0/1, header pins 27/28), with U1 at address 0x50. Ship with JP1
open so the EEPROM can be programmed in production, then close it.

**Status:** Fitted on `feat/v0.3-caps-eeprom`. U1 is a TSSOP-8 in the strip
above the jacks, and JP1 is on the bottom side. Both ID lines run on F.Cu,
with B.Cu used only for short hops under the power rails. The image's
`product_ver` is now 0x0003 to match.

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

### 8. Output impedance

The 470 R series resistors are fine for driving a line input (10 k and above).
With 32 R headphones, though, the attenuation is about 24 dB. People will plug
headphones into a 3.5 mm jack.

**Recommendation:** At minimum, label J2 as a line output (see finding 1). If
driving headphones matters, reduce the series resistance and rescale the filter
capacitor to keep the corner frequency.

## Suggested v0.4 changes, in order

1. Plot settings: point the output directory at `production/v0.3`.
2. Route BCK on F.Cu.
3. ~~Decoupling: C7, C11 at their pins; 100 nF at AVDD pin 8.~~ Done (C14).
4. Settle on a ground topology (finding 5). TI recommends a common ground.
5. ~~Fit the ID EEPROM (U1, R1, R2, JP1, C1).~~ Done.
6. Add an ESD diode and a series resistor on J4 after measuring the
   receiver-side pull-down.
7. Add the 4 missing `PWR_FLAG`s so ERC is clean.

## Related

- `install/MANIFEST.md`: the software stack, measured RI timing, and verified RI
  codes
- `hardware/eeprom/`: the HAT ID EEPROM image and its build

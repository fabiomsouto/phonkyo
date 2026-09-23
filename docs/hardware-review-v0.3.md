# phonkyo v0.3 hardware review

**Date:** 2026-09-23
**Design reviewed:** `phonkyo.kicad_sch` / `phonkyo.kicad_pcb` at commit `6e10180` ("add: revision 0.3"), KiCad 8 format
**Board:** 2-layer, 65 x 30 mm pHAT for the Raspberry Pi Zero 2 W

## Scope and method

The KiCad files were parsed directly to extract placement, routing, zones, vias
and silkscreen, and distances were computed from pad coordinates. No DRC or ERC
was run; `kicad-cli` was not available when this review was written.

Only **v0.2** has been built. A v0.2 board was exercised end to end on a Pi Zero
2 W with an Onkyo TX-8020 receiver: DAC output on both channels, RI transmit, and
RI receive. None of the findings below has been confirmed or ruled out on
fabricated v0.3 hardware, and no EMC measurements have been made.

## Summary

The analog design is sound. The analog/digital partition runs cleanly through
the DAC, the output filter is placed well, and the grounding follows a
deliberate single-point scheme. The significant issues are in layout and product
readiness rather than circuit design:

1. No functional silkscreen. The two identical jacks are unlabelled.
2. The I2S bit clock, the fastest signal on the board, has the longest route,
   and nearly all of it has no reference plane.
3. The 100 nF decoupling capacitors are 3.7 to 5.6 mm from the pins they serve.
4. The XSMT mute network gives effectively no soft-start.
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
- **Mechanical.** The mounting holes are on the 58 x 23 mm Pi Zero pattern, and
  there is a keepout for the Pi's PoE header.

## Findings

Findings are ordered by value per effort, not by severity.

### 1. No functional silkscreen

Every reference designator is hidden (`(hide yes)`), and the board has no
free-standing silkscreen text. All 650 F.SilkS elements are artwork. J2 (line
out) and J4 (RI) are the same PJ-320D part, mounted next to each other, with no
labels.

This caused a real problem during bring-up. The cables were plugged in swapped,
and diagnosing it took about twenty minutes. A buyer will run into the same thing
on first use.

**Recommendation:** Add `LINE OUT` and `RI` labels at J2 and J4. Consider showing
reference designators on the back silkscreen to help with rework. This is the
cheapest change in this review and would prevent the most confusion.

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
| C7, 100 nF | AVDD, pin 1 | **3.69 mm** |
| C11, 100 nF | DVDD, pin 20 | **5.62 mm** |
| C10, 2.2 uF | VNEG, pin 5 | **5.67 mm** |
| C8, 10 uF | AVDD | 5.17 mm |
| C9, 10 uF | DVDD | 6.77 mm |
| C12 / C13 | LDOO, pin 18 | 2.75 / 2.88 mm |
| C4, 2.2 uF | CAPP / CAPM | 2.28 mm |

The 100 nF capacitors handle high-frequency decoupling and should be within about
2 mm of the pin. At 5.6 mm, trace inductance undoes most of their benefit. C10
decouples the charge-pump output and deserves the same treatment. The bulk 10 uF
capacitors are less sensitive to placement.

**Recommendation:** Move C7, C11 and C10 to the pins they serve, on the same
layer and with short, direct connections.

### 4. The XSMT soft-start is too short to work

R5 (10 k, to +5 V) and R6 (20 k, to GND) set XSMT to 3.33 V, filtered by C6
(2.2 nF). The Thevenin resistance is 6.67 k, so

    tau = 6.67 k x 2.2 nF ~= 15 us

A useful power-on mute delay is roughly 10 to 100 ms. At 15 us, the DAC unmutes
almost as soon as it has power, which is a likely cause of a turn-on pop into the
amplifier. This has not been confirmed on hardware.

The divider also runs from +5 V, which can rise before the Pi's 3V3 rail. XSMT
can therefore be driven high before DVDD is valid, and its steady state
(3.33 V) is slightly above the 3.3 V rail.

**Recommendation:** Increase C6 to about 2.2 uF (tau ~= 15 ms) and feed the
divider from +3V3. Alternatively, drive XSMT from a spare GPIO. The pin defaults
low at boot, so the DAC starts muted, and software can then mute it around amp
power transitions. That would also give phonkyo a proper software mute.

### 5. Ground topology

There are two pours:

- GNDA on F.Cu, covering only the analog region (x 129 to 151, y 80 to 100)
- GND on B.Cu, covering the whole board, **including beneath the analog region**

The two are joined only at R11. As a result, the analog circuitry sits directly
above the digital ground plane. The planes couple capacitively over that whole
area even though they share only one DC connection. The top layer has no ground
pour at all over the digital two-thirds of the board, which is what leaves B.Cu
signals such as BCK without a reference (see finding 2).

The design follows a coherent split-ground philosophy and evidently works. Many
current references, however, recommend a single unbroken ground plane, with
separation achieved by placement and return-path control rather than by
splitting the plane. Either approach is defensible. The current layout falls
between them.

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
901-byte HAT v1 image that embeds the sound-card overlay and the GPIO settings.
Once U1 is fitted, the board configures itself at boot.

**Recommendation:** Assign footprints and place U1, R1, R2, JP1 and C1 on ID_SD
and ID_SC (GPIO0/1, header pins 27/28), with U1 at address 0x50. Ship with JP1
open so the EEPROM can be programmed in production, then close it.

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

1. Silkscreen: label `LINE OUT` and `RI`, and show reference designators.
2. Route BCK on F.Cu.
3. Move C7, C11 and C10 to within 2 mm of their pins.
4. Change C6 to about 2.2 uF and feed the XSMT divider from +3V3, or drive XSMT
   from a GPIO.
5. Settle on a ground topology (finding 5).
6. Fit the ID EEPROM (U1, R1, R2, JP1, C1).
7. Add an ESD diode and a series resistor on J4 after measuring the receiver-side
   pull-down.

## Related

- `install/MANIFEST.md`: the software stack, measured RI timing, and verified RI
  codes
- `hardware/eeprom/`: the HAT ID EEPROM image and its build

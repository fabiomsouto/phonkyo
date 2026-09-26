# phonkyo HAT ID EEPROM
#
#   make            build phonkyo.eep
#   make verify     build and dump it back for inspection
#   make flash      program and verify a fitted EEPROM with a fresh UUID
#                   (run on the Pi, HAT attached, JP1 open)
#
# NOTE: -v1 is required. eepmake now defaults to the HAT+ format (Pi 5 era),
# which drops gpio_drive/gpio_slew/gpio_hysteresis and is not what a Zero 2 W
# firmware expects. Without -v1 the build fails with
# "'gpio_drive' not supported on HAT+".

SHELL   := /bin/bash
EEPROM  := 24c256
SETTINGS := phonkyo-eeprom.txt
DTS      := phonkyo-hat.dts

all: phonkyo.eep

phonkyo-hat.dtbo: $(DTS)
	dtc -@ -I dts -O dtb -o $@ $<

phonkyo.eep: $(SETTINGS) phonkyo-hat.dtbo
	eepmake -v1 $(SETTINGS) $@ phonkyo-hat.dtbo

verify: phonkyo.eep
	eepdump phonkyo.eep phonkyo-dump.txt
	@grep -vE '^\s*#|^\s*$$' phonkyo-dump.txt | head -20

# Writes the EEPROM on a fitted HAT. JP1 (write protect) must be OPEN.
# eepflash.sh uses /dev/i2c-0 or i2c-9 if present; otherwise it loads the
# i2c-gpio overlay on GPIO0/1 (the ID pins) as bus 9 by itself, so no
# config.txt change is needed. Nothing else may hold those pins.
#
# The image is rebuilt on every flash: product_uuid is zero in the settings, so
# eepmake generates a new UUID on each build and every board gets its own. The
# chip is then read back and compared with the image.
flash: phonkyo-hat.dtbo
	$(MAKE) -B phonkyo.eep
	sudo eepflash.sh -y -w -f=phonkyo.eep -t=$(EEPROM)
	sudo eepflash.sh -y -r -f=readback.eep -t=$(EEPROM)
	sudo chown $$(id -u):$$(id -g) readback.eep
	cmp -n $$(stat -c%s phonkyo.eep) phonkyo.eep readback.eep
	@grep -m1 product_uuid <(eepdump phonkyo.eep /dev/stdout 2>/dev/null) || true
	@echo "EEPROM written and verified. Bridge JP1 to write-protect it."

clean:
	rm -f phonkyo.eep phonkyo-hat.dtbo phonkyo-dump.txt readback.eep

.PHONY: all verify flash clean

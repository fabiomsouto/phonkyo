# Phonkyo

A PiHat for Onkyo RI-enabled devices.

Phonkyo allows you to control your Onkyo home theater system using a Raspberry Pi. It's a great way to automate your home entertainment experience, particularly if you use tools such as Home Assistant in your setup.

## Release notes

### v0.1

Initial release of the Phonkyo project. There is no ID EEPROM present yet, and all the hat exposes is a 3.5mm jack that's connected to the GPIO pin 25 on the Raspberry Pi. Use a mono or a stereo male-to-male cable to connect your Onkyo remote control to the hat.

### v0.2

This release adds the much acclaimed DAC to the design, allowing to expand the functionality of the device beyond a simple
remote control for your home theater system with RI. Depending on your needs, you will now be able to:
- Control your remote interface home theater to your liking
- Expose the Raspberry Pi as a Spotify device
- Expose the Raspberry Pi as an Airplay device

## Related projects and documentation

[https://macsbug-wordpress-com.translate.goog/2021/02/19/web-radio-of-m5stack-pcm5102a-i2s-dac/](https://macsbug-wordpress-com.translate.goog/2021/02/19/web-radio-of-m5stack-pcm5102a-i2s-dac/)
[https://www.ti.com/lit/ds/symlink/pcm5102a.pdf?ts=1728009135968](https://www.ti.com/lit/ds/symlink/pcm5102a.pdf?ts=1728009135968)
[https://shop.pimoroni.com/products/phat-dac](https://shop.pimoroni.com/products/phat-dac)
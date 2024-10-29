# Phonkyo

A PiHat for Onkyo RI-enabled devices, hence the name (PiHat Onkyo).

Phonkyo allows you to control your Onkyo home theater system using a Raspberry Pi. It's a great way to automate your home entertainment experience, 
particularly if you use tools such as Home Assistant in your setup.

Version 0.2 now allows you to use your Raspberry Pi as a Spotify device, Airplay device, Plexamp player, thanks to
the addition of a PCM5102A DAC.

I believe this device could also be used for other RI-enabled devices, such as Marantz, but I have no way to test it 
(and therefore implement support)!

## Release notes

### v0.1

Initial release of the Phonkyo project. There is no ID EEPROM present yet, and all the hat exposes is a 3.5mm jack that's 
connected to the GPIO pin 25 on the Raspberry Pi. Use a mono or a stereo male-to-male cable to connect your Onkyo remote control to the hat.

### v0.2

This release adds the much acclaimed PCM5102A DAC to the design, allowing to expand the functionality of the device beyond a simple
remote control for your home theater system with RI. Depending on your needs, you will now be able to:
- Control your remote interface home theater to your liking
- Expose the Raspberry Pi as a Spotify device
- Expose the Raspberry Pi as an Airplay device
- Expose the Raspberry Pi as a Plex headless player

### v0.3

This release improves on the board design, particularly around power and ground rails, and removes the SCK jumper, as I don't
predict the need for an external clock source in this particular design.

## Related projects and documentation

[Macsbug article on PCM5102A](https://macsbug-wordpress-com.translate.goog/2021/02/19/web-radio-of-m5stack-pcm5102a-i2s-dac/)

[TI PCM5102A](https://www.ti.com/lit/ds/symlink/pcm5102a.pdf?ts=1728009135968)

[phatDAC](https://shop.pimoroni.com/products/phat-dac) as inspiration
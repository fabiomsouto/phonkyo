# Phonkyo software manifest

Everything the phonkyo software stack needs on top of a stock OS image.
Intended as the source of truth for `phonkyo-setup.sh`.

## Target platform

| | |
|---|---|
| Board | Raspberry Pi Zero 2 W (BCM2710A1, ARMv8) |
| HAT | phonkyo v0.2 (PCM5102A DAC + RI jack) |
| OS | Raspberry Pi OS **Lite 64-bit**, Trixie (Debian 13) |
| Verified image | `2026-09-15-raspios-trixie-arm64-lite.img.xz` |
| Kernel at time of writing | `6.18.50+rpt-rpi-v8` |

> The 64-bit image requires a Zero 2 W. The original Zero / Zero W (BCM2835,
> ARMv6) cannot boot it — no `kernel.img`, no `bcm2835-*.dtb`.

## 1. First-boot provisioning

Trixie uses **cloud-init**, *not* `custom.toml` (that was Bookworm and is
silently ignored on Trixie). Seed files go on the boot partition, which
cloud-init reads via `seedfrom: file:///boot/firmware`:

- `user-data` — hostname, user, SSH keys, `ssh_pwauth: false`
- `network-config` — netplan v2: wlan0 + usb0
- `meta-data` — `instance_id` (change it to force re-provisioning)

`/boot/firmware/ssh` (empty file) makes `sshswitch.service` enable
`ssh.service`, which is **not** enabled by default on Lite.

## 2. Boot configuration — `/boot/firmware/config.txt`

```ini
#dtparam=audio=on                 # onboard audio off; the PCM5102A is the output
dtoverlay=vc4-kms-v3d,noaudio     # HDMI audio off, so the DAC is card 0

[all]
dtoverlay=dwc2                    # USB ethernet gadget (SSH fallback)
dtoverlay=hifiberry-dac           # PCM5102A via I2S
```

`/boot/firmware/cmdline.txt` gains `modules-load=dwc2,g_ether` after `rootwait`.

The PCM5102A needs no I2C control, so `hifiberry-dac` is the correct overlay
and registers unconditionally — the card appears even with no HAT attached.

## 3. Packages from Debian/RPi repos

```
alsa-utils avahi-daemon          # present on Lite already
python3-lgpio gpiod python3-gpiozero
```

**`pigpiod` is gone from Trixie.** Only client-side remnants survive
(`python3-pigpio`, `pigpio-tools`, `libpigpiod-if*`, one tagged "deprecated")
and there is no daemon for them to talk to. RI control uses **lgpio** instead —
same author as pigpio, its designated successor, and supported on Pi 5.

## 4. Spotify Connect — raspotify

Third-party apt repo:

```sh
curl -sSL https://dtcooper.github.io/raspotify/key.asc \
  | sudo tee /usr/share/keyrings/raspotify_key.asc >/dev/null
echo "deb [signed-by=/usr/share/keyrings/raspotify_key.asc] https://dtcooper.github.io/raspotify raspotify main" \
  | sudo tee /etc/apt/sources.list.d/raspotify.list >/dev/null
sudo apt-get update && sudo apt-get install -y raspotify
```

Installed version: `0.48.2~librespot.v0.8.0-9c7d756`. Enables itself at boot.
Stock `/etc/raspotify/conf` works as-is — card 0 is the DAC.

## 5. AirPlay 2 — nqptp + shairport-sync (from source)

Debian ships `shairport-sync 4.3.7` but **AirPlay 1 only**, and `nqptp`
is not packaged at all. AirPlay 2 requires both.

Build dependencies:

```
build-essential git autoconf automake libtool
libpopt-dev libconfig-dev libasound2-dev
avahi-daemon libavahi-client-dev libssl-dev libsoxr-dev
libplist-dev libplist-utils libsodium-dev
libavutil-dev libavcodec-dev libavformat-dev
uuid-dev libgcrypt-dev xxd
```

> `plistutil` is in **`libplist-utils`**, not `libplist-dev`. Omitting it
> fails at `./configure`, not at compile time.

```sh
git clone --depth 1 https://github.com/mikebrady/nqptp.git
cd nqptp && autoreconf -fi && ./configure --with-systemd-startup && make -j2 && sudo make install

git clone --depth 1 https://github.com/mikebrady/shairport-sync.git
cd shairport-sync && autoreconf -fi && ./configure \
    --sysconfdir=/etc --with-alsa --with-soxr --with-avahi \
    --with-ssl=openssl --with-systemd --with-airplay-2 \
  && make -j2 && sudo make install
```

Zero 2 W has 512 MB RAM — use `-j2`, not `-j4`.

## 6. Plexamp headless

Needs `nodejs` (Debian Trixie ships 20.19.2, which satisfies it).

```sh
sudo apt-get install -y nodejs
curl -sSL -o /tmp/plexamp.tar.bz2 \
  https://plexamp.plex.tv/headless/Plexamp-Linux-headless-v4.13.2.tar.bz2
sudo tar -xjf /tmp/plexamp.tar.bz2 -C /opt
sudo chown -R "$USER":"$USER" /opt/plexamp
```

### The claim step resists scripting

First run is **interactive and the token is single-use** — it is consumed the
moment it is submitted. A script that supplies the token but fails at the
*second* prompt (player name) still burns the token and writes no config.

Neither a plain pipe nor `ssh -tt` works: the first needs a TTY the prompts
never get, the second echoes both lines into the *first* prompt before the
second appears. Use `expect`, which waits for each prompt:

```expect
#!/usr/bin/expect -f
set timeout 180
spawn node js/index.js
expect -re "claim token:"        ; send -- "[lindex $argv 0]\r"
expect -re "name \\(e.g."        ; send -- "[lindex $argv 1]\r"
expect -re "signed in and ready"
sleep 20
```

Settings land in `~/.local/share/Plexamp/Settings/`.

### systemd unit

The shipped `/opt/plexamp/plexamp.service` hardcodes `User=pi` and
`/home/pi/plexamp`. Rewrite for the real user and install path; Plexamp reads
its settings from the service user's `~/.local/share/Plexamp`.

## 7. Diagnostics tooling

`avahi-utils` is **not** on the Lite image. Without it `avahi-browse` does not
exist, and its absence is indistinguishable from "no services are advertising".
Install it before debugging any mDNS/AirPlay discovery problem.

## 8. Nice to have

- `log2ram` — was on the original install; reduces SD card writes noticeably
  on an appliance that logs continuously.
- journald is **volatile** by default on this image. Persistent logs need
  `/etc/systemd/journald.conf.d/` with `Storage=persistent`; weigh against flash wear.

## Status

- [x] Boot config / DAC overlay — verified, tone out both channels
- [x] python3-lgpio
- [x] raspotify
- [x] nqptp
- [x] nqptp + shairport-sync with AirPlay 2 — `01078ad-AirPlay2-smi10-OpenSSL-Avahi-ALSA-soxr`
- [x] Plexamp 4.13.2 claimed as `phonkyo`, systemd unit rewritten
- [x] avahi-utils
- [x] **RI control on GPIO25 via lgpio** — verified end to end on a real receiver
- [x] `phonkyo-monitor` playback-follow service
- [ ] `phonkyo-setup.sh` installer
- [ ] log2ram

## 9. RI control timing (measured, Pi Zero 2 W)

`pigpio` is the wrong tool here for two independent reasons: it is no longer
packaged on Trixie, **and** its DMA timebase defaults to the PCM peripheral —
the same block the I2S DAC drives (`pigpiod -t 0` switches it to PWM, but that
is a footgun to ship). `lgpio` goes through `/dev/gpiochip0` and touches
neither PCM nor PWM, so there is no contention with the DAC.

The cost is software-generated timing. Measured worst-case error on a 1000 us
pulse, 400 samples per cell:

| Load | normal scheduling | SCHED_FIFO prio 50 |
|---|---|---|
| I2S idle | +12.1 us | +11.5 us |
| I2S streaming | +57.9 us | +48.2 us |
| I2S + 4 saturated cores | **+4005 us** | **+2.5 us** |

**`SCHED_FIFO` is mandatory, not an optimisation.** Under CPU contention,
ordinary scheduling produces 4 ms errors against a 1-2 ms bit period — every
frame corrupt. With real-time priority the same load costs 2.5 us.

I2S activity alone is not a problem: ~48 us worst case is under 5% of a bit
period, against roughly 20% receiver tolerance.

One `lgpio.gpio_write` costs ~6.8 us, so the transmitter uses absolute
deadlines rather than relative sleeps to stop that accumulating across a frame.
Measured end-to-end: 3.43 us worst-case edge error over 270 edges.

Installer implication: the RI service needs `CAP_SYS_NICE` (or root), e.g.
`AmbientCapabilities=CAP_SYS_NICE` in its unit.

### Unverified

- Protocol constants (3000/1000/1000/2000 us, 12 bits) are from community
  reverse-engineering, not confirmed against hardware.
- Command codes are unknown; `ri.sniff()` exists to learn them from a real unit.
- **Line polarity is unconfirmed.** GPIO25 connects to the J4 tip with no series
  resistor, clamp or level shifter. If the RI bus idles high at 5 V (as some
  sources describe) that is out of spec for a 3.3 V pin and v0.3 needs
  protection there. Measure tip-to-sleeve before connecting.

## 10. Playback-follow service (phonkyo-monitor)

Watches the DAC and drives the amp over RI: power on + select DOCK when audio
starts, power off after an idle timeout.

### Detecting playback

Do **not** key on `subdevices_avail` in `/proc/asound/.../info` ("is the device
claimed"). Plexamp opens the PCM at startup and holds it in `PREPARED` state
indefinitely while idle, so that test reads as permanent playback and the amp
never switches off. The previous phonkyo build had this bug.

Require `state: RUNNING` **and** `hw_ptr` advancing between polls. That
separates real playback from a device that is merely open, or open and stalled.

### Only switch off what you switched on

Track power state starting at `False`, so the service never sends `power_off`
for an amp it did not power up. Otherwise switching the receiver on yourself
for vinyl or TV gets it silently killed after the idle timeout.

### systemd gotchas

- **`CAP_SYS_NICE` is required** for `SCHED_FIFO`. Without it the transmitter
  refuses to send rather than emit frames it cannot time reliably.
- **lgpio needs a writable working directory.** It creates `.lgd-nfy*`
  notification FIFOs in the CWD; under `ProtectSystem=strict` a `/opt` working
  directory is read-only and the module fails at *import* with
  `FileNotFoundError: '.lgd-nfy-3'`. Use `RuntimeDirectory=phonkyo` plus
  `WorkingDirectory=/run/phonkyo`.
- Service user needs supplementary groups `gpio` (for `/dev/gpiochip0`) and
  `audio`.

### Verified RI command codes

Recovered from the previous working install and confirmed against hardware:

| Code | Action |
|---|---|
| `0x17F` | power on **and** select DOCK |
| `0x170` | select DOCK |
| `0x420` | power off |
| `0x2B0/1/2` | dimmer high / mid / low |

The `...F` suffix means "power on and select this input"; `...0` selects only.
Published tables disagree about which family is DOCK — `0x1AF` is a different
input and does nothing useful here. Trust `0x17F`.

Each command is sent **3x** with a **50 ms idle gap** between frames; RI has no
acknowledgement, so repetition is how reliability is achieved.

## Verified end state

```
nqptp            enabled active
shairport-sync   enabled active   :7000     AirPlay 2
raspotify        enabled active   :46651    Spotify Connect
plexamp          enabled active   :32500    Plexamp
avahi-daemon     enabled active
card 0: sndrpihifiberry - snd_rpi_hifiberry_dac
```

mDNS advertises `2CCF…@phonkyo` (_raop), `phonkyo` (_airplay, vv=2) and
`raspotify (phonkyo)` (_spotify-connect). No service holds the ALSA device
while idle, so the three players coexist on the single card.

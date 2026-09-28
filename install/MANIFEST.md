# Phonkyo software manifest

Everything the phonkyo software stack needs on top of a stock OS image.
Intended as the source of truth for `phonkyo-setup.sh`.

## Target platform

| | |
|---|---|
| Board | Raspberry Pi Zero 2 W (BCM2710A1, ARMv8) |
| HAT | phonkyo v0.2 (PCM5102A DAC + RI jack), the hardware everything here was verified on. v0.3 adds the ID EEPROM and RI protection and has not been built yet |
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
libglib2.0-dev          # for the D-Bus/MPRIS interfaces
```

> `plistutil` is in **`libplist-utils`**, not `libplist-dev`. Omitting it
> fails at `./configure`, not at compile time.

```sh
git clone --depth 1 https://github.com/mikebrady/nqptp.git
cd nqptp && autoreconf -fi && ./configure --with-systemd-startup && make -j2 && sudo make install

git clone --depth 1 https://github.com/mikebrady/shairport-sync.git
cd shairport-sync && autoreconf -fi && ./configure \
    --sysconfdir=/etc --with-alsa --with-soxr --with-avahi \
    --with-ssl=openssl --with-airplay-2 \
    --with-dbus-interface --with-mpris-interface \
  && make -j2 && sudo make install
```

`make install` installs the systemd unit (in `/usr/local/lib/systemd/system/`)
by itself when systemd is present. An earlier version of this manifest passed
`--with-systemd`, which configure ignores as unrecognised; the real flag is
`--with-systemd-startup`, and it isn't needed.

The D-Bus and MPRIS interfaces register `org.gnome.ShairportSync` and
`org.mpris.MediaPlayer2.ShairportSync` on the system bus. `make install` adds
their policy files to `/etc/dbus-1/system.d/`; the default policy lets any
local user call them. They report whether a session is active, the player
state, the sender's name and the current track's metadata.

**Remote control does not work in AirPlay 2 mode.** Verified on 2026-09-28
with an iPhone, from both the Spotify app and Apple's Podcasts app:
`RemoteControl.Available` stays `false`, `Next`/`PlayPause` through either
interface have no effect, and `RemoteCommand` returns status 490 (no
remote-control channel from the sender). shairport-sync's remote control uses DACP, which senders only offer
in classic AirPlay sessions; AirPlay 2 senders are controlled over a newer
protocol that shairport-sync does not implement. So the receiver's transport
buttons cannot drive AirPlay playback. The interfaces are still worth
building for the state and metadata.

Zero 2 W has 512 MB RAM — use `-j2`, not `-j4`.

`/etc/shairport-sync.conf` needs two edits from stock:

```
name = "phonkyo";
output_device = "hw:CARD=sndrpihifiberry";
```

Address the DAC by card **name**, never `hw:0` -- see section 10. raspotify and
Plexamp use the ALSA default and need no change while the DAC is the only card.

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
- [x] nqptp + shairport-sync with AirPlay 2 — `01078ad-AirPlay2-smi10-OpenSSL-Avahi-ALSA-soxr-metadata-dbus-mpris`
- [x] Plexamp 4.13.2 claimed as `phonkyo`, systemd unit rewritten
- [x] avahi-utils
- [x] **RI control on GPIO25 via lgpio** — verified end to end on a real receiver
- [x] `phonkyo-monitor` playback-follow service
- [x] Receiver remote controls Plexamp (play/pause, skip, seek, repeat) — verified with a TX-8020 remote
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

### Verified and open

- **Protocol constants** (3000/1000/1000/2000 us, 12 bits) came from community
  reverse-engineering and are now confirmed on a TX-8020 in both directions:
  the receiver acts on frames sent with them, and frames it sends decode with
  them, with captured pulses within about 25 us of nominal.
- **Command codes** are mapped in both directions; see "Verified RI command
  codes" and "Codes the receiver sends *to* the dock" below.
- **RI electrical levels (open).** On a TX-8020 the line idles low. The level the
  receiver drives when it sends has not been measured; some sources describe
  5 V. On v0.2, GPIO25 connects to the J4 tip directly. From v0.3 it goes
  through R12 (100 R), with D1 (5 V ESD clamp) on the jack side, which limits
  the current into the GPIO if a receiver does drive 5 V.

## 10. HAT ID EEPROM -- automating setup for buyers

Source in `hardware/eeprom/`. Fitted from v0.3 (U1, R1, R2, C1, JP1); v0.2
has none. It is what turns "edit config.txt by hand" into "flash the image,
plug in the HAT, boot".

### What the firmware does with it

At boot the Pi reads the EEPROM at 0x50 on ID_SD/ID_SC (GPIO0/1) and:

1. **applies the embedded device tree overlay** -- the PCM5102A sound card
   is instantiated with no `dtoverlay=` line in config.txt at all
2. **applies the GPIO function/pull settings** declared in the EEPROM
3. **publishes identity** under `/proc/device-tree/hat/` -- vendor, product,
   product_id, product_ver, uuid

### Build

```sh
cd hardware/eeprom && make          # -> phonkyo.eep
make verify                          # dump it back and eyeball the fields
make flash                           # on the Pi, HAT fitted, JP1 open
```

The image identifies the board as vendor `obcecado.com`, product
`phonkyo DAC + Onkyo RI`, `product_id` 0x0001, `product_ver` 0x0003.

### Programming a board

1. Solder J1 (boards ship without it) and seat the board on a Pi.
2. Leave JP1 open, so WP floats low and the EEPROM is writable.
3. `make flash`. It rebuilds the image (so the board gets its own UUID),
   writes it, reads the chip back, compares the bytes, and prints the UUID.
   `eepflash.sh` brings up an I2C bus on GPIO0/1 by itself; nothing needs
   adding to config.txt.
4. Bridge JP1 with solder to write-protect the EEPROM.
5. Reboot. `/proc/device-tree/hat/` should now exist, and
   `python3 -m phonkyo.hat` should report the board.

**`eepmake` must be run with `-v1`.** It now defaults to the HAT+ format
(Pi 5 era), which dropped `gpio_drive`/`gpio_slew`/`gpio_hysteresis` and is
not what Zero 2 W firmware expects. Without it the build dies with
`'gpio_drive' not supported on HAT+`. The Makefile handles this.

Tooling is already present on the Trixie image via `rpi-eeprom`: `eepmake`,
`eepflash.sh`, `eepdump`, plus `dtc` from `device-tree-compiler`.

Verified: builds to a 906-byte image with the 778-byte overlay embedded, and
every field round-trips through `eepdump`.

`product_uuid` is left as zeros in the settings file, so `eepmake` generates a
new UUID every time it builds the image. `make flash` therefore rebuilds before
every write. Do not program a batch from one prebuilt `phonkyo.eep` with
`eepflash.sh` directly, or every board will share one UUID. Bump `product_ver`
per board revision so software can adapt.

### What software does with it

`software/phonkyo/hat.py` reads the identity and degrades gracefully -- on a
board with no EEPROM (v0.2, or a v0.3 not yet programmed) `detect()` returns
`None` and callers keep their current behaviour.

### Do not hardcode `hw:0`

Card numbering is not stable across machines. A buyer who leaves HDMI audio
enabled gets the DAC on card 1, and a hardcoded `hw:0` then plays into the
television. `hat.alsa_card()` resolves the card by *name*
(`hw:CARD=sndrpihifiberry`), which removes that whole class of support
ticket.

## 11. Playback-follow service (phonkyo-monitor)

Watches the DAC and drives the amp over RI: power on + select DOCK when audio
starts, power off after an idle timeout. It also listens for the receiver's
transport buttons and passes them to Plexamp (see "The receiver's remote"
below). `--remote control|log|off` sets whether it acts on them, only logs
them, or ignores them; the default is `control`.

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

### The receiver's remote

With DOCK selected, the receiver forwards its remote's transport buttons to the
dock over RI. `phonkyo/remote.py` listens for them inside `phonkyo-monitor`.
The listener lives in the monitor because RI is one wire used in both
directions: one object (`RILine`) owns the GPIO, listens by default, and pauses
listening while it transmits. A separate listener process would hold the GPIO
and make every `power_on_dock` fail with the line busy.

Each press arrives as 3 frames about 50 ms apart and is folded into one press.
Fast-forward and rewind keep firing every 0.4 s while held.

| Button | Code | Action (Plexamp) |
|---|---|---|
| Play/pause | `0x5CB` | `playPause` |
| Next track | `0x5C8` | `skipNext` |
| Previous track | `0x5C9` | `skipPrevious` |
| Fast-forward | `0x5C0` | `seekTo` current + 10 s |
| Rewind | `0x5C1` | `seekTo` current - 10 s |
| Repeat | `0x5D3` | `setParameters repeat`, cycling off -> all -> one -> off |
| Shuffle | `0x5D2` | none: `setParameters shuffle` is accepted but ignored |
| Menu | `0x5D6` | none: deliberately unassigned |

Verified on 2026-09-28 with a TX-8020 remote and Plexamp 4.13.2. Plexamp's
local API is on `127.0.0.1:32500`. It lists `stepForward`/`stepBack` as
controllable but answers 404, hence `seekTo`.

Presses only reach Plexamp when Plexamp is the player: the listener reads which
process owns the DAC (`owner_pid` in the PCM status, resolved to its process
through `Tgid`, since ALSA records the opening thread, e.g. Plexamp's
`libuv-worker`), and ignores presses while shairport-sync or librespot is
playing. AirPlay 2 senders offer no remote-control channel (section 5), and
librespot has no local control interface; the Spotify Web API would be the way
in, and is not set up.

### Verified RI command codes

Recovered from the previous working install and confirmed against hardware:

| Code | Action |
|---|---|
| `0x17F` | power on **and** select DOCK |
| `0x170` | select DOCK |
| `0x420` | power off |
| `0x2B0/1/2` | dimmer high / mid / low |

### Codes the receiver sends *to* the dock

RI is bidirectional. With DOCK selected, the receiver forwards its transport
buttons to the attached dock. Captured from a real receiver, three isolated
frames each:

| Code | Action |
|---|---|
| `0x5C0` | fast-forward |
| `0x5C1` | rewind |
| `0x5C8` | track forward |
| `0x5C9` | track back |
| `0x5CB` | play/pause |
| `0x5D2` | shuffle |
| `0x5D3` | repeat |
| `0x5D6` | menu |

All are in the `0x5C_`/`0x5D_` family. See "The receiver's remote" (section
11) for how phonkyo acts on them.

This is the more interesting half: it means the receiver's own remote can
drive playback on the Pi, if phonkyo listens for these and maps them onto
whatever is currently playing.

### Codes that are NOT available on a TX-8020 (exhaustively verified)

Do not spend time re-deriving these. Swept on real hardware:

- **All 256 families as `0xNN0`** (select input) -- 256 codes
- **All 256 families as `0xNNF`** (power on + select) -- 256 codes
- **Every command nibble `1`-`E` across all 256 families** -- 3,570 codes

**4,082 of the 4,096-code space.** The 14 excluded are the `0x42_` service
family (see the warning below). Results:

| Wanted | Found |
|---|---|
| TV input select | **no** -- no code selects TV in either form |
| Volume up/down | **no** -- `0x172/3` and `0x1A2/3` both inert |
| Mute | **no** |
| Input cycle/next | **no** |

This is now **two independent exhaustive sweeps** in agreement: ours, and the
developer whose published TX-8020 codes we started from, who brute-forced the
same space and found only those four inputs plus the dimmer family. TV is not
undiscovered -- it does not exist.

Only four inputs respond to select codes: CD, TAPE, BD/DVD, DOCK -- exactly
the four an RI-capable Onkyo *source device* plugs into. RI is a coordination
bus between the receiver and its source equipment; a TV has no RI connector
and nothing to coordinate, so Onkyo appears never to have assigned it a code.
No published table for any model lists one either.

### Sweep method, if this ever needs repeating

Watching a display for an hour does not work. Instead, play continuous audio
from the DAC with DOCK selected and *listen*: any code that changes the input
cuts the sound, which is far more noticeable than a display change and leaves
the operator free to do something else. Re-select DOCK every 32 codes so the
audio resumes and the operator can localise a hit to a 32-code window.

Caveat: mute and power-off cut the audio identically, so a dropout is a lead,
not an answer -- each one needs a follow-up look at the display.

Practical consequence: TV selection is not automatable over RI. Use the
receiver's own remote. This does not affect phonkyo's use case, which needs
`0x17F` (power on + select DOCK) and nothing else.

### DANGER: the 0x42_ family is service mode

`0x42_` is the factory **service/diagnostic** interface, not a normal command
family -- sweeping it put the receiver into a test mode displaying
`Test 1-00` ... `Test-04-00`. `0x420` (power off) lives here, which is
misleading: the rest of the family is not safe to probe. If it is entered
accidentally, power-cycle the receiver at the wall.

Any code-discovery tooling shipped to users must exclude `0x42_` except for
the known-good `0x420`.

### What the receiver does *not* emit

Input selection and volume changes produce nothing on the bus (verified with
repeated 30 s captures while pressing them). RI is largely a downstream bus --
the receiver commands attached sources, rather than broadcasting its own
state. Sniffing cannot discover volume or input codes; those have to come from
a code table or a sweep.

Volume was tested and **did not work** with either `0x172`/`0x173` (DOCK-family
offset) or the documented `0x1A2`/`0x1A3` (Video-family). It may not be
controllable from the dock side on this model.

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

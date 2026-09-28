#!/usr/bin/env bash
# phonkyo-setup.sh: set up a Raspberry Pi with a phonkyo HAT in one step.
#
#   curl -fsSL https://obcecado.com/phonkyo/install.sh | bash
#
# Run it as your normal user on Raspberry Pi OS Lite 64-bit (Trixie); it uses
# sudo where it needs to. It installs the players you choose (Spotify Connect,
# AirPlay 2, Plexamp) and phonkyo-monitor, which switches the receiver on and
# to DOCK when music plays and passes the receiver remote's buttons to Plexamp.
#
# Running it again is safe: finished steps are skipped, so it doubles as the
# way to update. Everything is logged to ~/phonkyo-setup.log.
#
# Options:
#   --players LIST   comma-separated: spotify,airplay,plexamp (default: ask)
#   --name NAME      how the player shows up on phones (default: phonkyo)
#   --yes            don't ask; use the defaults or the options above
#   --no-reboot      never reboot at the end, even if needed
#
# Every step mirrors install/MANIFEST.md in the phonkyo repository, which
# explains the reasons behind each one.

# The whole script is inside main(), so a download cut off halfway never runs.
main() {
set -Euo pipefail

# ---------------------------------------------------------------- versions
PHONKYO_REPO="https://github.com/fabiomsouto/phonkyo"
PHONKYO_REF="${PHONKYO_REF:-sw-v1.0.0}"
NQPTP_COMMIT="c925f27c1fd12e4033ac477e5a405969b0b0260b"          # nqptp 1.2.8
SHAIRPORT_COMMIT="01078ad15d4da06dffba0c5f15ffeaf9146a2a2a"      # AirPlay 2, tested
PLEXAMP_VERSION="4.13.2"

LOG="$HOME/phonkyo-setup.log"
BUILD_DIR="$HOME/.cache/phonkyo-build"
CARD="sndrpihifiberry"
REBOOT_NEEDED=0

# ---------------------------------------------------------------- helpers
say()  { printf '%s\n' "$*" | tee -a "$LOG"; }
step() { printf '\n== %s\n' "$*" | tee -a "$LOG"; }
die()  { printf '\nError: %s\nThe full log is in %s\n' "$*" "$LOG" | tee -a "$LOG" >&2; exit 1; }

# run "what it does" command...: the command's output goes to the log only.
run() {
    local desc=$1; shift
    printf '  %s ... ' "$desc"
    printf '\n--- %s\n$ %s\n' "$desc" "$*" >>"$LOG"
    if "$@" >>"$LOG" 2>&1; then
        echo "ok"
    else
        echo "failed"
        printf '\nLast lines of the log:\n'; tail -n 15 "$LOG" | sed 's/^/  | /'
        die "$desc failed."
    fi
}

# Questions come from the terminal, since stdin is the script itself under curl | bash.
TTY=""
if [ -t 0 ]; then TTY=/dev/stdin; elif { : </dev/tty; } 2>/dev/null; then TTY=/dev/tty; fi
ASSUME_YES=0

ask() {  # ask VAR "question" default
    local __var=$1 question=$2 default=${3-} answer=""
    if [ "$ASSUME_YES" = 1 ] || [ -z "$TTY" ]; then
        answer=$default
    else
        read -r -p "$question " answer <"$TTY" || answer=""
        answer=${answer:-$default}
    fi
    printf -v "$__var" '%s' "$answer"
    printf '%s %s\n' "$question" "$answer" >>"$LOG"
}
yes_no() { local a; ask a "$1 [${2:-Y}/$( [ "${2:-Y}" = Y ] && echo n || echo N )]" "${2:-Y}"; [[ $a =~ ^[Yy] ]]; }

hat_vendor() { { tr -d '\0' </proc/device-tree/hat/vendor; } 2>/dev/null || true; }

# ---------------------------------------------------------------- options
PLAYER_LIST="" PLAYER_NAME="" NO_REBOOT=0
while [ $# -gt 0 ]; do
    case $1 in
        --players) PLAYER_LIST=${2:-}; shift ;;
        --name) PLAYER_NAME=${2:-}; shift ;;
        --yes|-y) ASSUME_YES=1 ;;
        --no-reboot) NO_REBOOT=1 ;;
        -h|--help) sed -n '2,22p' "$0" 2>/dev/null || echo "See https://obcecado.com/phonkyo/setup/"; exit 0 ;;
        *) die "unknown option: $1" ;;
    esac
    shift
done

: >>"$LOG"
printf '\n######## phonkyo-setup %s, %s\n' "$PHONKYO_REF" "$(date -Is)" >>"$LOG"

cat <<EOF

phonkyo setup
This installs the players you choose and phonkyo-monitor on this Pi.
It takes about 10-15 minutes; AirPlay 2 is compiled here, which adds a few.
The log is in $LOG.
EOF

# ---------------------------------------------------------------- preflight
step "Checking this Pi"
[ "$(id -u)" -ne 0 ] || die "run this as your normal user, not root; it uses sudo where needed."
command -v sudo >/dev/null || die "sudo is missing."
[ "$(uname -m)" = aarch64 ] || die "this needs the 64-bit Raspberry Pi OS (found $(uname -m))."
# /etc/os-release defines NAME and friends, so read it in a subshell.
# shellcheck disable=SC1091
OS_CODENAME=$(. /etc/os-release && echo "${VERSION_CODENAME:-}")
# shellcheck disable=SC1091
OS_PRETTY=$(. /etc/os-release && echo "${PRETTY_NAME:-unknown}")
[ "$OS_CODENAME" = trixie ] || say "  Warning: tested on Raspberry Pi OS Trixie; this is $OS_PRETTY."
sudo -v || die "sudo needs your password to continue."
# Keep sudo's cached password alive: the AirPlay build outlasts its 15 minutes.
( while kill -0 "$$" 2>/dev/null; do sudo -n true 2>/dev/null; sleep 60; done ) &
curl -fsSI -m 15 https://github.com >/dev/null || die "no internet connection (can't reach github.com)."
say "  $({ tr -d '\0' </proc/device-tree/model; } 2>/dev/null || echo 'Raspberry Pi'), $OS_PRETTY"
[ "$(hat_vendor)" = obcecado.com ] && say "  phonkyo board with ID EEPROM detected"

# ---------------------------------------------------------------- choices
if [ -z "$PLAYER_LIST" ]; then
    PLAYER_LIST=""
    yes_no "Install Spotify Connect (raspotify)?" Y && PLAYER_LIST+="spotify,"
    yes_no "Install AirPlay 2 (shairport-sync, compiled here, a few minutes)?" Y && PLAYER_LIST+="airplay,"
    yes_no "Install Plexamp (needs a Plex account)?" Y && PLAYER_LIST+="plexamp,"
fi
has() { [[ ",$PLAYER_LIST," == *",$1,"* ]]; }
if [ -z "$PLAYER_NAME" ]; then ask PLAYER_NAME "Name shown on phones? [phonkyo]" phonkyo; fi
[[ $PLAYER_NAME =~ ^[A-Za-z0-9][A-Za-z0-9\ ._-]{0,39}$ ]] || die "the name may only use letters, digits, spaces, dots, dashes and underscores."
say "  Players: ${PLAYER_LIST%,}   Name: $PLAYER_NAME"

# ---------------------------------------------------------------- boot config
step "Boot configuration"
CFG=/boot/firmware/config.txt
[ -f "$CFG" ] || die "$CFG not found."
[ -f "$CFG.phonkyo-bak" ] || run "Backing up config.txt" sudo cp -p "$CFG" "$CFG.phonkyo-bak"
if grep -qE '^[[:space:]]*dtparam=audio=on' "$CFG"; then
    run "Turning off the Pi's onboard audio" sudo sed -i -E 's/^[[:space:]]*dtparam=audio=on.*/#dtparam=audio=on  # phonkyo: the DAC is the audio output/' "$CFG"
    REBOOT_NEEDED=1
fi
if grep -qE '^[[:space:]]*dtoverlay=vc4-kms-v3d' "$CFG" && ! grep -qE '^[[:space:]]*dtoverlay=vc4-kms-v3d.*noaudio' "$CFG"; then
    run "Turning off HDMI audio" sudo sed -i -E 's/^([[:space:]]*dtoverlay=vc4-kms-v3d[^[:space:]#]*)/\1,noaudio/' "$CFG"
    REBOOT_NEEDED=1
fi
if [ "$(hat_vendor)" = obcecado.com ]; then
    say "  The ID EEPROM sets up the DAC; no overlay needed"
elif ! grep -qE '^[[:space:]]*dtoverlay=hifiberry-dac' "$CFG"; then
    run "Enabling the DAC (hifiberry-dac overlay)" bash -c "printf '\n[all]\n# phonkyo: PCM5102A DAC over I2S\ndtoverlay=hifiberry-dac\n' | sudo tee -a '$CFG' >/dev/null"
    REBOOT_NEEDED=1
else
    say "  DAC overlay already enabled"
fi

# ---------------------------------------------------------------- packages
step "Packages"
run "Updating the package lists" sudo apt-get update
BASE=(alsa-utils avahi-daemon avahi-utils python3-lgpio curl ca-certificates)
run "Installing base packages" sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y "${BASE[@]}"

# ---------------------------------------------------------------- spotify
if has spotify; then
    step "Spotify Connect (raspotify)"
    if [ ! -f /etc/apt/sources.list.d/raspotify.list ]; then
        run "Adding the raspotify repository" bash -c '
            curl -fsSL https://dtcooper.github.io/raspotify/key.asc | sudo tee /usr/share/keyrings/raspotify_key.asc >/dev/null &&
            echo "deb [signed-by=/usr/share/keyrings/raspotify_key.asc] https://dtcooper.github.io/raspotify raspotify main" |
                sudo tee /etc/apt/sources.list.d/raspotify.list >/dev/null &&
            sudo apt-get update'
    fi
    run "Installing raspotify" sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y raspotify
    CONF=/etc/raspotify/conf
    if sudo grep -qE '^LIBRESPOT_NAME=' "$CONF"; then
        run "Setting the Spotify name" sudo sed -i -E "s|^LIBRESPOT_NAME=.*|LIBRESPOT_NAME=\"$PLAYER_NAME\"|" "$CONF"
    else
        run "Setting the Spotify name" bash -c "echo 'LIBRESPOT_NAME=\"$PLAYER_NAME\"' | sudo tee -a $CONF >/dev/null"
    fi
    run "Starting raspotify" sudo systemctl enable --now raspotify
    run "Applying the name" sudo systemctl restart raspotify
fi

# ---------------------------------------------------------------- airplay
if has airplay; then
    step "AirPlay 2 (nqptp + shairport-sync)"
    run "Installing build dependencies" sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y \
        build-essential git autoconf automake libtool libpopt-dev libconfig-dev libasound2-dev \
        libavahi-client-dev libssl-dev libsoxr-dev libplist-dev libplist-utils libsodium-dev \
        libavutil-dev libavcodec-dev libavformat-dev uuid-dev libgcrypt-dev xxd libglib2.0-dev \
        systemd-dev
    mkdir -p "$BUILD_DIR"
    fetch_commit() {  # fetch_commit URL COMMIT DIR
        rm -rf "$3" && git init -q "$3" && git -C "$3" fetch -q --depth 1 "$1" "$2" && git -C "$3" checkout -q FETCH_HEAD
    }
    # A build from git reports its commit, e.g. "Version: c925f27. Shared Memory ...".
    if ! nqptp -V 2>/dev/null | grep -q "^Version: ${NQPTP_COMMIT:0:7}\."; then
        run "Downloading nqptp" fetch_commit https://github.com/mikebrady/nqptp.git "$NQPTP_COMMIT" "$BUILD_DIR/nqptp"
        run "Building nqptp" bash -c "cd '$BUILD_DIR/nqptp' && autoreconf -fi && ./configure --with-systemd-startup && make -j2"
        run "Installing nqptp" bash -c "cd '$BUILD_DIR/nqptp' && sudo make install"
    else
        say "  nqptp ${NQPTP_COMMIT:0:7} already installed"
    fi
    run "Starting nqptp" sudo systemctl enable --now nqptp
    # Rebuild if the binary isn't the pinned commit, or an earlier run left no service unit.
    if ! /usr/local/bin/shairport-sync -V 2>/dev/null | grep -q "^${SHAIRPORT_COMMIT:0:7}-AirPlay2" ||
       ! systemctl cat shairport-sync >/dev/null 2>&1; then
        run "Downloading shairport-sync" fetch_commit https://github.com/mikebrady/shairport-sync.git "$SHAIRPORT_COMMIT" "$BUILD_DIR/shairport-sync"
        run "Configuring shairport-sync" bash -c "cd '$BUILD_DIR/shairport-sync' && autoreconf -fi && ./configure \
            --sysconfdir=/etc --with-alsa --with-soxr --with-avahi --with-ssl=openssl --with-airplay-2 \
            --with-dbus-interface --with-mpris-interface --with-systemd-startup"
        say "  Compiling shairport-sync. This is the slow part: a few minutes on a Zero 2 W."
        run "Building shairport-sync" bash -c "cd '$BUILD_DIR/shairport-sync' && make -j2"
        run "Installing shairport-sync" bash -c "cd '$BUILD_DIR/shairport-sync' && sudo make install"
    else
        say "  shairport-sync ${SHAIRPORT_COMMIT:0:7} already installed"
    fi
    SCONF=/etc/shairport-sync.conf
    [ -f "$SCONF" ] || run "Creating $SCONF" sudo cp /etc/shairport-sync.conf.sample "$SCONF"
    run "Setting the AirPlay name" sudo sed -i -E "0,/^[[:space:]]*(\/\/)?[[:space:]]*name = \"[^\"]*\";/s//\tname = \"$PLAYER_NAME\";/" "$SCONF"
    run "Pointing AirPlay at the DAC" sudo sed -i -E "0,/^[[:space:]]*(\/\/)?[[:space:]]*output_device = \"[^\"]*\";/s//\toutput_device = \"hw:CARD=$CARD\";/" "$SCONF"
    run "Reloading systemd" sudo systemctl daemon-reload
    run "Enabling shairport-sync" sudo systemctl enable shairport-sync
    run "Restarting shairport-sync" sudo systemctl restart shairport-sync
fi

# ---------------------------------------------------------------- plexamp
if has plexamp; then
    step "Plexamp headless"
    run "Installing Node.js and expect" sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs expect bzip2
    if [ "$(cat /opt/plexamp/.phonkyo-version 2>/dev/null)" != "$PLEXAMP_VERSION" ]; then
        run "Downloading Plexamp $PLEXAMP_VERSION" curl -fsSL -o "$BUILD_DIR/plexamp.tar.bz2" --create-dirs \
            "https://plexamp.plex.tv/headless/Plexamp-Linux-headless-v$PLEXAMP_VERSION.tar.bz2"
        run "Unpacking Plexamp" sudo tar -xjf "$BUILD_DIR/plexamp.tar.bz2" -C /opt
        run "Handing /opt/plexamp to $USER" sudo chown -R "$USER:$USER" /opt/plexamp
        echo "$PLEXAMP_VERSION" >/opt/plexamp/.phonkyo-version
    else
        say "  Plexamp $PLEXAMP_VERSION already installed"
    fi
    run "Installing the Plexamp service" bash -c "sudo tee /etc/systemd/system/plexamp.service >/dev/null <<UNIT
[Unit]
Description=Plexamp headless player
After=network-online.target sound.target
Requires=network-online.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=/opt/plexamp
ExecStart=/usr/bin/node /opt/plexamp/js/index.js
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload"
    if [ -f "$HOME/.local/share/Plexamp/Settings/%40Plexamp%3Aplayer%3Aname" ]; then
        say "  Plexamp is already signed in"
        run "Starting Plexamp" sudo systemctl enable --now plexamp
    elif [ -z "$TTY" ] || [ "$ASSUME_YES" = 1 ]; then
        say "  Plexamp needs signing in, which has to be done interactively. Run this script again"
        say "  in a terminal (without --yes) to do it."
    else
        claim_plexamp
    fi
fi

# ---------------------------------------------------------------- monitor
step "phonkyo-monitor (receiver control)"
run "Downloading phonkyo $PHONKYO_REF" bash -c "rm -rf '$BUILD_DIR/phonkyo' && mkdir -p '$BUILD_DIR/phonkyo' &&
    curl -fsSL '$PHONKYO_REPO/archive/$PHONKYO_REF.tar.gz' | tar -xz --strip-components=1 -C '$BUILD_DIR/phonkyo'"
if ! id phonkyo >/dev/null 2>&1; then
    run "Creating the phonkyo system user" sudo useradd --system --no-create-home --user-group --groups gpio,audio phonkyo
fi
run "Installing the software" bash -c "sudo mkdir -p /opt/phonkyo && sudo rm -rf /opt/phonkyo/phonkyo &&
    sudo cp -r '$BUILD_DIR/phonkyo/software/phonkyo' /opt/phonkyo/ &&
    sudo cp '$BUILD_DIR/phonkyo/software/systemd/phonkyo-monitor.service' /etc/systemd/system/ &&
    sudo systemctl daemon-reload"
run "Enabling phonkyo-monitor" sudo systemctl enable phonkyo-monitor
run "Restarting phonkyo-monitor" sudo systemctl restart phonkyo-monitor

# ---------------------------------------------------------------- summary
step "Checking the result"
services="phonkyo-monitor"
has spotify && services+=" raspotify"
has airplay && services+=" nqptp shairport-sync"
has plexamp && services+=" plexamp"
for s in $services; do
    printf '  %-16s %s\n' "$s" "$(systemctl is-active "$s" 2>/dev/null)" | tee -a "$LOG"
done
if grep -q "$CARD" /proc/asound/cards 2>/dev/null; then
    say "  DAC: found"
else
    say "  DAC: not active yet (it appears after a reboot)"
    REBOOT_NEEDED=1
fi

if [ "$REBOOT_NEEDED" = 1 ]; then
    if [ "$NO_REBOOT" = 0 ] && yes_no "A reboot is needed to switch on the DAC. Reboot now?" Y; then
        say "Rebooting. When the Pi is back, play something to \"$PLAYER_NAME\"."
        sudo systemctl reboot
    else
        say "Reboot when you're ready (sudo reboot), then play something to \"$PLAYER_NAME\"."
    fi
else
    say "All done. Play something to \"$PLAYER_NAME\"."
fi
}

# Plexamp's sign-in: a single-use claim token that expires after 4 minutes,
# fed to two prompts in turn. See install/MANIFEST.md, section 6.
claim_plexamp() {
    local token="" name="$PLAYER_NAME" rc
    cat <<'EOF'

  Plexamp needs to be signed in to your Plex account, once.
  1. On any computer or phone, open https://plex.tv/claim while signed in to Plex.
  2. Copy the code it shows (it starts with "claim-"). It expires after 4 minutes.
EOF
    while :; do
        ask token "  Paste the claim code (or press Enter to skip):" ""
        if [ -z "$token" ]; then
            say "  Skipped. Run this script again to sign Plexamp in later."
            return 0
        fi
        [[ $token =~ ^claim-[A-Za-z0-9_-]+$ ]] || { say "  That doesn't look like a claim code; it should start with \"claim-\"."; continue; }
        cat >"$BUILD_DIR/claim.exp" <<'EXP'
set timeout 180
set token [lindex $argv 0]
set name [lindex $argv 1]
spawn node js/index.js
expect {
    -re "claim token:" { send -- "$token\r" }
    timeout { exit 2 }
}
expect {
    -re {name \(e\.g\.} { send -- "$name\r" }
    -re {(?i)(invalid|expired|error)} { exit 3 }
    timeout { exit 2 }
}
expect {
    -re "signed in and ready" { }
    timeout { exit 4 }
}
sleep 20
exit 0
EXP
        printf '  Signing Plexamp in ... '
        (cd /opt/plexamp && expect "$BUILD_DIR/claim.exp" "$token" "$name") >>"$LOG" 2>&1
        rc=$?
        rm -f "$BUILD_DIR/claim.exp"
        if [ $rc -eq 0 ] && [ -f "$HOME/.local/share/Plexamp/Settings/%40Plexamp%3Aplayer%3Aname" ]; then
            echo "ok"
            run "Starting Plexamp" sudo systemctl enable --now plexamp
            return 0
        fi
        echo "failed"
        say "  The code didn't work (it may have expired or already been used). Codes work"
        say "  only once, so get a fresh one from https://plex.tv/claim and try again."
    done
}

main "$@"

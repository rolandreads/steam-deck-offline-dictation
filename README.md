# Steam Deck Offline Dictation

Local hold-to-talk dictation for Steam Deck Game Mode.

The goal is simple: focus any text field, hold `L4`, speak, release, and have the transcript typed into the focused app. No Decky plugin, no cloud dictation service, no transcript history.

## What This Uses

- Trigger: Steam Deck `L4` back button, read from the controller `hidraw` device
- Speech recognition: `voxtype` `0.6.6`
- Model: Whisper `base.en`
- Acceleration: Vulkan/RADV on the Steam Deck AMD GPU
- Silence trim: voxtype energy VAD
- Text injection: temporary `/dev/uinput` virtual keyboard
- Remote setup path: optional Tailscale SSH

## Why Tailscale First

Typing long commands on the Deck is painful. I used Tailscale SSH so an agent could set this up remotely.

For Steam Deck Tailscale setup, use:

https://github.com/tailscale-dev/deck-tailscale

That project installs Tailscale in a SteamOS-friendly way and can enable Tailscale SSH. Once the Deck is reachable over Tailscale, the rest of this setup can be done from another machine.

## Footprint From My Deck

Measured on a Steam Deck with SteamOS 3.7.21:

| Item | Approx size |
|---|---:|
| voxtype Vulkan binary | 40 MB |
| Whisper `base.en` model | 142 MB |
| scripts and units | tiny |
| total | about 190 MB |

Idle resource use after tuning:

| Service | Idle CPU | Memory |
|---|---:|---:|
| L4 bridge | about 190ms CPU / 20s | about 7 MB cgroup memory |
| voxtype daemon | about 28ms CPU / 20s | about 18 MB cgroup memory |

Real Deck mic benchmark:

| Candidate | Disk | Warm RSS | Median transcribe | Result |
|---|---:|---:|---:|---|
| Whisper `base.en` + Vulkan | 142 MB model + 40 MB binary | about 137 MB RSS | 0.31s | best fit |
| Whisper `small.en` + Vulkan | 466 MB model | larger Vulkan allocation | 0.75s | slower, no clear win |
| Moonshine tiny ONNX CPU | 108 MB model + 37 MB binary | about 284 MB RSS | 0.045s | failed one clip |
| Moonshine base ONNX CPU | 240 MB model + 37 MB binary | about 541 MB RSS | 0.12s | correct, weaker punctuation |
| Parakeet TDT v3 int8 ONNX CPU | 640 MB model + 37 MB binary | about 987 MB RSS | 0.265s | correct, heavy |

Conclusion: Whisper `base.en` + Vulkan is not the newest ASR model, but it was the best practical fit for always-available Deck dictation.

## Install

These instructions assume the normal Steam Deck user is `deck`.

### 1. Install Tailscale Optional

If you want remote agent access first, install Tailscale using:

https://github.com/tailscale-dev/deck-tailscale

After that, connect over Tailscale SSH as `deck` or `root`.

### 2. Copy This Repo To The Deck

```sh
git clone https://github.com/rolandreads/steam-deck-offline-dictation.git ~/steam-deck-offline-dictation
cd ~/steam-deck-offline-dictation
```

### 3. Run The Installer

```sh
sudo ./install.sh
```

The installer:

- creates `/home/deck/src/deck-dictate`
- installs the helper scripts
- downloads and verifies the voxtype Vulkan binary
- downloads the Whisper `base.en` model
- installs the user and root systemd services
- enables both services

### 4. Test

Focus a text field, hold `L4`, speak, release.

Watch logs:

```sh
sudo journalctl -u deck-dictate-l4.service -f
```

Check services:

```sh
systemctl --user status deck-dictate.service
sudo systemctl status deck-dictate-l4.service
```

## Behavior

The bridge strips one final period before typing because this is mostly for chat, search, and URLs rather than prose.

Examples:

```text
hello.       -> hello
example.com. -> example.com
wow!         -> wow!
```

Internal periods are preserved.

## Files Installed On The Deck

```text
/home/deck/src/deck-dictate/deck-dictate-daemon
/home/deck/src/deck-dictate/hold_l4_warm.py
/home/deck/src/deck-dictate/uinput_type.py
/home/deck/.local/deck-dictate/bin/voxtype
/home/deck/.local/share/deck-dictate/models/ggml-base.en.bin
/home/deck/.config/systemd/user/deck-dictate.service
/etc/systemd/system/deck-dictate-l4.service
```

## Troubleshooting

If L4 does nothing:

```sh
sudo systemctl restart deck-dictate-l4.service
sudo journalctl -u deck-dictate-l4.service -n 80 --no-pager
```

If the model daemon is stopped:

```sh
systemctl --user restart deck-dictate.service
journalctl --user -u deck-dictate.service -n 120 --no-pager
```

If the hidraw node changed, the bridge should autodetect it by Steam Deck controller HID metadata. On my Deck it resolves to `/dev/hidraw2`.

## Security Notes

- This avoids Decky plugins entirely.
- Dictation is offline after install.
- The root service is small, but it is still root because it reads `hidraw` and writes `/dev/uinput`.
- Do not run unreviewed scripts as root. Read `install.sh` first.


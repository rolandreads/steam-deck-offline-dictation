#!/usr/bin/env python3
import argparse
import json
import os
import select
import subprocess
import sys
import time
from pathlib import Path

L4_OFFSET = 13
L4_MASK = 0x02


def deck_home():
    sudo_user = os.environ.get('SUDO_USER')
    if sudo_user and sudo_user != 'root':
        return Path('/home') / sudo_user
    return Path('/home/deck')


def emit(msg):
    print(msg, flush=True)


def env_for(user_home):
    env = os.environ.copy()
    env['HOME'] = str(user_home)
    env['XDG_RUNTIME_DIR'] = '/run/user/1000'
    return env


def voxtype_cmd(user_home, *args, check=False):
    cmd = [str(user_home / '.local/deck-dictate/bin/voxtype'), '--config', str(user_home / 'src/deck-dictate/config.toml'), *args]
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env_for(user_home), check=check)


def status_class(user_home):
    result = voxtype_cmd(user_home, 'status', '--format', 'json')
    try:
        return json.loads(result.stdout).get('class', '')
    except json.JSONDecodeError:
        return ''


def wait_done(user_home, timeout=15):
    deadline = time.monotonic() + timeout
    last = ''
    while time.monotonic() < deadline:
        cls = status_class(user_home)
        if cls != last:
            emit(f'status={cls}')
            last = cls
        if cls == 'idle':
            return True
        time.sleep(0.15)
    return False


def clean_transcript(text):
    text = text.strip()
    if text.endswith('.'):
        return text[:-1].rstrip()
    return text


def type_transcript(root, text):
    if text:
        subprocess.run([str(root / 'uinput_type.py'), text], check=False)


def hidraw_uevent(hidraw_name):
    path = Path('/sys/class/hidraw') / hidraw_name / 'device/uevent'
    try:
        return path.read_text(errors='replace')
    except OSError:
        return ''


def find_steam_l4_hidraw():
    for path in sorted(Path('/sys/class/hidraw').glob('hidraw*')):
        uevent = hidraw_uevent(path.name)
        if 'HID_NAME=Valve Software Steam Deck Controller' in uevent and 'MODALIAS=hid:b0003g0103v000028DEp00001205' in uevent:
            return Path('/dev') / path.name
    return Path('/dev/hidraw2')


def main():
    ap = argparse.ArgumentParser(description='Warm-daemon L4 hold-to-talk runner.')
    ap.add_argument('--hidraw', default=None)
    ap.add_argument('--seconds', type=float, default=31536000)
    ap.add_argument('--min-duration', type=float, default=0.35)
    ap.add_argument('--max-record', type=float, default=30)
    args = ap.parse_args()

    if not os.access('/dev/uinput', os.W_OK):
        print('error: /dev/uinput is not writable; run as root/sudo', file=sys.stderr)
        return 1

    user_home = deck_home()
    root = user_home / 'src/deck-dictate'
    runtime = Path('/run/user/1000/deck-dictate')
    runtime.mkdir(parents=True, exist_ok=True)
    output_file = runtime / 'last_transcription.txt'

    st = status_class(user_home)
    if st not in {'idle', 'recording', 'transcribing'}:
        print(f'error: voxtype daemon not ready, status={st!r}. Start /home/deck/src/deck-dictate/deck-dictate-daemon first.', file=sys.stderr)
        return 1

    hidraw = Path(args.hidraw) if args.hidraw else find_steam_l4_hidraw()
    try:
        fd = os.open(hidraw, os.O_RDONLY | os.O_NONBLOCK)
    except OSError as e:
        print(f'error: cannot open {hidraw}: {e}', file=sys.stderr)
        return 1

    emit(f'warm L4 hold-to-talk ready hidraw={hidraw} status={st} output={output_file}')
    prev_pressed = False
    recording = False
    started_at = None
    end = time.monotonic() + args.seconds
    try:
        while time.monotonic() < end:
            if recording and started_at and time.monotonic() - started_at > args.max_record:
                emit('max-record reached; stopping')
                voxtype_cmd(user_home, 'record', 'stop')
                recording = False
                wait_done(user_home)
                text = clean_transcript(output_file.read_text(errors='replace')) if output_file.exists() else ''
                emit(f'transcript={text}')
                type_transcript(root, text)
            r, _, _ = select.select([fd], [], [], 0.25)
            if not r:
                continue
            try:
                data = os.read(fd, 64)
            except BlockingIOError:
                continue
            if len(data) <= L4_OFFSET:
                continue
            pressed = bool(data[L4_OFFSET] & L4_MASK)
            if pressed and not prev_pressed and not recording:
                output_file.unlink(missing_ok=True)
                emit('recording start')
                res = voxtype_cmd(user_home, 'record', 'start', f'--file={output_file}')
                if res.returncode != 0:
                    emit('record start failed: ' + res.stdout.strip())
                else:
                    recording = True
                    started_at = time.monotonic()
            elif not pressed and prev_pressed and recording:
                duration = time.monotonic() - started_at
                emit(f'recording stop duration={duration:.2f}s')
                voxtype_cmd(user_home, 'record', 'stop')
                recording = False
                if duration >= args.min_duration:
                    wait_done(user_home)
                    text = clean_transcript(output_file.read_text(errors='replace')) if output_file.exists() else ''
                    emit(f'transcript={text}')
                    type_transcript(root, text)
                else:
                    emit('ignored: hold too short')
            prev_pressed = pressed
    finally:
        if recording:
            voxtype_cmd(user_home, 'record', 'cancel')
        os.close(fd)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())


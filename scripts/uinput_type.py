#!/usr/bin/env python3
import argparse
import fcntl
import os
import struct
import time

UI_SET_EVBIT = 0x40045564
UI_SET_KEYBIT = 0x40045565
UI_DEV_CREATE = 0x5501
UI_DEV_DESTROY = 0x5502
EV_SYN = 0x00
EV_KEY = 0x01
SYN_REPORT = 0
BUS_USB = 0x03

KEY_LEFTSHIFT = 42
KEY_ENTER = 28
KEY_SPACE = 57

KEYS = {
    'a': 30, 'b': 48, 'c': 46, 'd': 32, 'e': 18, 'f': 33, 'g': 34,
    'h': 35, 'i': 23, 'j': 36, 'k': 37, 'l': 38, 'm': 50, 'n': 49,
    'o': 24, 'p': 25, 'q': 16, 'r': 19, 's': 31, 't': 20, 'u': 22,
    'v': 47, 'w': 17, 'x': 45, 'y': 21, 'z': 44,
    '1': 2, '2': 3, '3': 4, '4': 5, '5': 6, '6': 7, '7': 8, '8': 9,
    '9': 10, '0': 11,
    ' ': KEY_SPACE, '\n': KEY_ENTER,
    '-': 12, '=': 13, '[': 26, ']': 27, '\\': 43, ';': 39, "'": 40,
    '`': 41, ',': 51, '.': 52, '/': 53,
}
SHIFTED = {
    'A': 'a', 'B': 'b', 'C': 'c', 'D': 'd', 'E': 'e', 'F': 'f', 'G': 'g',
    'H': 'h', 'I': 'i', 'J': 'j', 'K': 'k', 'L': 'l', 'M': 'm', 'N': 'n',
    'O': 'o', 'P': 'p', 'Q': 'q', 'R': 'r', 'S': 's', 'T': 't', 'U': 'u',
    'V': 'v', 'W': 'w', 'X': 'x', 'Y': 'y', 'Z': 'z',
    '!': '1', '@': '2', '#': '3', '$': '4', '%': '5', '^': '6', '&': '7',
    '*': '8', '(': '9', ')': '0', '_': '-', '+': '=', '{': '[', '}': ']',
    '|': '\\', ':': ';', '"': "'", '~': '`', '<': ',', '>': '.', '?': '/',
}

EVENT_STRUCT = 'llHHI'
USER_DEV_STRUCT = '80sHHHHI' + 'i' * 256


def emit(fd, ev_type, code, value):
    sec = int(time.time())
    usec = int((time.time() - sec) * 1_000_000)
    os.write(fd, struct.pack(EVENT_STRUCT, sec, usec, ev_type, code, value))


def syn(fd):
    emit(fd, EV_SYN, SYN_REPORT, 0)


def key(fd, code, value):
    emit(fd, EV_KEY, code, value)
    syn(fd)


def tap(fd, code, shifted=False, delay=0.008):
    if shifted:
        key(fd, KEY_LEFTSHIFT, 1)
    key(fd, code, 1)
    time.sleep(delay)
    key(fd, code, 0)
    if shifted:
        key(fd, KEY_LEFTSHIFT, 0)
    time.sleep(delay)


def create_keyboard():
    fd = os.open('/dev/uinput', os.O_WRONLY | os.O_NONBLOCK)
    fcntl.ioctl(fd, UI_SET_EVBIT, EV_KEY)
    fcntl.ioctl(fd, UI_SET_EVBIT, EV_SYN)
    for code in sorted(set(KEYS.values()) | {KEY_LEFTSHIFT}):
        fcntl.ioctl(fd, UI_SET_KEYBIT, code)
    user_dev = struct.pack(
        USER_DEV_STRUCT,
        b'deck-dictate virtual keyboard',
        BUS_USB,
        0x1209,
        0x4444,
        1,
        0,
        *([0] * 256),
    )
    os.write(fd, user_dev)
    fcntl.ioctl(fd, UI_DEV_CREATE)
    time.sleep(0.25)
    return fd


def type_text(text):
    fd = create_keyboard()
    try:
        for ch in text:
            shifted = False
            key_ch = ch
            if ch in SHIFTED:
                shifted = True
                key_ch = SHIFTED[ch]
            code = KEYS.get(key_ch)
            if code is None:
                continue
            tap(fd, code, shifted=shifted)
    finally:
        time.sleep(0.1)
        fcntl.ioctl(fd, UI_DEV_DESTROY)
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description='Type text through a temporary uinput keyboard.')
    parser.add_argument('text', nargs='?', default='deck dictate test')
    parser.add_argument('--enter', action='store_true', help='press Enter after typing')
    args = parser.parse_args()
    text = args.text + ('\n' if args.enter else '')
    type_text(text)


if __name__ == '__main__':
    main()


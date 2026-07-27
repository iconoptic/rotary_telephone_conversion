#!/usr/bin/env python3
"""
Host-side companion for the vintage rotary phone USB volume control.

The Pico's `hid_consumer.VolumeHID` interface is a vendor-defined HID usage
page (not the standard Consumer Control page), so the OS never treats it as
a media key -- it just shows up as a plain /dev/hidrawN device. This script
finds that device, reads its 1-byte reports (0-100 = target volume percent),
and applies the exact value with `pactl set-sink-volume`. Deterministic, no
drift, no auto-mute side effects.

Usage:
    python3 host/volume_daemon.py

Requires read access to the matching /dev/hidrawN node. If you get a
Permission denied error, add a udev rule (see docs/) granting your user
(or the `input` group) access to hidraw devices from this board
(VID 2e8a / PID 0005), then replug the board.
"""

import glob
import re
import subprocess
import sys

VID = "2e8a"
PID = "0005"

_HID_ID_RE = re.compile(r"HID_ID=0003:0000([0-9A-Fa-f]{4}):0000([0-9A-Fa-f]{4})")


def find_hidraw_device():
    for uevent_path in glob.glob("/sys/class/hidraw/hidraw*/device/uevent"):
        try:
            with open(uevent_path) as f:
                contents = f.read()
        except OSError:
            continue
        m = _HID_ID_RE.search(contents)
        if not m:
            continue
        vid, pid = m.group(1).lower(), m.group(2).lower()
        if vid == VID and pid == PID:
            hidraw_name = uevent_path.split("/")[4]  # e.g. "hidraw10"
            return "/dev/" + hidraw_name
    return None


def set_volume_percent(percent):
    subprocess.run(
        ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "{}%".format(percent)],
        check=False,
    )
    print("Set system volume to {}%".format(percent))


def main():
    dev_path = find_hidraw_device()
    if not dev_path:
        print("Could not find the Pico's hidraw device (VID {}:{}). "
              "Is it plugged in and running main.py?".format(VID, PID), file=sys.stderr)
        sys.exit(1)

    print("Reading volume reports from {}".format(dev_path))
    try:
        with open(dev_path, "rb", buffering=0) as f:
            while True:
                data = f.read(1)
                if not data:
                    continue
                percent = data[0]
                set_volume_percent(percent)
    except PermissionError:
        print("Permission denied opening {}. See the docstring at the top of "
              "this script for the udev rule needed.".format(dev_path), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()

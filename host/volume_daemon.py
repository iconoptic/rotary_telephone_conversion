#!/usr/bin/env python3
"""
Host-side companion for the vintage rotary phone USB volume control.

The firmware's vendor-defined HID usage page (0xFF00) is not the standard
Consumer Control page, so the OS never treats it as a media key -- it just
shows up as a plain HID device. This script finds that device, reads its
reports (byte 0 = HID Report ID, always 0x01; byte 1 = target volume
percent 0-100), and applies the exact value to the system volume.
Deterministic, no drift, no auto-mute side effects.

Supports Linux and Windows 11:

  Linux: reads /dev/hidrawN directly (stdlib only) and shells out to
      `pactl set-sink-volume`. Requires read access to the matching
      /dev/hidrawN node -- see the udev rule mentioned below.

  Windows 11: uses the `hid` (hidapi) package to open the device by
      VID/PID + vendor usage page, and `pycaw` (Windows Core Audio API
      bindings) to set the default output device's master volume.
      Install the extra dependencies first:
          pip install -r host/requirements-windows.txt
      No driver setup needed -- Windows' generic HID driver handles
      vendor-defined HID collections out of the box, and admin rights are
      NOT required to open or read a HID device.

Usage:
    python3 host/volume_daemon.py

Linux permission errors: if you get "Permission denied" opening
/dev/hidrawN, add a udev rule granting your user (or the `input` group)
access to hidraw devices from this board (VID 239a / PID 800e -- Adafruit
ItsyBitsy 32u4 5V 16MHz), then replug the board.

Rev I (2026-07-27): MCU migrated from a Raspberry Pi Pico (VID 2e8a / PID
0005) to an Adafruit ItsyBitsy 32u4 (VID 239a / PID 800e). Arduino's HID.h
requires a Report ID on custom report descriptors, so reports are now 2
bytes (report ID + percent) instead of 1.

Windows 11 support added same revision: platform-specific device I/O and
volume-control backends, selected automatically at runtime via
sys.platform. The wire protocol (VID/PID, vendor usage page 0xFF00/usage
0x01, 2-byte report) is identical on both platforms -- only how the host
opens the device and how it applies the volume differs.
"""

import sys

VID = "239a"
PID = "800e"
REPORT_ID = 0x01

VID_INT = 0x239A
PID_INT = 0x800E
USAGE_PAGE = 0xFF00
USAGE = 0x01


# =========================================================================
# Linux backend: /dev/hidrawN + pactl
# =========================================================================

def _linux_find_hidraw_device():
    import glob
    import re

    hid_id_re = re.compile(r"HID_ID=0003:0000([0-9A-Fa-f]{4}):0000([0-9A-Fa-f]{4})")
    for uevent_path in glob.glob("/sys/class/hidraw/hidraw*/device/uevent"):
        try:
            with open(uevent_path) as f:
                contents = f.read()
        except OSError:
            continue
        m = hid_id_re.search(contents)
        if not m:
            continue
        vid, pid = m.group(1).lower(), m.group(2).lower()
        if vid == VID and pid == PID:
            hidraw_name = uevent_path.split("/")[4]  # e.g. "hidraw10"
            return "/dev/" + hidraw_name
    return None


def _linux_set_volume_percent(percent):
    import subprocess

    subprocess.run(
        ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "{}%".format(percent)],
        check=False,
    )
    print("Set system volume to {}%".format(percent))


def _run_linux():
    import time

    while True:
        dev_path = _linux_find_hidraw_device()
        if not dev_path:
            print("Could not find the ItsyBitsy's hidraw device (VID {}:{}). "
                  "Is it plugged in and running rotary_volume.ino? Retrying in 2s...".format(VID, PID),
                  file=sys.stderr)
            try:
                time.sleep(2)
            except KeyboardInterrupt:
                print("\nStopped.")
                return
            continue

        print("Reading volume reports from {}".format(dev_path))
        try:
            with open(dev_path, "rb", buffering=0) as f:
                while True:
                    data = f.read(2)
                    if not data or len(data) < 2:
                        continue
                    if data[0] != REPORT_ID:
                        continue
                    percent = data[1]
                    _linux_set_volume_percent(percent)
        except PermissionError:
            print("Permission denied opening {}. See the docstring at the top of "
                  "this script for the udev rule needed.".format(dev_path), file=sys.stderr)
            sys.exit(1)
        except OSError as e:
            # Transient USB hiccup/reset (e.g. Errno 5 I/O error) -- the
            # board is still there but the file handle died. Reopen rather
            # than crashing the whole daemon.
            print("Lost connection to {} ({}). Reconnecting in 2s...".format(dev_path, e), file=sys.stderr)
            try:
                time.sleep(2)
            except KeyboardInterrupt:
                print("\nStopped.")
                return
        except KeyboardInterrupt:
            print("\nStopped.")
            return


# =========================================================================
# Windows backend: hidapi + pycaw
# =========================================================================

def _windows_find_device_path():
    import hid

    for info in hid.enumerate(VID_INT, PID_INT):
        # The ItsyBitsy enumerates as a composite device (CDC + HID); hidapi
        # gives one entry per top-level HID collection/interface, so filter
        # to our vendor-defined usage page/usage to avoid picking a
        # non-existent or unrelated collection.
        if info.get("usage_page") == USAGE_PAGE and info.get("usage") == USAGE:
            return info["path"]
    return None


def _windows_get_volume_interface():
    from ctypes import POINTER, cast

    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

    speakers = AudioUtilities.GetSpeakers()
    interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))


def _run_windows():
    import time

    try:
        import hid
    except ImportError:
        print("Missing dependency 'hid' (hidapi). Install with:\n"
              "    pip install -r host/requirements-windows.txt", file=sys.stderr)
        sys.exit(1)

    try:
        volume = _windows_get_volume_interface()
    except ImportError:
        print("Missing dependency 'pycaw'/'comtypes'. Install with:\n"
              "    pip install -r host/requirements-windows.txt", file=sys.stderr)
        sys.exit(1)

    while True:
        device_path = _windows_find_device_path()
        if not device_path:
            print("Could not find the ItsyBitsy's HID device (VID {}:{}, usage page "
                  "0x{:04X}). Is it plugged in and running rotary_volume.ino? "
                  "Retrying in 2s...".format(VID, PID, USAGE_PAGE), file=sys.stderr)
            try:
                time.sleep(2)
            except KeyboardInterrupt:
                print("\nStopped.")
                return
            continue

        h = hid.device()
        try:
            h.open_path(device_path)
        except OSError as e:
            print("Failed to open HID device ({}). Retrying in 2s...".format(e), file=sys.stderr)
            try:
                time.sleep(2)
            except KeyboardInterrupt:
                print("\nStopped.")
                return
            continue

        print("Reading volume reports from {}".format(device_path))
        try:
            h.set_nonblocking(False)
            while True:
                data = h.read(2)
                if not data or len(data) < 2:
                    continue
                if data[0] != REPORT_ID:
                    continue
                percent = data[1]
                volume.SetMasterVolumeLevelScalar(percent / 100.0, None)
                print("Set system volume to {}%".format(percent))
        except OSError as e:
            # Transient USB hiccup/reset -- reopen rather than crashing.
            print("Lost connection to {} ({}). Reconnecting in 2s...".format(device_path, e), file=sys.stderr)
            try:
                time.sleep(2)
            except KeyboardInterrupt:
                print("\nStopped.")
                return
        except KeyboardInterrupt:
            print("\nStopped.")
            return
        finally:
            h.close()


def main():
    if sys.platform.startswith("win"):
        _run_windows()
    else:
        _run_linux()


if __name__ == "__main__":
    main()

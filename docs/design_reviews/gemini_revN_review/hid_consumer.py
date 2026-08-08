"""
USB HID device for absolute volume control, built on top of the official
micropython-lib usb.device.hid.HIDInterface (vendored in /lib/usb/device/
since this plain Pico has no Wi-Fi for `mip install`).

Vendor-specific HID usage page 0xFF00, Usage 0x01: single-byte report is
the literal target volume percentage (0-100). Because it's a vendor page
(not Consumer Control), the OS does NOT treat it as a media key -- no mute
side effects, no per-OS step-size guessing, no drift. A host-side companion
script (see host/volume_daemon.py) reads this raw HID report via
/dev/hidrawN and calls `pactl set-sink-volume` directly with the exact
percentage.

Rev N: ported back from legacy_itsybitsy unchanged -- this vendor report
format was always Pico-native (the ItsyBitsy fork only added a Report ID
byte because Arduino's HID.h/PluggableUSB requires one for custom
descriptors; the Pico's usb.device.hid never needed it).
"""

from usb.device.hid import HIDInterface

_REPORT_DESCRIPTOR = bytes([
    0x06, 0x00, 0xFF,  # Usage Page (Vendor Defined 0xFF00)
    0x09, 0x01,        # Usage (0x01)
    0xA1, 0x01,        # Collection (Application)
    0x15, 0x00,        #   Logical Minimum (0)
    0x26, 0x64, 0x00,  #   Logical Maximum (100)
    0x75, 0x08,        #   Report Size (8)
    0x95, 0x01,        #   Report Count (1)
    0x09, 0x01,        #   Usage (0x01)
    0x81, 0x02,        #   Input (Data,Var,Abs)
    0xC0,              # End Collection
])


class VolumeHID(HIDInterface):
    def __init__(self):
        super().__init__(
            _REPORT_DESCRIPTOR,
            interface_str="Vintage Rotary Volume Control",
        )

    def set_volume_percent(self, percent):
        percent = max(0, min(100, int(percent)))
        if not self.is_open():
            return False
        return self.send_report(bytes([percent]))

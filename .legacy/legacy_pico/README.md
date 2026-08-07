# legacy_pico/

MicroPython firmware that ran on the original Raspberry Pi Pico (RP2040)
prototype. Superseded 2026-07-27 by the Arduino/ItsyBitsy 32u4 firmware in
`firmware/rotary_volume/` -- the Pico's ARM Cortex-M0+ / 264KB RAM / 2MB
flash were massively oversized for a "dial+hook -> USB HID volume/mute"
role once all audio processing moved off-MCU (Rev H, gutted Logitech USB
audio PCB). The ItsyBitsy 32u4 has native USB HID and just enough I/O.

Kept here as a reference until the new firmware is validated on hardware:
- `main.py` -- dial pulse decoder + switchhook + LED status, event-queue
  main loop, sends vendor HID reports via `hid_consumer.VolumeHID`.
- `hid_consumer.py` -- vendor-page (0xFF00) HID interface built on
  micropython-lib's `usb.device.hid.HIDInterface`.
- `led_blink_test.py` -- standalone LED wiring sanity check.

Required `mpremote`-based workflow (see `/memories/repo/vintage_headset.md`
for the full gotcha list) and a manually vendored `usb.device` package,
neither of which is needed on the ItsyBitsy (native USB + stock Arduino
`HID.h`).

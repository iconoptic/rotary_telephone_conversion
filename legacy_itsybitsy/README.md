# legacy_itsybitsy/

Arduino C++ firmware that ran on the Adafruit ItsyBitsy 32u4 (ATmega32u4),
which superseded `legacy_pico/` in Rev I (2026-07-27). Superseded in turn on
2026-08-02: the ItsyBitsy hardware failed during bell-driver bring-up (the
chip overheated and the board stopped enumerating over USB entirely,
unresponsive even to a manual bootloader reset). Root cause was never
conclusively proven with a DMM before the decision was made to abandon this
MCU and port the whole project back to the Raspberry Pi Pico. See
`docs/pico_port_handoff_prompt.md` for the full port plan and the leading
suspects for what fried the board.

Kept here as reference for wiring/timing/state-machine logic while porting:
- `rotary_volume/rotary_volume.ino` -- main firmware: dial pulse decoder,
  switchhook, 3 status LEDs, vendor HID volume reports, bell ring-generator
  state machine, IR trigger, AVR watchdog.
- `bell_ir_test/bell_ir_test.ino` -- standalone bell + IR bring-up sketch
  (serial commands r/h/s/a/b/i/c/+/-), no HID.
- `bell_button_test/bell_button_test.ino` -- standalone bell bring-up sketch
  triggered by a physical pushbutton instead of serial commands.
- `pin_monitor/pin_monitor.ino` -- whole-header GPIO diagnostic scanner.
- `led_blink_test/led_blink_test.ino` -- standalone LED wiring sanity check.

Required `arduino-cli` toolchain (`adafruit:avr:itsybitsy32u4_5V` FQBN) and
a udev rule for VID:PID `239a:800e`, neither of which is needed on the Pico.

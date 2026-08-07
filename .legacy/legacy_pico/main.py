"""
Rotary dial DECODER for Raspberry Pi Pico (RP2040) MicroPython -- Rev B.

Roles CONFIRMED by DMM measurement (2026-07-26), so no more auto-detection:
  - White pair = SHUNT / off-normal switch. Rest = 14.5kohm (bleeder resistor
    inside the dial in parallel with the contact), moved = ~0ohm. Needs an
    EXTERNAL 2.2kohm pull-up to 3V3 -- the internal ~50-80kohm pull-up is too
    weak and would leave GP2 below the logic-HIGH threshold even at rest.
  - Blue pair = PULSE switch. A true dry contact: ~0ohm (closed) at rest and
    through the whole wind-up, opens/closes ~10 times/sec during the spring
    return. Internal Pin.PULL_UP is fine here.

WIRING (see docs/rotary_dial_circuit_revC.svg):
  White pair -> one wire to GND, other wire to GP2 (phys pin 4) AND to a
                2.2kohm resistor up to 3V3 (phys pin 36).
  Blue  pair -> one wire to GND, other wire to GP3 (phys pin 5).
  LED1 "SHUNT" -> GP14 (phys 19) -> 330ohm -> LED -> GND. Lit whenever the
                  dial is off-normal (moving).
  LED2 "PULSE" -> GP15 (phys 20) -> 330ohm -> LED -> GND. Mirrors the raw
                  pulse contact -- this IS the ~10Hz square wave, visible to
                  the naked eye (well below the ~60-90Hz flicker-fusion
                  threshold), no oscilloscope needed.
  This revision REMOVES the binary digit-readout LEDs (GP16-19) -- not
  wired up on the breadboard, and LED2 already made the pulse train fully
  visible to the naked eye, so they weren't needed.

LOGGING: everything printed here goes out over the USB serial REPL. To save
a permanent log file on your host while testing, run this script via:
    mpremote connect /dev/ttyACM0 run main.py | tee dial_test_log.txt
(mpremote just streams the board's stdout, so `tee`/redirection works like
any other CLI tool -- nothing special needed on the Pico side.)

Debounce: 15ms software lockout via time.ticks_ms(), matching ~10ms of
expected mechanical contact bounce on vintage contacts.

NEW THIS REVISION -- USB HID volume control (Rev 2, absolute):
Each decoded digit is mapped to an absolute target volume percentage and
sent to the host as a single-byte vendor-defined HID report (0-100), see
hid_consumer.py:
    digit 1 -> 10%, digit 2 -> 20%, ... digit 9 -> 90%, digit 0 -> 100%
This is NOT the standard Consumer Control usage page -- that only offers
relative Volume Increment/Decrement/Mute, which proved unreliable (host-
specific step size, and overshoot past 0/100% could trigger the OS's own
auto-mute behavior). The vendor report is read on the host by a small
companion script (host/volume_daemon.py) via /dev/hidrawN, which sets the
exact volume with `pactl set-sink-volume` -- fully deterministic, no drift,
no mute side effects, since the OS never sees it as a media key at all.

NEW THIS REVISION -- switchhook (lever under the handset):
Green/White pair, a true dry contact (DMM confirmed: ~0ohm when the lever is
pressed, open/out-of-range when released) -- same internal-pull-up wiring
style as the Blue/PULSE pair, no external resistor needed.
  - Lever pressed (handset resting in the cradle, contact CLOSED) = on-hook
    -> mute (send a 0% volume report), without forgetting the last dialed
    target.
  - Lever released (handset lifted, contact OPEN) = off-hook -> restore the
    last dialed volume target.
WIRING: Green/White pair -> one wire to GND, other wire to GP4 (phys pin 6).
No LED is wired for this input (not needed to troubleshoot so far); add one
on a spare GPIO the same way as LED1/LED2 if that changes.
"""

import time
from machine import Pin
import usb.device
from hid_consumer import VolumeHID

SHUNT_PIN = 2   # physical pin 4  -- White pair, external 2.2kohm pull-up to 3V3
PULSE_PIN = 3   # physical pin 5  -- Blue pair, internal pull-up
HOOK_PIN = 4    # physical pin 6  -- Green/White switchhook pair, internal pull-up

LED_SHUNT_PIN = 14        # physical pin 19
LED_PULSE_PIN = 15        # physical pin 20

DEBOUNCE_MS = 15
HOOK_DEBOUNCE_MS = 30     # heavier spring-loaded lever than the dial contacts

shunt = Pin(SHUNT_PIN, Pin.IN)              # no internal pull -- R3 does the job
pulse = Pin(PULSE_PIN, Pin.IN, Pin.PULL_UP)
hook = Pin(HOOK_PIN, Pin.IN, Pin.PULL_UP)

led_shunt = Pin(LED_SHUNT_PIN, Pin.OUT)
led_pulse = Pin(LED_PULSE_PIN, Pin.OUT)

# Bring up the USB HID vendor-report interface alongside the normal CDC
# serial REPL (builtin_driver=True keeps the REPL/mpremote connection alive
# as a composite USB device). This re-enumerates the USB device, so any
# existing mpremote/serial connection will briefly drop and need reconnecting.
hid = VolumeHID()
usb.device.get().init(hid, builtin_driver=True)


def digit_to_percent(digit):
    return 100 if digit == 0 else digit * 10


# Small fixed-size ring buffer filled by the IRQs, drained by the main loop.
# Keeping the IRQ handlers this short avoids missing fast pulses.
# Each queued entry: (ticks_ms, 'SHUNT'/'PULSE'/'HOOK', 1 or 0)
_EVQ_LEN = 128
_evq = [(0, '', 0)] * _EVQ_LEN
_evq_head = 0
_evq_tail = 0
_last_irq_ms = {'SHUNT': 0, 'PULSE': 0, 'HOOK': 0}


def _push(now, ch, val):
    global _evq_head
    _evq[_evq_head] = (now, ch, val)
    _evq_head = (_evq_head + 1) % _EVQ_LEN


def _shunt_irq(pin):
    now = time.ticks_ms()
    if time.ticks_diff(now, _last_irq_ms['SHUNT']) < DEBOUNCE_MS:
        return
    _last_irq_ms['SHUNT'] = now
    at_rest = pin.value() == 1
    led_shunt.value(0 if at_rest else 1)
    _push(now, 'SHUNT', 0 if at_rest else 1)


def _pulse_irq(pin):
    now = time.ticks_ms()
    if time.ticks_diff(now, _last_irq_ms['PULSE']) < DEBOUNCE_MS:
        return
    _last_irq_ms['PULSE'] = now
    closed = pin.value() == 0
    led_pulse.value(1 if closed else 0)
    _push(now, 'PULSE', 1 if closed else 0)


def _hook_irq(pin):
    now = time.ticks_ms()
    if time.ticks_diff(now, _last_irq_ms['HOOK']) < HOOK_DEBOUNCE_MS:
        return
    _last_irq_ms['HOOK'] = now
    closed = pin.value() == 0
    _push(now, 'HOOK', 1 if closed else 0)


shunt.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=_shunt_irq)
pulse.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=_pulse_irq)
hook.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=_hook_irq)

print("Rotary dial decoder (Rev B, confirmed roles) + HID volume control ready.")
print("SHUNT=GP2 (White, ext. 2.2kohm pull-up)  PULSE=GP3 (Blue, int. pull-up)")
print("HOOK=GP4 (Green/White, int. pull-up)")
print("Dial a digit and watch the log + LEDs. digit N -> N*10% volume (0 -> 100%)")
print("Lift handset to unmute/restore volume, replace handset to mute.")
print("-" * 60)

dial_active = False
make_count = 0
last_volume_percent = 50
on_hook = (hook.value() == 0)
if on_hook:
    print("Startup state: ON-HOOK (muted)")
    hid.set_volume_percent(0)
else:
    print("Startup state: OFF-HOOK, volume {}%".format(last_volume_percent))
    hid.set_volume_percent(last_volume_percent)

while True:
    while _evq_tail != _evq_head:
        now, ch, val = _evq[_evq_tail]
        _evq_tail = (_evq_tail + 1) % _EVQ_LEN

        if ch == 'SHUNT':
            moved = bool(val)
            print("[{:>8d}ms] SHUNT -> {}".format(
                now, "OFF-NORMAL (dial moving)" if moved else "AT REST"))
            if moved and not dial_active:
                dial_active = True
                make_count = 0
            elif not moved and dial_active:
                dial_active = False
                digit = 0 if make_count == 10 else make_count
                print(">>> DIALED DIGIT: {} ({} pulses)".format(digit, make_count))
                last_volume_percent = digit_to_percent(digit)
                if on_hook:
                    print("    -> ON-HOOK (muted); volume target updated to {}% but held muted".format(
                        last_volume_percent))
                else:
                    ok = hid.set_volume_percent(last_volume_percent)
                    print("    -> HID volume report sent: {}% (open={})".format(last_volume_percent, ok))
        elif ch == 'PULSE':
            closed = bool(val)
            print("[{:>8d}ms] PULSE -> {}".format(
                now, "MAKE (closed)" if closed else "BREAK (open)"))
            if dial_active and closed:
                make_count += 1
        else:  # HOOK
            closed = bool(val)
            on_hook = closed
            if on_hook:
                print("[{:>8d}ms] HOOK -> ON-HOOK (handset down) -> MUTE".format(now))
                hid.set_volume_percent(0)
            else:
                print("[{:>8d}ms] HOOK -> OFF-HOOK (handset lifted) -> RESTORE {}%".format(
                    now, last_volume_percent))
                hid.set_volume_percent(last_volume_percent)

    time.sleep_ms(5)

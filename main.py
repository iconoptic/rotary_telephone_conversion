"""
Rotary dial DECODER + switchhook + LED status + USB HID absolute volume
control + bell ring generator + remote ring switch, for the Raspberry Pi
Pico (RP2040/MicroPython) -- Rev Q.

Rev Q -- the IR proximity trigger (Rev J-P) is RETIRED and replaced with a
direct-wired remote ring switch: a momentary mechanical switch (~5.5ohm
closed-contact resistance) wired via 30-50cm of ordinary hookup wire
directly to GP20 (TRIGGER_PIN) and GND. The phone will never be relocated,
so a plain wire is simpler than an optical sensor that needed calibration/
lockout tuning and was architecturally incapable of seeing an independent
remote transmitter anyway. See the "Rev Q summary" box on
docs/schematics/rotary_dial_circuit_revQ.svg and
/memories/repo/vintage_headset.md for the full rationale.

MOVED GP19 -> GP20 (2026-08-08): GP19 was bench-tested clean (no port
contention, board confirmed alive/booting) and showed ZERO response to the
physical switch across multiple presses -- no edge, on GP19 or on any other
free GPIO scanned simultaneously. GP19 itself is not proven bad (could be a
broken wire/joint/breadboard row never reaching the pad), but rather than
keep debugging blind, the switch is being moved to a fresh, previously-
unused pin (GP20) to isolate the fault. GP19 is now free/unused again.

WIRING (see docs/schematics/rotary_dial_circuit_revQ.svg):
  SHUNT_PIN (GP2)  -- White pair (dial off-normal). ~14.5kohm internal
                      bleeder resistor in parallel with the contact at
                      rest, so an EXTERNAL 2.2kohm pull-up to 3V3 (R3) is
                      MANDATORY -- the internal ~50-80kohm pull-up is too
                      weak and would leave GP2 below VIH even at rest.
  PULSE_PIN (GP3)  -- Blue pair (dial pulse contact). True dry contact,
                      internal Pin.PULL_UP is fine.
  HOOK_PIN  (GP4)  -- Green/White switchhook lever. True dry contact,
                      internal Pin.PULL_UP is fine. Debounce 30ms (heavier
                      spring than the dial contacts' 15ms).
  LED_SHUNT (GP14) -- 330ohm -> LED -> GND. Lit while the dial is off-normal.
  LED_PULSE (GP15) -- 330ohm -> LED -> GND. Mirrors the raw pulse contact.
  LED_HOOK  (GP16) -- 330ohm -> LED -> GND. NEW this revision -- no Pico
                      equivalent existed before; mirrors the ItsyBitsy's
                      LED_HOOK_PIN/D11 (Rev I/J). Lit while ON-HOOK (muted).
  BELL_A    (GP17) -- push-pull gate A. See bell.py's module docstring for
                      the full NPN level-shifter gate-drive design (the
                      3V3 GPIO does not reliably enhance the on-hand
                      IRFZ44N directly) -- this pin is driven ACTIVE-LOW.
  BELL_B    (GP18) -- push-pull gate B. Same active-low convention.
  TRIGGER   (GP20) -- remote ring switch (Rev Q, moved from GP19 2026-08-08
                      after GP19 showed zero response under clean bench
                      test). Internal Pin.PULL_UP; switch closes GP20 to
                      GND. A new C11 100nF filter cap to GND (mirrors C6 on
                      GP4) hardens the long unshielded wire run against EMI.
                      GP19 and GP26/ADC0 (old IR_RX) are now both free.

BELL/TRIGGER: see bell.py's module docstring for the ring-generator theory
of operation. The bell rings on any trigger closure regardless of hook
state -- there is no on-hook requirement (this is a deliberate departure
from historical rotary-phone behavior; the switch is meant to ring the
bell on demand, not simulate an incoming call). It is still silenced
immediately if the handset is lifted mid-ring (answered). TRIGGER_PIN is
interrupt-driven, debounced, and edge-triggered on the closing edge only
-- holding the switch closed does not re-trigger while already ringing or
before release.

ARCHITECTURE CHANGE FROM THE ORIGINAL legacy_pico/main.py: the old main
loop drained the dial/hook IRQ event queue then `time.sleep_ms(5)`. The
bell generator's 1ms deadband needs sub-5ms servicing, so this revision
calls `bell.update(now)` on every single pass of the loop, unconditionally,
with no sleep at all -- mirroring the ItsyBitsy .ino's unthrottled loop().
Dial/hook stay interrupt-driven (proven architecture, dial_test_log.txt
baseline) and are drained every pass too, just without an added delay.
VERIFY EMPIRICALLY (log actual half-period min/max via time.ticks_us())
that plain-Python MicroPython keeps up before adding any complexity like
@micropython.native -- per hard-won experience elsewhere in this repo,
that decorator has caused a SILENT regression before (see user memory).

GEMINI REV N REVIEW AUDIT (2026-08-02, see
docs/revN_design_review/01_gemini_deep_research_audit.md, finding D14/D15):
- WATCHDOG: a firmware hang mid-ring would leave a GPIO driven LOW forever,
  which (active-low) leaves a bell gate latched ON -- sustained DC into a
  T1 half-winding. machine.WDT is armed LAZILY on the first bell.start()
  call, not at boot: the rp2 WDT can never be stopped or reconfigured once
  created and survives a soft reset, so arming it at import time would
  kill any `mpremote fs cp`/`exec` call that takes longer than the
  timeout -- including ordinary firmware deployment. A `try/finally`
  around the main loop also forces the gates off if MicroPython itself
  raises an unhandled exception (the WDT only covers a true hang).
- GC: MicroPython's mark-and-sweep collector can pause for a few ms,
  which would stretch a 16-17ms half-cycle toward the saturation floor.
  gc.collect() is therefore called explicitly, and only while bell.is_idle().

LOGGING: everything printed here goes out over the USB serial REPL. To
save a permanent log file on your host while testing:
    mpremote connect /dev/ttyACM0 run main.py | tee dial_test_log_reN.txt

HID: vendor-defined usage page 0xFF00, usage 0x01, single-byte absolute
volume percent report (0-100) -- see hid_consumer.py. Read on the host by
host/volume_daemon.py via /dev/hidrawN, VID:PID 2e8a:0005.
"""

import time
import gc
import machine
from machine import Pin
import usb.device
from hid_consumer import VolumeHID
from bell import BellRinger

SHUNT_PIN = 2
PULSE_PIN = 3
HOOK_PIN = 4

LED_SHUNT_PIN = 14
LED_PULSE_PIN = 15
LED_HOOK_PIN = 16

BELL_A_PIN = 17
BELL_B_PIN = 18
TRIGGER_PIN = 20   # Rev Q: remote ring switch. Moved from GP19 2026-08-08 (zero response on GP19).

DEBOUNCE_MS = 15
HOOK_DEBOUNCE_MS = 30
TRIGGER_DEBOUNCE_MS = 20

WDT_TIMEOUT_MS = 5000   # lazily armed on first bell.start() -- see module docstring
GC_INTERVAL_MS = 5000   # only run while bell.is_idle() -- see module docstring

shunt = Pin(SHUNT_PIN, Pin.IN)              # no internal pull -- R3 does the job
pulse = Pin(PULSE_PIN, Pin.IN, Pin.PULL_UP)
hook = Pin(HOOK_PIN, Pin.IN, Pin.PULL_UP)
trigger = Pin(TRIGGER_PIN, Pin.IN, Pin.PULL_UP)   # Rev Q: remote ring switch

led_shunt = Pin(LED_SHUNT_PIN, Pin.OUT)
led_pulse = Pin(LED_PULSE_PIN, Pin.OUT)
led_hook = Pin(LED_HOOK_PIN, Pin.OUT)

bell = BellRinger(BELL_A_PIN, BELL_B_PIN, active_low=True)

# Re-enumerates the USB device (builtin_driver=True keeps the CDC/REPL
# connection alive as a composite device) -- any existing mpremote/serial
# connection will briefly drop and need reconnecting.
hid = VolumeHID()
usb.device.get().init(hid, builtin_driver=True)


def digit_to_percent(digit):
    return 100 if digit == 0 else digit * 10


# Small fixed-size ring buffer filled by the IRQs, drained by the main loop.
_EVQ_LEN = 128
_evq = [(0, '', 0)] * _EVQ_LEN
_evq_head = 0
_evq_tail = 0
_last_irq_ms = {'SHUNT': 0, 'PULSE': 0, 'HOOK': 0, 'TRIGGER': 0}


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


def _trigger_irq(pin):
    # Rev Q: remote ring switch. Edge-triggered on the CLOSING edge only --
    # the release edge is ignored entirely, so holding the switch shut
    # cannot re-trigger a ring.
    now = time.ticks_ms()
    if time.ticks_diff(now, _last_irq_ms['TRIGGER']) < TRIGGER_DEBOUNCE_MS:
        return
    _last_irq_ms['TRIGGER'] = now
    if pin.value() == 0:
        _push(now, 'TRIGGER', 1)


shunt.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=_shunt_irq)
pulse.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=_pulse_irq)
hook.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=_hook_irq)
trigger.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=_trigger_irq)

print("Rotary dial decoder (Rev Q, Pico) + HID volume + bell + remote switch ready.")
print("SHUNT=GP2 (White, ext. 2.2kohm pull-up)  PULSE=GP3 (Blue, int. pull-up)")
print("HOOK=GP4 (Green/White, int. pull-up)  BELL=GP17/18 (active-low)  TRIGGER=GP20 (int. pull-up)")
print("Dial a digit and watch the log + LEDs. digit N -> N*10% volume (0 -> 100%)")
print("Lift handset to unmute/restore volume, replace handset to mute.")
print("-" * 60)

dial_active = False
make_count = 0
last_volume_percent = 50
on_hook = (hook.value() == 0)
led_hook.value(1 if on_hook else 0)
if on_hook:
    print("Startup state: ON-HOOK (muted)")
    hid.set_volume_percent(0)
else:
    print("Startup state: OFF-HOOK, volume {}%".format(last_volume_percent))
    hid.set_volume_percent(last_volume_percent)

_wdt = None
_last_gc_ms = time.ticks_ms()

try:
    while True:
        now = time.ticks_ms()

        # Serviced every pass, unconditionally, so half-cycles/deadband stay accurate.
        bell.update(now)

        while _evq_tail != _evq_head:
            ev_now, ch, val = _evq[_evq_tail]
            _evq_tail = (_evq_tail + 1) % _EVQ_LEN

            if ch == 'SHUNT':
                moved = bool(val)
                print("[{:>8d}ms] SHUNT -> {}".format(
                    ev_now, "OFF-NORMAL (dial moving)" if moved else "AT REST"))
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
                    ev_now, "MAKE (closed)" if closed else "BREAK (open)"))
                if dial_active and closed:
                    make_count += 1
            elif ch == 'HOOK':
                closed = bool(val)
                on_hook = closed
                led_hook.value(1 if on_hook else 0)
                if on_hook:
                    print("[{:>8d}ms] HOOK -> ON-HOOK (handset down) -> MUTE".format(ev_now))
                    hid.set_volume_percent(0)
                else:
                    print("[{:>8d}ms] HOOK -> OFF-HOOK (handset lifted) -> RESTORE {}%".format(
                        ev_now, last_volume_percent))
                    hid.set_volume_percent(last_volume_percent)
                    if not bell.is_idle():
                        print("    -> handset answered, bell silenced")
                        bell.stop()
            else:  # TRIGGER (Rev Q: remote ring switch, closing edge only)
                if not bell.is_idle():
                    print("[{:>8d}ms] TRIGGER -> ignored, already ringing".format(ev_now))
                else:
                    print("[{:>8d}ms] TRIGGER -> ringing".format(ev_now))
                    if _wdt is None:
                        _wdt = machine.WDT(timeout=WDT_TIMEOUT_MS)
                        print("    -> watchdog armed ({}ms, cannot be disarmed)".format(WDT_TIMEOUT_MS))
                    bell.start(ev_now)

        if _wdt is not None:
            _wdt.feed()

        if bell.is_idle() and time.ticks_diff(now, _last_gc_ms) >= GC_INTERVAL_MS:
            gc.collect()
            _last_gc_ms = now
finally:
    bell.stop()

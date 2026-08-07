"""
Rotary dial DECODER + switchhook + LED status + USB HID absolute volume
control + bell ring generator + IR proximity trigger, for the Raspberry Pi
Pico (RP2040/MicroPython) -- Rev N.

Rev N -- MCU migration BACK from the Adafruit ItsyBitsy 32u4 (Rev I-M),
which failed (overheated, stopped enumerating over USB) during bell-driver
bring-up. This restores the original dial/hook/HID subset (legacy_pico/)
and ALSO ports the bell ring generator + IR trigger that were designed and
firmware-complete on the ItsyBitsy but never had a Pico equivalent -- see
docs/pico_port_handoff_prompt.md for the full port mandate and
/memories/repo/vintage_headset.md for the design history.

WIRING (see docs/rotary_dial_circuit_revN.svg once drawn):
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
  IR_TX     (GP19) -- IR emitter LED (via R10). Digital out.
  IR_RX     (GP26/ADC0) -- IR phototransistor emitter-follower (+ R11 to
                      GND). Analog in.

BELL/IR: see bell.py and ir_trigger.py module docstrings for the full
theory of operation. The bell only rings while ON-HOOK (mirrors the
ItsyBitsy firmware's refusal to ring into a lifted handset) and is
silenced immediately if the handset is answered mid-ring. IR sampling is
skipped entirely while the bell is ringing (a sample blocks for a couple
hundred microseconds and would distort the ring waveform).

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
from ir_trigger import IRTrigger

SHUNT_PIN = 2
PULSE_PIN = 3
HOOK_PIN = 4

LED_SHUNT_PIN = 14
LED_PULSE_PIN = 15
LED_HOOK_PIN = 16

BELL_A_PIN = 17
BELL_B_PIN = 18
IR_TX_PIN = 19
IR_RX_PIN = 26

DEBOUNCE_MS = 15
HOOK_DEBOUNCE_MS = 30

WDT_TIMEOUT_MS = 5000   # lazily armed on first bell.start() -- see module docstring
GC_INTERVAL_MS = 5000   # only run while bell.is_idle() -- see module docstring

shunt = Pin(SHUNT_PIN, Pin.IN)              # no internal pull -- R3 does the job
pulse = Pin(PULSE_PIN, Pin.IN, Pin.PULL_UP)
hook = Pin(HOOK_PIN, Pin.IN, Pin.PULL_UP)

led_shunt = Pin(LED_SHUNT_PIN, Pin.OUT)
led_pulse = Pin(LED_PULSE_PIN, Pin.OUT)
led_hook = Pin(LED_HOOK_PIN, Pin.OUT)

bell = BellRinger(BELL_A_PIN, BELL_B_PIN, active_low=True)
ir = IRTrigger(IR_TX_PIN, IR_RX_PIN)

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

print("Rotary dial decoder (Rev N, Pico) + HID volume + bell + IR trigger ready.")
print("SHUNT=GP2 (White, ext. 2.2kohm pull-up)  PULSE=GP3 (Blue, int. pull-up)")
print("HOOK=GP4 (Green/White, int. pull-up)  BELL=GP17/18 (active-low)  IR TX=GP19 RX=GP26")
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

irb = ir.calibrate()
print("IR baseline (emitter/detector crosstalk) = {} counts; trigger above {}".format(
    irb, irb + ir.margin))

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
            else:  # HOOK
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

        # IR proximity trigger -- only while the bell isn't already ringing (a
        # sample blocks briefly and would distort the ring waveform anyway).
        if bell.is_idle() and ir.poll(now):
            if on_hook:
                print("[{:>8d}ms] IR TRIGGER -> ringing".format(now))
                if _wdt is None:
                    _wdt = machine.WDT(timeout=WDT_TIMEOUT_MS)
                    print("    -> watchdog armed ({}ms, cannot be disarmed)".format(WDT_TIMEOUT_MS))
                bell.start(now)
            else:
                print("[{:>8d}ms] IR TRIGGER -> ignored, handset off-hook".format(now))

        if _wdt is not None:
            _wdt.feed()

        if bell.is_idle() and time.ticks_diff(now, _last_gc_ms) >= GC_INTERVAL_MS:
            gc.collect()
            _last_gc_ms = now
finally:
    bell.stop()

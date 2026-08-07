"""
Standalone bell + IR bring-up tool for the Raspberry Pi Pico (RP2040/
MicroPython) -- Rev N. Mirrors legacy_itsybitsy/bell_ir_test/bell_ir_test.ino
in spirit, adapted to this repo's established phased-bring-up pattern (see
mic_meter.py/receiver_test.py in prior session history): a library of plain
functions called interactively over mpremote's REPL, NOT a live serial
character-command parser (mpremote doesn't give this script an easy way to
read raw stdin chars while also printing).

Does NOT import usb.device or hid_consumer, and does NOT load the dial/hook
state machine -- flash/run this FIRST when bringing up new bell/IR hardware
so a fault can only be in the new hardware, not main.py.

Usage (from a host shell):
    mpremote connect /dev/ttyACM0 exec "import bell_ir_test as b; b.ring()"
    mpremote connect /dev/ttyACM0 exec "import bell_ir_test as b; b.dc_test('a')"
    mpremote connect /dev/ttyACM0 exec "import bell_ir_test as b; b.ir_monitor(20)"
    mpremote connect /dev/ttyACM0 exec "import bell_ir_test as b; b.gate_hold('a', 1)"
or open an interactive REPL (`mpremote connect /dev/ttyACM0`) and call the
functions directly -- Ctrl-C aborts ring()/hold()/ir_monitor()/gate_hold()
cleanly.

WIRING: see bell.py and ir_trigger.py module docstrings, and
docs/pico_port_handoff_prompt.md, for the full pin list and gate-drive
theory (BELL_A/BELL_B are ACTIVE-LOW through an NPN level shifter).
"""

import time

from machine import ADC

from bell import BellRinger
from ir_trigger import IRTrigger

BELL_A_PIN = 17
BELL_B_PIN = 18
IR_TX_PIN = 19
IR_RX_PIN = 26

# MUST match the physical centre-tap rail. Rev P: the 160G24's tap is back
# on 5V VBUS (jumper 6-7) and the 12V wall wart is retired. Deploy this
# ONLY once the tap is physically rewired to VBUS -- running SUPPLY_V = 5
# against a 12V tap drops the strike-mode interlock (this value caps strike
# on-time: 5V -> 9ms, 12V -> 4ms, and >5.5V locks out full-square drive).
SUPPLY_V = 5

bell = BellRinger(BELL_A_PIN, BELL_B_PIN, active_low=True, supply_v=SUPPLY_V)
ir = IRTrigger(IR_TX_PIN, IR_RX_PIN)

# GPIO29/ADC3 reads VSYS/3 on the Pico -- our no-scope brownout/inrush
# detector for the bell's ~300mA LV-side draw.
_vsys_adc = ADC(29)


def vsys():
    """One-shot 5V-rail (VSYS) reading in volts, printed and returned."""
    v = _vsys_adc.read_u16() * 3 * 3.3 / 65535
    print("VSYS = {:.2f}V".format(v))
    return v


class _RailMeter:
    """Tracks min/max VSYS across a test run; sample() is cheap enough to
    call every state-machine pass without disturbing half-cycle timing."""

    def __init__(self):
        self.lo = 65535
        self.hi = 0

    def sample(self):
        raw = _vsys_adc.read_u16()
        if raw < self.lo:
            self.lo = raw
        if raw > self.hi:
            self.hi = raw

    def report(self):
        k = 3 * 3.3 / 65535
        print("VSYS during test: min {:.2f}V / max {:.2f}V".format(self.lo * k, self.hi * k))
        if self.lo * k < 4.5:
            print("WARNING: rail sagged below 4.5V -- USB current budget problem")


def ring():
    """Standard cadence (2s ring / 4s pause, 2 bursts). Blocks until done; Ctrl-C aborts."""
    meter = _RailMeter()
    bell.start(time.ticks_ms())
    try:
        while not bell.is_idle():
            bell.update(time.ticks_ms())
            meter.sample()
        print("ring cadence done")
    except KeyboardInterrupt:
        print("aborted")
    finally:
        bell.stop()
        meter.report()


def hold(seconds=10):
    """Continuous ring for measuring/tuning, auto-stops after `seconds` (a
    dropped mpremote session must not leave the bell ringing forever --
    see docs/revN_design_review/01_gemini_deep_research_audit.md finding
    D14). Ctrl-C stops early."""
    meter = _RailMeter()
    bell.start(time.ticks_ms(), hold=True)
    print("ringing continuously for up to {}s -- Ctrl-C to stop early".format(seconds))
    end_ms = time.ticks_add(time.ticks_ms(), seconds * 1000)
    try:
        while time.ticks_diff(end_ms, time.ticks_ms()) > 0:
            bell.update(time.ticks_ms())
            meter.sample()
        print("hold timed out, stopping")
    except KeyboardInterrupt:
        print("stopped")
    finally:
        bell.stop()
        meter.report()


def dc_test(gate):
    """Capped 10ms half-winding continuity check ('a' or 'b'). NOT a
    substitute for the unpowered DMM R(3-6)~=2xR(3-4) check."""
    meter = _RailMeter()
    bell.dc_test(gate, time.ticks_ms())
    while not bell.is_idle():
        bell.update(time.ticks_ms())
        meter.sample()
    print("DC test done")
    meter.report()


def gate_hold(gate, level, seconds=15, t1_disconnected=False):
    """Force GP17/GP18 (BELL_A/BELL_B) to a fixed RAW GPIO level for
    `seconds`, bypassing the ring state machine entirely (no 10ms cap --
    this is for bringing up the Q5/Q6 NPN LEVEL SHIFTERS IN ISOLATION,
    BEFORE Q2/Q3/T1 are connected, so there's no half-winding downstream
    to overheat). `gate` is 'a' or 'b'; `level` is the RAW GPIO value (0
    or 1), NOT bell.py's active-low on/off semantics:
        level=0 (GPIO LOW)  -> NPN OFF -> GATE node pulled toward VBUS by Rc
        level=1 (GPIO HIGH) -> NPN ON (saturated) -> GATE node pulled near 0V
    INTERLOCK: level=0 turns the FET ON. With T1 wired, that puts sustained
    DC across a half-winding (core saturates, current -> 5V/DCR ~ amps --
    the exact failure class that killed the ItsyBitsy). Requires
    t1_disconnected=True to run.
    Ctrl-C stops early. Always leaves the pin back at the boot-safe OFF
    level (GPIO HIGH) when done, matching bell.py's default state.
    """
    if level == 0 and not t1_disconnected:
        print("REFUSED: level=0 holds the FET ON = DC across a T1 half-winding.")
        print("Only run this with T1 physically disconnected, then pass t1_disconnected=True.")
        return
    pin = bell.pin_b if gate == 'b' else bell.pin_a
    gpio = BELL_B_PIN if gate == 'b' else BELL_A_PIN
    pin.value(level)
    print("GP{} forced {} for up to {}s -- probe GATE_{} now (Ctrl-C to stop early)".format(
        gpio, level, seconds, gate.upper()))
    try:
        time.sleep(seconds)
        print("timed out")
    except KeyboardInterrupt:
        print("stopped early")
    finally:
        bell.stop()
        print("GP{} released back to boot-safe OFF (HIGH)".format(gpio))


def set_freq(hz):
    actual = bell.set_ring_freq(hz)
    print("ring frequency = {}Hz (half period {}ms)".format(actual, bell.half_period_ms))
    return actual


def strike(freq=20, on_ms=None, seconds=10):
    """Duty-limited resonance drive (sub-25Hz allowed -- flux bounded by
    on_ms, not period; see bell.set_strike). on_ms=None uses the max safe
    for the declared supply. Mode stays active until set_freq() restores
    the plain square drive."""
    if on_ms is None:
        on_ms = bell.max_safe_on_ms()
    hz, on = bell.set_strike(freq, on_ms)
    print("strike mode: {}Hz, {}ms on-time per half-cycle ({}V tap)".format(
        hz, on, bell.supply_v))
    hold(seconds)


def supply(volts):
    """Runtime override of the declared centre-tap voltage (source of truth
    is SUPPLY_V above -- keep it in sync with the hardware)."""
    cap = bell.set_supply(volts)
    print("tap supply declared {}V -> max strike on-time {}ms".format(volts, cap))
    return cap


def sweep(freqs=(15, 18, 20, 23, 26, 30, 35, 40), on_ms_list=None, dwell=4, pause=1.5):
    """Walks every (freq, on_ms) combination via strike(), `dwell` seconds
    each with a `pause`-second gap so attempts are audibly distinct. Prints
    a labeled header before each so live serial output lines up with what
    you hear. on_ms_list defaults to [max_safe_on_ms()] -- the strongest
    legal drive at the declared supply; on_ms can only go DOWN from there
    (raising it risks core saturation), so pass e.g. (1, 2, 3) only to
    compare weaker duty, never higher."""
    if on_ms_list is None:
        on_ms_list = [bell.max_safe_on_ms()]
    for hz in freqs:
        for on in on_ms_list:
            print("=== {}Hz, {}ms on-time ===".format(hz, on))
            strike(freq=hz, on_ms=on, seconds=dwell)
            time.sleep(pause)
    print("sweep done")


def ir_sample():
    """One synchronous dark/lit/dark 3-point sample, printed and returned
    (matches IRTrigger._read_delta's mains-flicker rejection scheme)."""
    delta = ir._read_delta()
    print("delta={} (baseline {})".format(delta, ir.baseline))
    return delta


def ir_calibrate():
    baseline = ir.calibrate()
    print("IR baseline (direct emitter->detector crosstalk) = {} counts; trigger above {}".format(
        baseline, baseline + ir.margin))
    return baseline


def ir_monitor(seconds=10):
    """Print one IR sample per second for `seconds`. Ctrl-C stops early."""
    end_ms = time.ticks_add(time.ticks_ms(), seconds * 1000)
    try:
        while time.ticks_diff(end_ms, time.ticks_ms()) > 0:
            ir_sample()
            time.sleep_ms(1000)
    except KeyboardInterrupt:
        print("stopped")


if __name__ == "__main__":
    print("Bell + IR bring-up tool ready. Call ring(), hold(), dc_test('a'/'b'),")
    print("gate_hold('a'/'b', 0/1, seconds), set_freq(hz), ir_sample(), ir_calibrate(), or ir_monitor(seconds).")
    ir_calibrate()

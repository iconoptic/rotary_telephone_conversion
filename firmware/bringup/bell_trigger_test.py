"""
Standalone bell + remote-switch bring-up tool for the Raspberry Pi Pico
(RP2040/MicroPython) -- Rev Q. Renamed from bell_ir_test.py: the IR
proximity trigger (Rev J-P) is retired and replaced by a direct-wired
remote ring switch on GP20 (moved from GP19 2026-08-08 after GP19 showed
zero response under a clean bench test -- see main.py's module docstring
and docs/schematics/rotary_dial_circuit_revQ.svg for the full rationale).
Adapted from this repo's established phased-bring-up pattern: a library
of plain functions called interactively over mpremote's REPL, NOT a live
serial character-command parser (mpremote doesn't give this script an
easy way to read raw stdin chars while also printing).

Does NOT import usb.device or hid_consumer, and does NOT load the dial/hook
state machine -- flash/run this FIRST when bringing up new bell/switch
hardware so a fault can only be in the new hardware, not main.py.

Usage (from a host shell):
    mpremote connect /dev/ttyACM0 exec "import bell_trigger_test as b; b.ring()"
    mpremote connect /dev/ttyACM0 exec "import bell_trigger_test as b; b.dc_test('a')"
    mpremote connect /dev/ttyACM0 exec "import bell_trigger_test as b; b.trigger_status()"
    mpremote connect /dev/ttyACM0 exec "import bell_trigger_test as b; b.gate_hold('a', 1)"
or open an interactive REPL (`mpremote connect /dev/ttyACM0`) and call the
functions directly -- Ctrl-C aborts ring()/hold()/gate_hold() cleanly.

WIRING: see bell.py's module docstring and
docs/schematics/rotary_dial_circuit_revQ.svg for the full pin list and
gate-drive theory (BELL_A/BELL_B are ACTIVE-LOW through an NPN level
shifter). TRIGGER_PIN (GP20) is a plain Pin.PULL_UP input; the remote
switch closes it to GND. GP19 is free/unused (moved here 2026-08-08).
"""

import time

from machine import ADC, Pin

from bell import BellRinger

BELL_A_PIN = 17
BELL_B_PIN = 18
TRIGGER_PIN = 20   # Rev Q: remote ring switch. Moved from GP19 2026-08-08 (zero response on GP19).

# MUST match the physical centre-tap rail. Rev P: the 160G24's tap is back
# on 5V VBUS (jumper 6-7) and the 12V wall wart is retired. Deploy this
# ONLY once the tap is physically rewired to VBUS -- running SUPPLY_V = 5
# against a 12V tap drops the strike-mode interlock (this value caps strike
# on-time: 5V -> 9ms, 12V -> 4ms, and >5.5V locks out full-square drive).
SUPPLY_V = 5

bell = BellRinger(BELL_A_PIN, BELL_B_PIN, active_low=True, supply_v=SUPPLY_V)
trigger = Pin(TRIGGER_PIN, Pin.IN, Pin.PULL_UP)

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


def trigger_status():
    """Print and return the current raw GP20/TRIGGER_PIN state (Rev Q:
    remote ring switch). Pin.PULL_UP means value()==1 (HIGH) at rest,
    value()==0 (LOW) while the remote switch is held closed."""
    closed = trigger.value() == 0
    print("TRIGGER GP20 = {} ({})".format(trigger.value(), "CLOSED" if closed else "open/at rest"))
    return closed


def bringup(dc_pause_s=2, hold_seconds=4, ring_after=False):
    """Guided progressive test sequence for a fully-wired Rev P bell stage
    (T1/Q2/Q3 built, RED/BLACK already attached -- unlike the earlier
    disconnected-secondary bench protocol). Chains the existing lowest-
    -energy-first tests instead of stringing them together by hand each
    bring-up session, printing VSYS-meter evidence at every stage.
    Stages (each also callable standalone if one needs a re-run):
      1. vsys() -- idle rail baseline.
      2. dc_test('a'), dc_test('b') -- 10ms capped pulses, `dc_pause_s`
         apart. Lowest-energy check that each gate/FET/winding conducts
         and the rail doesn't sag hard, before committing to sustained
         drive. Safe regardless of jumper 2-3 phasing (a single pulse
         doesn't depend on the two HV halves summing).
      3. hold(hold_seconds) -- short continuous 25Hz drive. THIS is the
         phasing check: read AC volts across the bell leads (or R18-to-
         RED/BLACK) on a DMM now -- ~85-96Vac loaded means jumper 2-3 is
         series-aiding (correct); near-0V means series-opposing (power
         off, swap one end of that jumper, re-run).
      4. ring() -- the real 2s-ring/4s-pause cadence, ONLY if
         ring_after=True (default False, so you can read the DMM and
         decide before the full cadence runs).
    Ctrl-C during any stage aborts that stage only (each underlying
    function already stops the bell in its own finally block).
    """
    print("=== STAGE 1/4: idle VSYS baseline ===")
    vsys()
    print("=== STAGE 2/4: dc_test each gate (10ms capped, lowest energy) ===")
    print("-- gate A --")
    dc_test('a')
    time.sleep(dc_pause_s)
    print("-- gate B --")
    dc_test('b')
    time.sleep(dc_pause_s)
    print("=== STAGE 3/4: hold({}s) -- READ DMM AC VOLTS ACROSS THE BELL NOW ===".format(
        hold_seconds))
    print("expect ~85-96Vac (phasing OK); near-0V means jumper 2-3 is series-opposing")
    hold(hold_seconds)
    if ring_after:
        print("=== STAGE 4/4: full ring() cadence ===")
        ring()
    else:
        print("bringup() stopped after the diagnostic hold -- call ring() directly, "
              "or re-run bringup(ring_after=True), once the Stage 3 reading looks right.")


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


if __name__ == "__main__":
    print("Bell + remote-switch bring-up tool ready. Call bringup() for the guided")
    print("progressive test sequence, or individually: ring(), hold(), dc_test('a'/'b'),")
    print("gate_hold('a'/'b', 0/1, seconds), set_freq(hz), trigger_status().")

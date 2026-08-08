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
or open an interactive REPL (`mpremote connect /dev/ttyACM0`) and call the
functions directly -- Ctrl-C aborts ring()/hold()/ir_monitor() cleanly.

WIRING: see bell.py and ir_trigger.py module docstrings, and
docs/pico_port_handoff_prompt.md, for the full pin list and gate-drive
theory (BELL_A/BELL_B are ACTIVE-LOW through an NPN level shifter).
"""

import time

from bell import BellRinger
from ir_trigger import IRTrigger

BELL_A_PIN = 17
BELL_B_PIN = 18
IR_TX_PIN = 19
IR_RX_PIN = 26

bell = BellRinger(BELL_A_PIN, BELL_B_PIN, active_low=True)
ir = IRTrigger(IR_TX_PIN, IR_RX_PIN)


def ring():
    """Standard cadence (2s ring / 4s pause, 2 bursts). Blocks until done; Ctrl-C aborts."""
    bell.start(time.ticks_ms())
    try:
        while not bell.is_idle():
            bell.update(time.ticks_ms())
    except KeyboardInterrupt:
        bell.stop()
        print("aborted")
        return
    print("ring cadence done")


def hold():
    """Continuous ring for measuring/tuning. Ctrl-C to stop."""
    bell.start(time.ticks_ms(), hold=True)
    print("ringing continuously -- Ctrl-C to stop")
    try:
        while True:
            bell.update(time.ticks_ms())
    except KeyboardInterrupt:
        bell.stop()
        print("stopped")


def dc_test(gate):
    """Capped 10ms half-winding continuity check ('a' or 'b'). NOT a
    substitute for the unpowered DMM R(3-6)~=2xR(3-4) check."""
    bell.dc_test(gate, time.ticks_ms())
    while not bell.is_idle():
        bell.update(time.ticks_ms())
    print("DC test done")


def set_freq(hz):
    actual = bell.set_ring_freq(hz)
    print("ring frequency = {}Hz (half period {}ms)".format(actual, bell.half_period_ms))
    return actual


def ir_sample():
    """One synchronous dark/lit/delta sample, printed and returned."""
    ir.tx.value(0)
    time.sleep_us(ir.settle_us)
    dark = ir.rx.read_u16()
    ir.tx.value(1)
    time.sleep_us(ir.settle_us)
    lit = ir.rx.read_u16()
    ir.tx.value(0)
    delta = lit - dark
    print("dark={} lit={} delta={} (baseline {})".format(dark, lit, delta, ir.baseline))
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
    print("set_freq(hz), ir_sample(), ir_calibrate(), or ir_monitor(seconds).")
    ir_calibrate()

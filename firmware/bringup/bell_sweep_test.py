"""
Comprehensive frequency x on-time (duty) parameter sweep for the Rev P
bell stage (T1 = 160G24, Q2/Q3 = STP55NF06L, tap on VBUS).

Standalone script built ON TOP of bell_trigger_test.py's already-initialized
BellRinger (imported, not re-constructed) so there is exactly one Pin()
owner for GP17/GP18 and one source of truth for SUPPLY_V. Does NOT import
usb.device/hid_consumer/main -- safe to run without disturbing the
dial/HID firmware.

Two independent sweeps, run separately so a bad reading in one mode can't
be misread as the other:
  - full_square_sweep(): legal 50%-duty square wave, frequency only.
    Valid ONLY while the declared tap is <=5.5V -- bell.py raises if not.
  - strike_sweep(): duty-limited strike mode across a frequency x
    on-time grid (covers the clapper's ~20Hz resonance region below the
    full-square saturation floor).
  - all_sweeps(): runs both back to back.

Every permutation reuses hold()/strike() from bell_trigger_test.py, so each
dwell window already prints its own VSYS-sag telemetry (the no-scope
brownout/inrush evidence) -- this script only adds the labeled grid walk
and a restore-to-default-frequency step at the end (so a run cut short by
Ctrl-C, or by any single call, never leaves the bell stuck in a
duty-limited/non-default state).

LISTEN/WATCH/DMM THE BELL LIVE DURING EACH DWELL WINDOW. This script has
no way to detect whether the clapper actually struck -- only whether the
drive circuit ran without an electrical fault.

Usage (bell should be RECONNECTED -- these sweeps are for finding a
striking setting, not the disconnected-secondary bench checks):
    mpremote connect /dev/ttyACM0 exec "import bell_sweep_test as s; s.full_square_sweep()"
    mpremote connect /dev/ttyACM0 exec "import bell_sweep_test as s; s.strike_sweep()"
    mpremote connect /dev/ttyACM0 exec "import bell_sweep_test as s; s.all_sweeps()"
Ctrl-C aborts the current dwell and skips to cleanup (each stage prints
a final restore-to-default line, matching bell_trigger_test.py's own
Ctrl-C-safe pattern).
"""

import time

import bell_trigger_test as b

# Full-square frequencies to test: MIN_RING_FREQ_HZ(25)..MAX_RING_FREQ_HZ(40)
# for the 160G24 at a <=5.5V tap (bell.py's set_ring_freq() clamps/raises
# outside this anyway -- kept explicit here so a failed permutation names
# the frequency that failed).
FULL_SQUARE_FREQS_HZ = (25, 28, 30, 33, 36, 40)

# Strike-mode frequencies: bell.set_strike() allows down to 15Hz (below the
# full-square floor) since flux is bounded by on_ms, not the half-period --
# this range brackets the clapper's ~20Hz mechanical resonance.
STRIKE_FREQS_HZ = (15, 17, 20, 23, 26, 30, 35, 40)


def _on_ms_grid():
    """Spread of duty-limited on-times up to the declared supply's safe
    cap (9ms at 5V, 4ms at 12V) -- always includes 1ms and the cap
    itself, de-duplicated for low caps."""
    cap = b.bell.max_safe_on_ms()
    grid = []
    for v in (1, 2, 3, 5, 7, cap):
        v = max(1, min(cap, v))
        if v not in grid:
            grid.append(v)
    return grid


def full_square_sweep(freqs=FULL_SQUARE_FREQS_HZ, dwell=3, pause=1.5):
    """Legal full-square (50%-duty) frequency-only sweep. `dwell` seconds
    continuous drive per frequency, `pause` seconds of silence between so
    attempts are audibly/visually distinct."""
    print("=== full-square sweep: {} frequencies, ~{:.0f}s total ===".format(
        len(freqs), len(freqs) * (dwell + pause)))
    try:
        for i, hz in enumerate(freqs, 1):
            actual = b.set_freq(hz)
            print("--- [{}/{}] full square {}Hz ---".format(i, len(freqs), actual))
            b.hold(dwell)
            time.sleep(pause)
        print("full-square sweep done")
    except KeyboardInterrupt:
        print("full-square sweep aborted")
    finally:
        b.set_freq(25)


def strike_sweep(freqs=STRIKE_FREQS_HZ, on_ms_list=None, dwell=3, pause=1):
    """Duty-limited strike-mode sweep across every (freq, on_ms)
    permutation -- comprehensive by design, not just the single
    strongest-legal-drive point. `dwell` seconds per permutation, `pause`
    seconds of silence between. Ends by restoring plain 25Hz full-square
    drive (clears the duty cap) regardless of how the sweep exits."""
    if on_ms_list is None:
        on_ms_list = _on_ms_grid()
    total = len(freqs) * len(on_ms_list)
    print("=== strike sweep: {} frequencies x {} on-times = {} permutations, ~{:.0f}s total ===".format(
        len(freqs), len(on_ms_list), total, total * (dwell + pause)))
    n = 0
    try:
        for hz in freqs:
            for on_ms in on_ms_list:
                n += 1
                print("--- [{}/{}] strike {}Hz, {}ms on-time ---".format(n, total, hz, on_ms))
                b.strike(freq=hz, on_ms=on_ms, seconds=dwell)
                time.sleep(pause)
        print("strike sweep done")
    except KeyboardInterrupt:
        print("strike sweep aborted")
    finally:
        b.set_freq(25)
        print("restored plain 25Hz full-square drive (duty cap cleared)")


def all_sweeps(full_square_kwargs=None, strike_kwargs=None):
    """Runs full_square_sweep() then strike_sweep() back to back."""
    full_square_sweep(**(full_square_kwargs or {}))
    time.sleep(2)
    strike_sweep(**(strike_kwargs or {}))


# Ranked by theoretical drive strength (volt-seconds per half-cycle), NOT by
# frequency order -- full-square 25Hz is the single strongest LEGAL
# continuous drive this transformer supports (20ms half-period, 0.93x rated
# flux); every strike-mode point below it is capped at max_safe_on_ms() (9ms
# at 5V), i.e. fewer volt-seconds than full-square-25Hz by construction, so
# don't expect strike mode to ever out-ring plain 25Hz -- it exists to reach
# frequencies (<25Hz) full-square can't legally hit at all.
TARGETED_POINTS = (
    ("full-square", 25, None),
    ("strike", 23, None),
    ("strike", 20, None),
    ("strike", 18, None),
    ("strike", 15, None),
)


def targeted_sweep(points=TARGETED_POINTS, dwell=6, pause=2.5):
    """Short, loudness-RANKED sweep (not a grid) -- use this once a full
    grid sweep has already run and volume was the limiting factor. Only
    tests the points that deliver the most volt-seconds per half-cycle:
    full-square 25Hz (max legal continuous drive) first, then strike mode
    at the on-time cap across the clapper's ~15-25Hz resonance band.
    Prints the theoretical mV.s for each point so DMM RMS readings can be
    correlated directly against drive strength -- note the reading after
    each dwell (this script cannot read the DMM for you). Longer dwell
    (default 6s) than the grid sweeps so a reading has time to settle."""
    cap = b.bell.max_safe_on_ms()
    print("=== targeted sweep: {} points, cap={}ms, ~{:.0f}s total ===".format(
        len(points), cap, len(points) * (dwell + pause)))
    n = 0
    try:
        for mode, hz, on_ms in points:
            n += 1
            if mode == "full-square":
                actual = b.set_freq(hz)
                on_time_ms = 500 // actual
                mvs = int(b.SUPPLY_V * on_time_ms)
                print("--- [{}/{}] full-square {}Hz (on={}ms, ~{}mV.s) ---".format(
                    n, len(points), actual, on_time_ms, mvs))
                b.hold(dwell)
            else:
                use_on_ms = on_ms if on_ms is not None else cap
                mvs = int(b.SUPPLY_V * use_on_ms)
                print("--- [{}/{}] strike {}Hz (on={}ms, ~{}mV.s) ---".format(
                    n, len(points), hz, use_on_ms, mvs))
                b.strike(freq=hz, on_ms=use_on_ms, seconds=dwell)
            print("    >>> note DMM RMS + whether it struck now <<<")
            time.sleep(pause)
        print("targeted sweep done")
    except KeyboardInterrupt:
        print("targeted sweep aborted")
    finally:
        b.set_freq(25)
        print("restored plain 25Hz full-square drive (duty cap cleared)")


if __name__ == "__main__":
    print("Bell parameter sweep tool ready. Call full_square_sweep(), strike_sweep(), targeted_sweep(), or all_sweeps().")

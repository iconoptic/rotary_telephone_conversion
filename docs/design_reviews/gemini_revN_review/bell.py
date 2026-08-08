"""
Bell ring generator for the Raspberry Pi Pico (RP2040/MicroPython) -- Rev N.

Non-blocking push-pull driver, ported from legacy_itsybitsy/rotary_volume/
rotary_volume.ino and legacy_itsybitsy/bell_ir_test/bell_ir_test.ino. This
never had a Pico implementation before this port.

THEORY (unchanged from the ItsyBitsy design -- see docs/transformer_primer.md
and docs/revK_design_review/ for the full derivation, not re-derived here):
the ringer coil (5.97kohm DC) needs ~90V/20Hz-class drive to move the
clapper, far beyond anything a bare 5V/3V3 GPIO can supply directly. BELL_A/
BELL_B alternately ground the two halves of a centre-tapped step-up
transformer's LV winding (centre tap on 5V); the HV winding drives the bell.
Currently T1 = Hammond 161G24 (single-primary, 60Hz-only core) -> saturation
floor 28Hz, default 30Hz.

GATE DRIVE -- ACTIVE-LOW, NOT A DIRECT PORT OF THE .ino LOGIC LEVELS:
the Pico's GPIO HIGH is 3V3, and the on-hand Q2/Q3 (IRFZ44N) have Vgs(th) up
to 4V -- 3V3 is not a reliable full-enhancement drive. Rather than buy a new
logic-level FET, each gate gets an NPN open-collector inverting level
shifter (Q5/Q6, e.g. 2N3904/2N2222 -- common small-signal bipolar; Q4 is
already the IR phototransistor):
    GPIO --Rb(~1k)--> NPN base <--pull-up(~10k)-- 5V
    NPN emitter -> GND
    NPN collector --pull-up Rc(~1k)--> 5V, feeds into the existing R12/R13
        100ohm gate series resistor -> Q2/Q3 gate (existing R14/R15 10k
        gate pulldowns stay, now a redundant-but-harmless second safety net)
This means: GPIO HIGH -> NPN ON -> collector pulled LOW -> Q2/Q3 gate LOW ->
FET OFF. GPIO LOW -> NPN OFF -> Rc pulls the gate HIGH -> FET ON. Critically,
the base pull-up makes "GPIO floating" (MCU reset/boot, before firmware
configures the pin) equivalent to "GPIO HIGH" -- NPN ON, FET OFF -- so the
bell defaults OFF at boot/reset, not ON. This module therefore drives its
output pins ACTIVE-LOW (`_ON_LEVEL = 0`); if the final hardware instead
drives Q2/Q3 directly (no level shifter), flip `active_low=False` in the
constructor and nothing else needs to change.
Resistor values above are starting points only -- bench-verify (scope the
gate node) before trusting them; see docs/pico_port_handoff_prompt.md and
the Phase 5 schematic work for the final component selection.

SOFT-START: from zero flux, a full-length first half-cycle would drive the
core to ~1.86x rated flux (deep saturation, amp-class current spike,
possible brownout right as the phone tries to ring). The first half-cycle
after any idle period or inter-burst gap is therefore half-length -- see
`_first_half_cycle` below.

TIMING: this is verified against wall-clock ms via time.ticks_ms()/
ticks_diff() (not raw subtraction -- MicroPython's tick counter wraps and
ticks_diff() handles that correctly, unlike Arduino's unsigned millis()
subtraction trick). update() must be called on every pass of the caller's
main loop, unconditionally, so half-cycles/deadband stay accurate -- do NOT
gate it behind a slower polling interval.
"""

import time
from machine import Pin

# Saturation floor/ceiling for the on-hand T1 (Hammond 161G24, 60Hz-only
# core): flux ratio = 333/(hz*12), so 28Hz = ~0.99x rated (last safe integer
# hertz), 30Hz = 0.93x (default, matches the ItsyBitsy design's safety
# margin). Re-derive (see docs/transformer_primer.md) if the transformer
# changes -- e.g. a dual-primary 160G24 drops the floor to 23Hz.
MIN_RING_FREQ_HZ = 28
MAX_RING_FREQ_HZ = 40
DEFAULT_RING_FREQ_HZ = 30

RING_DEADBAND_MS = 1     # both gates OFF across every half-cycle transition
RING_BURST_MS = 2000     # "ring" portion of the cadence
RING_GAP_MS = 4000       # "silence" portion of the cadence
RING_BURSTS = 2          # bursts per trigger
DC_TEST_MS = 10          # capped per revK_design_review finding #1 (was 1000ms -> ~2.5A rail short)

IDLE, BURST, GAP, HOLD, DC_TEST = range(5)


class BellRinger:
    def __init__(self, pin_a, pin_b, active_low=True, ring_freq_hz=DEFAULT_RING_FREQ_HZ):
        self.active_low = active_low
        self._on_level = 0 if active_low else 1
        self._off_level = 1 if active_low else 0
        self.pin_a = Pin(pin_a, Pin.OUT)
        self.pin_b = Pin(pin_b, Pin.OUT)
        self._gates_off()

        self.ring_freq_hz = ring_freq_hz
        self.half_period_ms = 500 // ring_freq_hz

        self.state = IDLE
        self.bursts_left = 0
        self.cadence_start_ms = 0
        self.toggle_ms = 0
        self.phase_b = False
        self.in_deadband = False
        self.first_half_cycle = False
        self.dc_test_pin = None

    def _gates_off(self):
        self.pin_a.value(self._off_level)
        self.pin_b.value(self._off_level)

    def set_ring_freq(self, hz):
        hz = max(MIN_RING_FREQ_HZ, min(MAX_RING_FREQ_HZ, hz))
        self.ring_freq_hz = hz
        self.half_period_ms = 500 // hz
        return hz

    def is_idle(self):
        return self.state == IDLE

    def start(self, now_ms, hold=False):
        """Begin the standard ring cadence, or continuous 'hold' for bench testing."""
        self.state = HOLD if hold else BURST
        self.bursts_left = 0 if hold else RING_BURSTS
        self.cadence_start_ms = now_ms
        self.toggle_ms = now_ms
        self.phase_b = False
        self.in_deadband = True
        self.first_half_cycle = True
        self._gates_off()

    def stop(self):
        self._gates_off()
        self.state = IDLE
        self.bursts_left = 0
        self.in_deadband = False

    def dc_test(self, gate, now_ms):
        """Capped-duration (DC_TEST_MS) single-gate continuity check -- NOT a
        substitute for the unpowered DMM R(3-6)~=2xR(3-4) check."""
        self._gates_off()
        self.state = DC_TEST
        self.cadence_start_ms = now_ms
        self.dc_test_pin = self.pin_b if gate == 'b' else self.pin_a
        self.dc_test_pin.value(self._on_level)

    def update(self, now_ms):
        """Call on every pass of the main loop, unconditionally."""
        if self.state == IDLE:
            return

        if self.state == DC_TEST:
            if time.ticks_diff(now_ms, self.cadence_start_ms) >= DC_TEST_MS:
                self._gates_off()
                self.state = IDLE
            return

        if self.state == GAP:
            if time.ticks_diff(now_ms, self.cadence_start_ms) >= RING_GAP_MS:
                self.state = BURST
                self.cadence_start_ms = now_ms
                self.toggle_ms = now_ms
                self.in_deadband = True
                self.first_half_cycle = True
            return

        # BURST or HOLD: run the oscillator; BURST additionally times out.
        if self.state == BURST and time.ticks_diff(now_ms, self.cadence_start_ms) >= RING_BURST_MS:
            self._gates_off()
            self.in_deadband = False
            self.bursts_left -= 1
            if self.bursts_left <= 0:
                self.state = IDLE
            else:
                self.state = GAP
                self.cadence_start_ms = now_ms
            return

        this_half_ms = (self.half_period_ms // 2) if self.first_half_cycle else self.half_period_ms
        if time.ticks_diff(now_ms, self.toggle_ms) >= this_half_ms:
            self._gates_off()
            self.toggle_ms = now_ms
            self.phase_b = not self.phase_b
            self.in_deadband = True
            self.first_half_cycle = False
        elif self.in_deadband and time.ticks_diff(now_ms, self.toggle_ms) >= RING_DEADBAND_MS:
            (self.pin_b if self.phase_b else self.pin_a).value(self._on_level)
            self.in_deadband = False

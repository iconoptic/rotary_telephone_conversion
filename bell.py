"""
Bell ring generator for the Raspberry Pi Pico (RP2040/MicroPython) -- Rev P.

Non-blocking push-pull driver, ported from legacy_itsybitsy/rotary_volume/
rotary_volume.ino and legacy_itsybitsy/bell_ir_test/bell_ir_test.ino. This
never had a Pico implementation before this port.

THEORY (unchanged from the ItsyBitsy design -- see docs/transformer_primer.md
and docs/revK_design_review/ for the full derivation, not re-derived here):
the ringer coil (5.97kohm DC) needs ~90V/20Hz-class drive to move the
clapper, far beyond anything a bare 5V/3V3 GPIO can supply directly. BELL_A/
BELL_B alternately ground the two halves of a centre-tapped step-up
transformer's LV winding (centre tap on 5V); the HV winding drives the bell.
Rev P: T1 = Hammond 160G24 (dual 115V primary in series = 19:1, 50/60Hz
core) -- the original Rev K spec part, now in hand. Saturation floor drops
to 25Hz (see the module-level constants below), default 25Hz.

GATE DRIVE -- ACTIVE-LOW, NOT A DIRECT PORT OF THE .ino LOGIC LEVELS:
Rev P's Q2/Q3 are STP55NF06L (logic-level, Vgs(th) max 1.7V), which 3V3
could likely drive directly -- but the NPN open-collector inverting level
shifters (Q5/Q6) from the IRFZ44N era are KEPT: already built and
bench-verified (2026-08-02), ~4.5V gate = deep full enhancement, and the
base pull-up keeps the bell OFF while a boot-time GPIO floats:
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

# Saturation floor/ceiling for T1 (Hammond 160G24, 50/60Hz core, Rev P):
# flux ratio = 277.5/(hz*12), so 25Hz = 0.93x rated at nominal 5V and
# ~0.97x at a worst-case USB VBUS of 5.25V -- still under rated flux.
# 20Hz (1.16x) stays illegal. (The interim 161G24 was a 60Hz-only core,
# constant 333, floor 30Hz; re-derive via docs/transformer_primer.md if
# the transformer changes again.)
MIN_RING_FREQ_HZ = 25
MAX_RING_FREQ_HZ = 40
DEFAULT_RING_FREQ_HZ = 25

# Peak volt-seconds (mV.s) tolerable from zero flux for the 160G24's 12V
# half-winding (sine-rated lambda_pk ~= 12*1.414/314 ~= 54mV.s, kept to ~48
# for margin). All on-time caps derive from this: 5V -> 9ms, 12V -> 4ms.
LAMBDA_MAX_MVS = 48
# Above this centre-tap voltage a plain 50%-duty square saturates the core
# at any frequency in the 25-40Hz band -- only duty-limited strike mode is
# permitted (e.g. 12V full square would need >=60Hz).
MAX_FULL_SQUARE_SUPPLY_V = 5.5

RING_DEADBAND_MS = 1     # both gates OFF across every half-cycle transition
RING_BURST_MS = 2000     # "ring" portion of the cadence
RING_GAP_MS = 4000       # "silence" portion of the cadence
RING_BURSTS = 2          # bursts per trigger
DC_TEST_MS = 10          # capped per revK_design_review finding #1 (was 1000ms -> ~2.5A rail short)

IDLE, BURST, GAP, HOLD, DC_TEST = range(5)


class BellRinger:
    def __init__(self, pin_a, pin_b, active_low=True, ring_freq_hz=DEFAULT_RING_FREQ_HZ,
                 supply_v=5.0):
        self.active_low = active_low
        self._on_level = 0 if active_low else 1
        self._off_level = 1 if active_low else 0
        self.pin_a = Pin(pin_a, Pin.OUT)
        self.pin_b = Pin(pin_b, Pin.OUT)
        self._gates_off()

        self.supply_v = supply_v
        self.ring_freq_hz = ring_freq_hz
        self.half_period_ms = 500 // ring_freq_hz
        self.max_on_ms = None
        if supply_v > MAX_FULL_SQUARE_SUPPLY_V:
            self.set_strike(ring_freq_hz, self.max_safe_on_ms())

        self.state = IDLE
        self.bursts_left = 0
        self.cadence_start_ms = 0
        self.toggle_ms = 0
        self.phase_b = False
        self.in_deadband = False
        self.gate_on = False
        self.first_half_cycle = False
        self.dc_test_pin = None

    def _gates_off(self):
        self.pin_a.value(self._off_level)
        self.pin_b.value(self._off_level)

    def max_safe_on_ms(self):
        return max(1, int(LAMBDA_MAX_MVS // self.supply_v))

    def set_supply(self, volts):
        """Declare the centre-tap rail voltage. Above 5.5V this forces
        strike mode (full square saturates) and re-clamps on_ms."""
        self.supply_v = volts
        if volts > MAX_FULL_SQUARE_SUPPLY_V:
            self.set_strike(self.ring_freq_hz, self.max_safe_on_ms())
        elif self.max_on_ms is not None:
            self.max_on_ms = min(self.max_on_ms, self.max_safe_on_ms())
        return self.max_safe_on_ms()

    def set_ring_freq(self, hz):
        if self.supply_v > MAX_FULL_SQUARE_SUPPLY_V:
            raise ValueError(
                "full-square drive saturates T1 above {}V tap -- use set_strike()".format(
                    MAX_FULL_SQUARE_SUPPLY_V))
        hz = max(MIN_RING_FREQ_HZ, min(MAX_RING_FREQ_HZ, hz))
        self.ring_freq_hz = hz
        self.half_period_ms = 500 // hz
        self.max_on_ms = None
        return hz

    def set_strike(self, hz, on_ms):
        """Duty-limited drive: gate conducts only the first `on_ms` of each
        half-cycle, so peak flux is bounded by V*on_ms alone (magnetizing
        current resets through the opposite body diode during the dead
        gap). This decouples strike rate from the core's full-square flux
        floor, allowing sub-25Hz drive to hit the clapper's ~20Hz
        mechanical resonance. The on_ms ceiling scales with the declared
        centre-tap supply via max_safe_on_ms() (5V -> 9ms, 12V -> 4ms)."""
        hz = max(15, min(MAX_RING_FREQ_HZ, hz))
        on_ms = max(1, min(self.max_safe_on_ms(), int(on_ms)))
        self.ring_freq_hz = hz
        self.half_period_ms = 500 // hz
        self.max_on_ms = on_ms
        return hz, on_ms

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
            if time.ticks_diff(now_ms, self.cadence_start_ms) >= min(DC_TEST_MS, self.max_safe_on_ms()):
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
            self.gate_on = False
            self.toggle_ms = now_ms
            self.phase_b = not self.phase_b
            self.in_deadband = True
            self.first_half_cycle = False
        elif self.in_deadband and time.ticks_diff(now_ms, self.toggle_ms) >= RING_DEADBAND_MS:
            (self.pin_b if self.phase_b else self.pin_a).value(self._on_level)
            self.in_deadband = False
            self.gate_on = True
        elif (self.gate_on and self.max_on_ms is not None
                and time.ticks_diff(now_ms, self.toggle_ms) >= RING_DEADBAND_MS + self.max_on_ms):
            self._gates_off()
            self.gate_on = False

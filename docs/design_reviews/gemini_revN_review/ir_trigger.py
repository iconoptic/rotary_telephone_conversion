"""
IR proximity trigger for the Raspberry Pi Pico (RP2040/MicroPython) -- Rev N.

Ported from legacy_itsybitsy/bell_ir_test/bell_ir_test.ino's irReadDelta()/
irCalibrate()/trigger-confirm loop. This never had a Pico implementation
before this port.

THEORY (unchanged): these are bare 2-leg phototransistors, no TSOP/38kHz
demodulator module, so ambient light is rejected by SYNCHRONOUS SAMPLING in
software instead -- read the ADC with the emitter off, then on, and use the
difference. The emitter and detector sit side by side, so there is always
some direct optical crosstalk; that resting delta is measured once at boot
(baseline) and the trigger threshold sits above it, making this a
reflective proximity sensor (wave a hand in front of the pair -> trigger).

RETUNE FROM SCRATCH ON REAL HARDWARE, do not trust the constants below as
final: they are placeholders carried over in spirit (not value) from the
AVR/10-bit-ADC design. The RP2040's ADC is 12-bit (read_u16() here returns
a 16-bit-scaled value, 0-65535) with different noise/timing characteristics
-- IR_SETTLE_US and TRIGGER_MARGIN both need fresh bench calibration.
"""

import time
from machine import ADC, Pin

IR_SAMPLE_INTERVAL_MS = 25
IR_SETTLE_US = 200          # retune on hardware -- see module docstring
IR_CALIBRATION_SAMPLES = 32
IR_TRIGGER_MARGIN = 2600    # placeholder: ~40 counts on a 10-bit ADC, scaled to read_u16()'s 16-bit range
IR_CONFIRM_SAMPLES = 3
IR_LOCKOUT_MS = 5000


class IRTrigger:
    def __init__(self, tx_pin, rx_adc_pin,
                 settle_us=IR_SETTLE_US,
                 margin=IR_TRIGGER_MARGIN,
                 confirm_samples=IR_CONFIRM_SAMPLES,
                 lockout_ms=IR_LOCKOUT_MS,
                 calibration_samples=IR_CALIBRATION_SAMPLES):
        self.tx = Pin(tx_pin, Pin.OUT)
        self.tx.value(0)
        self.rx = ADC(Pin(rx_adc_pin))

        self.settle_us = settle_us
        self.margin = margin
        self.confirm_samples = confirm_samples
        self.lockout_ms = lockout_ms
        self.calibration_samples = calibration_samples

        self.baseline = 0
        self.hits = 0
        self.last_delta = 0
        self.last_sample_ms = 0
        # Allow an immediate trigger right after boot (not blocked by lockout).
        self.last_trigger_ms = time.ticks_add(time.ticks_ms(), -lockout_ms)

    def _read_delta(self):
        self.tx.value(0)
        time.sleep_us(self.settle_us)
        dark = self.rx.read_u16()
        self.tx.value(1)
        time.sleep_us(self.settle_us)
        lit = self.rx.read_u16()
        self.tx.value(0)
        return lit - dark

    def calibrate(self):
        total = 0
        for _ in range(self.calibration_samples):
            total += self._read_delta()
        self.baseline = total // self.calibration_samples
        self.hits = 0
        return self.baseline

    def poll(self, now_ms):
        """Call at most every IR_SAMPLE_INTERVAL_MS; skip entirely while the
        bell is ringing (a sample blocks for ~2*settle_us). Returns True
        exactly once, the instant a trigger fires (after confirm+lockout)."""
        if time.ticks_diff(now_ms, self.last_sample_ms) < IR_SAMPLE_INTERVAL_MS:
            return False
        self.last_sample_ms = now_ms
        self.last_delta = self._read_delta()

        if self.last_delta > self.baseline + self.margin:
            if self.hits < self.confirm_samples:
                self.hits += 1
        else:
            self.hits = 0

        if self.hits >= self.confirm_samples and \
                time.ticks_diff(now_ms, self.last_trigger_ms) >= self.lockout_ms:
            self.last_trigger_ms = now_ms
            self.hits = 0
            return True
        return False

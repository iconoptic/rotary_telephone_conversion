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

GEMINI REV N REVIEW AUDIT (2026-08-02, see
docs/revN_design_review/01_gemini_deep_research_audit.md, findings C12/C13):
- 3-POINT SAMPLING: a plain dark/lit pair is vulnerable to 100/120Hz mains
  lighting flicker -- the ambient level can shift measurably between the
  two samples, leaking a false differential. _read_delta() now samples
  dark/lit/dark and subtracts the AVERAGE of the two dark samples from lit,
  cancelling any linear drift across the ~2*settle_us window.
- PAD DRIVE STRENGTH: the RP2040 defaults every GPIO pad to a 4mA drive
  (PADS_BANK0 reset value 0x56 -> DRIVE=01). At 3.3V through R10 150ohm the
  IR emitter LED wants ~14mA, well above that -- the pad's output voltage
  sags and the LED is under-driven. MicroPython's rp2 port does NOT expose
  Pin(..., drive=...) (verified against the machine.Pin docs -- that kwarg
  is cc3200/psoc-edge only), so the fix pokes the PADS_BANK0 register
  directly via machine.mem32 to raise TX_PIN to the 12mA setting.
"""

import time
import machine
from machine import ADC, Pin

# RP2040 PADS_BANK0: base 0x4001c000, GPIOn control register at +0x04+4*n;
# bits [5:4] select drive strength (00=2mA 01=4mA 10=8mA 11=12mA). See
# RP2040 datasheet 2.19.6. Read-modify-write (not an atomic alias) since
# this only ever runs once at init, before any interrupts are attached.
_PADS_BANK0_BASE = 0x4001c000
_PAD_DRIVE_MASK = 0b110000
_PAD_DRIVE_12MA = 0b110000


def _set_pad_drive_12ma(gpio):
    addr = _PADS_BANK0_BASE + 0x04 + 4 * gpio
    val = machine.mem32[addr]
    machine.mem32[addr] = (val & ~_PAD_DRIVE_MASK) | _PAD_DRIVE_12MA

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
        _set_pad_drive_12ma(tx_pin)
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
        """3-point dark/lit/dark sample -- see module docstring (finding C13):
        subtracting the average of two dark samples straddling the lit
        sample cancels linear ambient drift (e.g. 100/120Hz mains flicker)
        that a plain 2-point dark/lit pair would leak into the delta."""
        self.tx.value(0)
        time.sleep_us(self.settle_us)
        dark1 = self.rx.read_u16()
        self.tx.value(1)
        time.sleep_us(self.settle_us)
        lit = self.rx.read_u16()
        self.tx.value(0)
        time.sleep_us(self.settle_us)
        dark2 = self.rx.read_u16()
        return lit - (dark1 + dark2) // 2

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

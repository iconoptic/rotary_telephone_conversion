"""
Phase 1 -- carbon mic front-end bring-up + meter (vintage rotary headset).

STANDALONE diagnostic. It does NOT initialise USB HID and does NOT import the
dial decoder, so the running main.py dial->HID volume path is unaffected -- this
just reads the ADC and prints over the serial REPL. Run it by hand while you
bring up the RED/BLACK carbon-mic front end:

    # live meter (Ctrl-C to stop):
    mpremote connect /dev/ttyACM0 run mic_meter.py

    # one-shot DC bias check (confirm the divider centers ADC0 near 1.65 V):
    mpremote connect /dev/ttyACM0 exec "import mic_meter as m; m.calibrate(500)"

    # capture a 2 s raw snippet to the Pico flash, then pull it off and play:
    mpremote connect /dev/ttyACM0 exec "import mic_meter as m; m.record(2, 'mic.raw')"
    mpremote connect /dev/ttyACM0 fs cp :mic.raw mic.raw
    sox -t raw -r 8000 -e signed -b 16 -c 1 -L mic.raw out.wav && play out.wav
    # or: aplay -r 8000 -f S16_LE -c 1 mic.raw

Hardware (revF, RED/BLACK carbon mic front end -> GP26/ADC0 = physical pin 31):
  3V3 -> 220-330ohm bias -> carbon mic -> GND; mic junction AC-coupled through
  1-10uF into a 4.7k + 10nF low-pass (~3.4 kHz), with a 2x100k divider biasing
  ADC0 to ~1.65 V (mid-scale). Silence should read ~32768 counts / ~1.65 V;
  speech swings above and below that. Carbon mics are LOUD -- if RMS pins near
  full scale, increase attenuation (the plan expects trimming, not adding gain).

Meter columns:
  mid  = DC midpoint (should sit near 1.65 V once biased)
  rms  = AC RMS of the block (the "loudness")
  pkpk = peak-to-peak swing this block
shown in ADC counts (0-65535) and volts, plus a text bar of RMS.
"""

import time
import math
from machine import ADC, Pin

ADC_GP = 26                          # GP26 = ADC0 = physical pin 31
SAMPLE_RATE = 8000                   # Hz, telephone band
_PERIOD_US = 1000000 // SAMPLE_RATE  # 125 us
_VREF = 3.3
_FS = 65535                          # read_u16() full scale

_adc = ADC(Pin(ADC_GP))


def _counts_to_v(counts):
    return counts * _VREF / _FS


def _sample_block(n):
    """Sample n points at ~SAMPLE_RATE. Single pass, no per-sample allocation.
    Returns (mean, rms_ac, pkpk) in ADC counts."""
    sum_x = 0
    sum_x2 = 0
    vmin = 65535
    vmax = 0
    next_t = time.ticks_us()
    for _ in range(n):
        s = _adc.read_u16()
        sum_x += s
        sum_x2 += s * s
        if s < vmin:
            vmin = s
        if s > vmax:
            vmax = s
        next_t = time.ticks_add(next_t, _PERIOD_US)
        d = time.ticks_diff(next_t, time.ticks_us())
        if d > 0:
            time.sleep_us(d)
    mean = sum_x / n
    var = sum_x2 / n - mean * mean       # E[x^2] - E[x]^2
    if var < 0:                          # rounding guard
        var = 0.0
    return mean, math.sqrt(var), (vmax - vmin)


def calibrate(ms=500):
    """Print the DC bias point. Use this to confirm the 2x100k divider centers
    ADC0 near 1.65 V BEFORE worrying about audio levels."""
    n = max(1, SAMPLE_RATE * ms // 1000)
    mean, rms, pkpk = _sample_block(n)
    print("calibrate: mid={:.0f} cts ({:.3f} V)  noise_rms={:.1f} cts  pkpk={} cts".format(
        mean, _counts_to_v(mean), rms, pkpk))
    if not (0.30 * _FS < mean < 0.70 * _FS):
        print("  WARNING: midpoint far from mid-scale (~32768 / 1.65 V). Check the "
              "2x100k bias divider and AC-couple before trusting audio levels.")
    return mean, rms, pkpk


def _bar(rms, full=8000, width=40):
    n = int(min(1.0, rms / full) * width)
    return "#" * n + "-" * (width - n)


def meter(block_ms=120):
    """Continuous mic meter until Ctrl-C."""
    n = max(1, SAMPLE_RATE * block_ms // 1000)
    print("mic meter @ {} Hz, block {} ms ({} samples). Ctrl-C to stop.".format(
        SAMPLE_RATE, block_ms, n))
    print("bar full-scale = rms 8000 cts; carbon mics are loud, expect to attenuate.")
    try:
        while True:
            mean, rms, pkpk = _sample_block(n)
            print("mid {:5.0f} ({:.2f}V)  rms {:6.1f} ({:.3f}V)  pkpk {:5d}  |{}|".format(
                mean, _counts_to_v(mean), rms, _counts_to_v(rms), pkpk, _bar(rms)))
    except KeyboardInterrupt:
        print("stopped.")


def record(seconds=2, path="mic.raw"):
    """Capture `seconds` of audio at SAMPLE_RATE to `path` on the Pico flash as
    signed 16-bit little-endian with mid-scale removed (directly playable).
    Samples are buffered in RAM first so flash writes never disturb the timing."""
    n = int(SAMPLE_RATE * seconds)
    print("recording {} s ({} samples) at {} Hz...".format(seconds, n, SAMPLE_RATE))
    raw = bytearray(n * 2)
    j = 0
    next_t = time.ticks_us()
    for _ in range(n):
        s = _adc.read_u16() - 32768      # unsigned mid-scale -> signed
        if s < -32768:
            s = -32768
        elif s > 32767:
            s = 32767
        s &= 0xFFFF                       # two's-complement for byte split
        raw[j] = s & 0xFF                 # little-endian: low byte first
        raw[j + 1] = (s >> 8) & 0xFF
        j += 2
        next_t = time.ticks_add(next_t, _PERIOD_US)
        d = time.ticks_diff(next_t, time.ticks_us())
        if d > 0:
            time.sleep_us(d)
    with open(path, "wb") as f:
        f.write(raw)
    print("wrote {} ({} bytes). Pull it off and play with:".format(path, len(raw)))
    print("  mpremote fs cp :{} {}".format(path, path))
    print("  sox -t raw -r {} -e signed -b 16 -c 1 -L {} out.wav && play out.wav".format(
        SAMPLE_RATE, path))


if __name__ == "__main__":
    calibrate()
    meter()

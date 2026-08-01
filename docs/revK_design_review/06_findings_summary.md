# 06 — All findings, ranked

> One row per finding. 🔴 = fix before/at first power-up · 🟡 = fix or
> consciously accept · 🟢 = documented, no action needed.

> **Status update (2026-08-01):** findings **1, 2, 3, 6** are now fixed in
> firmware ([rotary_volume.ino](../../firmware/rotary_volume/rotary_volume.ino),
> [bell_ir_test.ino](../../firmware/bell_ir_test/bell_ir_test.ino)); both
> sketches recompiled clean. The schematic gained a documentation-only note
> for finding 7 (avalanche/no-snubber dependency). See
> [07_gemini_review_audit.md](07_gemini_review_audit.md) for a second-opinion
> adversarial pass that checked this review's own claims and caught one real
> physics error (§5 below / finding 15).

---

## 🔴 Significant (2) — ✅ both fixed 2026-08-01

| # | Finding | Where | One-line fix | Status | Detail |
|---|---------|-------|--------------|--------|--------|
| 1 | `'a'`/`'b'` DC test holds 5 V across ~2 Ω of winding DCR for **1 s** → ~2.5 A rail short, brownout/polyfuse trip | `bell_ir_test.ino` | Delete the test (the DMM check already covers it) or cap at 10 ms | ✅ shortened to 10 ms | [03 §1](03_bell_failure_modes.md) |
| 2 | Start-up **flux doubling**: first full-length half-cycle drives the core to ~1.86× rated flux → amp-class spike + possible brownout at *every* ring start | `bellUpdate()` / `oscillate()` | Make the first half-cycle after idle **10 ms** (half-length) — classic push-pull soft-start | ✅ implemented in both sketches | [03 §2](03_bell_failure_modes.md) |

## 🟡 Medium (4) — 2 fixed, 2 remain bench-only

| # | Finding | Where | One-line fix | Status | Detail |
|---|---------|-------|--------------|--------|--------|
| 3 | Frequency tuner allows 15 Hz; saturation floor for this core is **23 Hz** | `setRingFreq()` clamp | Change floor 15 → 23 | ✅ fixed | [03 §3](03_bell_failure_modes.md) |
| 4 | USB budget: ring burst + Logitech + MCU ≈ 450–550 mA on a single bus-powered 500 mA allocation | System power | Self-powered hub (already recommended — treat as **required**) | ⬜ hardware-only, unchanged | [03 §4](03_bell_failure_modes.md) |
| 5 | `IR_SETTLE_US = 200` is marginal vs. phototransistor speed with a 10 kΩ load (~50–150 µs typical, worse when dim) — attenuates delta/SNR, silently | `irReadDelta()` | Bench experiment: try 1000 µs, compare deltas, keep 2–3× the knee | ⬜ needs real hardware to tune, left as-is | [04 §4](04_ir_trigger.md) |
| 6 | Firmware hang with a bell gate latched HIGH = the DC-test scenario; R14/R15 only cover reset/Hi-Z, not a live-but-stuck pin | `rotary_volume.ino` | `wdt_enable(WDTO_250MS)` + `wdt_reset()` in loop | ✅ added (with the Caterina-bootloader-safe `.init3` MCUSR-clear guard) | [03 fault matrix](03_bell_failure_modes.md) |

## 🟢 Noted / no action (8)

| # | Finding | Verdict |
|---|---------|---------|
| 7 | No snubber on Q2/Q3 — leakage spikes absorbed by avalanche rating (µJ vs 100s of mJ: ~4 orders of margin) | Fine for this duty cycle; **dependency now documented directly on the schematic** — substitutes must be avalanche-rated, ≥60 V (see also finding 15 in [07](07_gemini_review_audit.md) for the repetitive-avalanche nuance) |
| 8 | Flux walking from `millis()` jitter (~±1 ms on 20 ms half-cycles) | Bounded to ~60 mA DC offset by winding DCR; self-limiting |
| 9 | Bell current will be ~13 mA, not 15.5 mA (copper losses ~16%, plus coil inductance above its 5.97 kΩ DCR) | Loudness estimate, not a fault; judge by ear |
| 10 | C7/C8 = 940 µF exceeds USB 2.0's 10 µF hot-plug inrush allowance | Compliance nit; universally tolerated; moot with self-powered hub |
| 11 | Fluorescent office ambient | **Favorable**: fluorescents are IR-quiet; 100/120 Hz ripple lands under the margin; 20–60 kHz electronic-ballast ripple averages out. Shroud Q4 from direct fixture line-of-sight |
| 12 | IR LED true current ~20 mA, not the labeled ~24 mA (AVR pin impedance) | Slightly less optical power than the label implies; harmless |
| 13 | IR baseline is boot-time-only; drifts with temp/dust | `c` recal exists; if auto-recal is added, never recal while triggered |
| 14 | Shorted bell wiring during ring → ~1.7 A rail drag, no dedicated protection | Low probability; polyfuse/brownout is the backstop; insulate well |

---

## ✅ Green lights — things that *look* wrong but were checked and are right

Deliberately listed so future-you doesn't "fix" them:

1. **T1's HV side has no capacitor.** Correct — a cap there would resonate
   with the bell coil and need a >200 V rating. Bulk caps belong on the LV
   tap, where they are.
2. **The FETs are "oversized" (60 V/35 A for a 10 V/300 mA job).** Correct —
   the 60 V covers 2×Vin plus unclamped leakage ringing, and the avalanche
   rating *is* the snubber (finding 7). IRFZ44N at 55 V/non-logic-level was
   rightly rejected.
3. **R18 "only" 0.25 W.** Correct — 53 mW actual, 4.7× margin. The earlier
   1 W spec was the error.
4. **Flyback diodes appear to be "missing" on T1.** Correct — the push-pull
   topology self-clamps magnetizing energy through the opposite FET's body
   diode into the rail ([02 §6](02_bell_ring_generator.md)).
5. **The bell gets a square wave, not a sine.** Correct — the fundamental of
   ±96 V square ≈ 86 V RMS at 25 Hz, essentially the original spec; the bell's
   mechanical resonance ignores the harmonics.
6. **R3 pull-up is external while the others are internal.** Correct — only
   N1 has the 14.5 kΩ bleeder divider to fight
   ([05 §1](05_dial_hook_leds.md)).
7. **25 Hz instead of the "authentic" 20 Hz.** Correct — 20 Hz would run the
   core at 1.16× rated flux; 25 Hz was a real exchange frequency anyway
   ([02 §4](02_bell_ring_generator.md)).
8. **GREY bell leads left unconnected.** Correct — likely a coil tap;
   bonding them could short part of the winding.
9. **1 ms deadband at 25 Hz.** Correct — 5% of a half-cycle, prevents
   shoot-through by construction, and the body diodes carry the interval.
10. **Polled firmware, no interrupts.** Correct — ~38× oversampling of the
    fastest input edge, less RAM/race complexity
    ([05 §4](05_dial_hook_leds.md)).

---

## 🔬 Pre-power-up bench checklist (condensed from findings)

1. DMM before wiring: R(5-8) ≈ 2× R(5-6) on T1; series-aiding check on the
   HV side (phasing trap, [02 §3](02_bell_ring_generator.md)).
2. ~~Apply firmware fixes for findings 1, 2, 3 first~~ — done 2026-08-01,
   both sketches recompile clean (9060/28672 B and 6116/28672 B).
3. First power: bell **disconnected**, scope on T1 secondary → expect
   ~±96 V/190 Vpp square at 25 Hz; scope a drain → expect ~10 V flat top +
   brief leakage spike ≪ 60 V.
4. Watch the 5 V rail during a ring start — sag should stay above the AVR
   brownout with the soft-start fix in place.
5. Connect the bell, ring, tune loudness expectations to ~13 mA reality.
6. IR: run the settle-time experiment ([04 §4](04_ir_trigger.md)),
   *then* tune `IR_TRIGGER_MARGIN` from live deltas.

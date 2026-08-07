# Rev N -- Gemini deep-research review: audit + integration (2026-08-02)

Audit of the Gemini Pro deep-research review commissioned via
`gemini_revN_review/00_RESEARCH_PROMPT.md`. Every load-bearing claim was
re-derived or checked against primary sources before anything was changed.
Convention follows `docs/revK_design_review/07_gemini_review_audit.md`: trust
nothing, grade everything.

Sources checked directly this session:
- MicroPython docs, `machine.WDT`: RP2040 max timeout **8388 ms**; once
  started the WDT **cannot be stopped or reconfigured**.
- MicroPython docs, `machine.Pin`: the `drive=` parameter / `Pin.drive()`
  is **NOT implemented on the rp2 port** (cc3200/psoc-edge only) -- the GP19
  drive-strength fix must poke `PADS_BANK0` directly.
- Our own firmware (main.py / bell.py / ir_trigger.py / bell_ir_test.py)
  for the claims about deadband, IRQ queue, and missing WDT.
- Arithmetic re-derived by hand for every numeric finding below.

## Verdict summary

| # | Gemini finding | Verdict | Action |
|---|---|---|---|
| A1 | Gate divider ~4.50V; marginal but sufficient at <=150mA | **VALID** (5*10k/11.1k = 4.504V) | None |
| A2 | Turn-on ~4.4us via Rc, turn-off ~150ns via NPN; no shoot-through vs 1ms deadband | **VALID** (order-of-magnitude sound) | None |
| A3 | Forced beta ~1.65, storage <=~1us, negligible | **VALID** (2N3904 ts max 200ns spec basis) | None |
| A4 | RP2040 pads default to input + pull-down (PADS_BANK0 reset 0x56); boot-safety survives -- Rbp injects ~0.42mA base current even against the internal pull-down | **VALID** -- and it *strengthens* the design claim (pin never truly floats) | None |
| A5 | Rb/Rbp/Rc values appropriate; GPIO sinks only ~0.45mA | **VALID** | None |
| A6 | Totem-pole unnecessary at 30Hz; direct 2N3904 common-emitter drive prohibited (200mA Ic limit) | **VALID** | None |
| B7 | 30Hz = 92.5% rated flux, 28Hz = 99.1%; soft-start halving is imperative | **VALID** (matches bell.py's 333/(hz*12)) | **Floor raised 28->30Hz**: at VBUS worst case 5.25V, 28Hz gives 0.991*1.05 ~= **1.04x rated flux** -- saturating. Gemini's own thinking stream flagged this but its final text kept 28Hz. |
| B8 | Snubber: E=0.056uJ, dV~=3.3V, drain ~=13.3V, "40V of margin" | **ARITHMETIC ERROR -- CONCLUSION INVERTED.** 1/2*5mH*(0.15A)^2 = **56.25uJ = 0.056mJ**, a 1000x slip. sqrt(2*56.25uJ/10nF) ~= **106V**, not 3.3V. Also zeta = R/2Z0 = 100/(2*707) ~= 0.07 -- underdamped. With 10nF the drain rings far past 55V and Q2/Q3 **avalanche every turn-off** (survivable: 56uJ << EAR 9.4mJ -- Rev M's declared backstop -- but the "snubbed below 55V" story was false). Gemini's own thinking stream said ">110V spikes"; its final report contradicted itself. | **C9/C10: 10nF -> 100nF (>=100V)**. sqrt(2*56.25uJ/100nF) ~= 33.5V -> drain ~= 43V worst-case; Z0 = sqrt(5mH/100nF) = 224ohm so R=100ohm now damps properly (zeta ~= 0.22). At L_lk=1mH: ~=25V. Dissipation ~= C*V^2*f ~= 0.6mW. **L_lk 1-5mH is an assumption -- bench-measure and scope the drain at first power, bell disconnected.** |
| B9 | 940uF violates USB 2.0 s7.2.4.1 10uF hot-plug limit; self-powered hub mandatory | **VALID in substance, overstated in tone** ("guarantees" failure -- real ports often survive via cable ESR + OCP soft-start; but it IS a ~94x compliance violation) | Self-powered hub **elevated from "prefer" to REQUIRED** on the schematic |
| B10 | ~46.4V RMS, ~7.3mA into the ringer; rings but acoustically soft | **PLAUSIBLE** -- math checks (47.9V*sqrt(0.94)); the "Bell System Practices C4A 40-50V/10-15mA" citation could not be verified -- treat as folklore. Matches Rev L's own "softer than spec" expectation. | None (accepted trade-off; 160G24/VPL24-210 remain the upgrade path) |
| C11 | Emitter follower OK at 3V3; RP2040 ADC ENOB ~8.7 bits (DNL erratum) | **VALID** (ENOB figure matches RP2040 datasheet s4.9.3) | None -- synchronous differencing already absorbs static offset |
| C12 | GP19 default 4mA pad drive starves the IR LED (~6-8mA vs 14mA design); set 12mA in firmware | **VALID and important.** Correction to Gemini: MicroPython rp2 does NOT support Pin(drive=) -- verified in docs. Fix must write PADS_BANK0 GPIO19 DRIVE bits [5:4]=0b11 via machine.mem32. | **Done in ir_trigger.py** (atomic set-alias write) |
| C13 | 2-point sampling leaks 120Hz flicker slope; use dark-lit-dark 3-point | **VALID** -- standard linear-drift cancellation | **Done**: _read_delta now returns lit - (dark1+dark2)//2; bell_ir_test.ir_sample matches |
| D14 | No WDT; crash mid-ring latches FET ON -> ~2.5A DC in T1 (~12.5W) | **VALID** -- flagged in our own prompt (Q14); Gemini confirmed and quantified. | **Done, with a workflow-critical amendment**: the WDT can never be stopped once armed (docs) and survives soft reset -- arming at boot would kill every long mpremote fs cp. main.py arms it **lazily, on first bell activation** (timeout 5000ms -- <=60J into T1 worst case, thermally trivial for a 10VA transformer), feeds every loop pass. PLUS try/finally gates-off around the main loop for instant safing on Python-level exceptions. Gemini's proposed WDT(timeout=250) at boot would have wrecked the mpremote deployment workflow it knew nothing about. |
| D15 | GC pauses 1-4ms can stretch a half-cycle into the saturation zone; collect only while idle | **VALID in direction** (pause magnitude plausible, not measured) | **Done**: idle-only gc.collect() every 5s in main.py. Also mitigated by the 30Hz floor and by half_period_ms = 500//30 = 16ms (integer division already runs the bell at ~31.25Hz effective -- slightly MORE margin than nominal). |
| D16 | Ring buffer single-producer-safe under MicroPython soft-IRQ sequential dispatch; 15ms debounce fine for 10pps | **VALID** -- our Pin.irq uses default hard=False (scheduled, sequential); 15/30ms debounce sits inside the ~33/66ms make/break budget | None |
| D17 | Second usb.device.init() while host mid-transaction can wedge the USB peripheral | **VALID -- already documented** in repo memory (kernel error -110, needs physical replug) | None (known operational hazard) |
| E18 | FMEA: reversed C7/C8 and gate-short faults NOT contained; brownout IS contained by the level shifter | **VALID** -- the brownout row is a genuinely useful observation (pads revert to pull-down -> NPN on -> FET off) | DMM polarity/wiring check already mandatory in the bench plan |

## Changes applied (all deployed to the Pico)

1. **bell.py** -- `MIN_RING_FREQ_HZ` 28 -> 30 (worst-case VBUS 5.25V pushes 28Hz to ~1.04x rated flux; GC jitter erodes the same margin).
2. **ir_trigger.py** -- 3-point ambient-rejection sampling; GP19 pad drive forced to 12mA via PADS_BANK0 atomic set (`mem32`), since rp2 MicroPython has no `Pin(drive=)`.
3. **main.py** -- lazily-armed `machine.WDT(timeout=5000)` on first bell activation + feed every loop pass; `try/finally` forcing gates off; idle-only periodic `gc.collect()`.
4. **bell_ir_test.py** -- `hold(seconds=...)` now bounded (a dropped mpremote session can no longer leave the bell ringing forever); `ring()`/`hold()` safe the gates in `finally`; `ir_sample()` prints the 3-point values.
5. **Schematic (rotary_dial_circuit_revN.svg)** -- C9/C10 10nF -> **100nF >=100V** with corrected math noted; self-powered hub **REQUIRED**; audit-delta lines added to the Rev N summary box.

## Still open (bench, cannot be resolved on paper)

- Measure T1's real leakage inductance (short the HV winding, measure L at
  a half-winding) -- the 100nF sizing assumes 1-5mH.
- Scope the Q2/Q3 drain at first power (bell disconnected) and confirm the
  peak stays comfortably under 55V.
- Scope the GATE_A/GATE_B nodes to confirm the ~4.5V ON level and the
  microsecond-scale edges the level-shifter math predicts.
- Re-tune IR_SETTLE_US / IR_TRIGGER_MARGIN with the 12mA drive under real
  room lighting (constants remain placeholders).

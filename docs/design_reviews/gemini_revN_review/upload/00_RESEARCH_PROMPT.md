# Deep research request: adversarial academic review of "Rev N" — a 3.3V-logic bell ring generator, IR trigger, and rotary-dial USB HID interface

## Your role

Act as a panel of three adversarial reviewers preparing a formal design review:

1. A **power-electronics academic** (magnetics, switching converters, device physics) reviewing the transformer push-pull driver, MOSFET gate drive, and snubber design against datasheets and first principles.
2. A **senior embedded-systems engineer** (RP2040/MicroPython, real-time firmware, USB) reviewing the firmware for timing hazards, failure modes, and safety interlocks.
3. A **safety/reliability engineer** performing an FMEA-style pass, with special attention to the documented failure of the previous build (details below).

Your job is to find what is **wrong, marginal, or unproven** — not to summarize what is right. Every prior review of this project has found real, load-bearing errors (see `07_gemini_review_audit.md` for how a previous Gemini review fared: some findings were valid and fixed, others were confidently wrong). Expect your claims to be audited the same way: **show your arithmetic, cite datasheet figures by number/page, and clearly separate "calculated" from "assumed."**

## Project context (60 seconds)

A hobbyist is converting a vintage rotary telephone into a USB headset/volume controller. A Raspberry Pi Pico (RP2040, MicroPython, 3.3V logic) decodes the rotary dial and switchhook, sends absolute volume (0–100%) over a vendor-defined USB HID report, and — new since "Rev J" — rings the phone's original electromechanical bell (polarized ringer, 5.97kΩ DC coil resistance, originally ~90V/20Hz) via a push-pull step-up driver, triggered by an IR proximity sensor.

**Critical history:** the previous MCU (Adafruit ItsyBitsy 32u4, 5V logic) **failed destructively during bell driver bring-up** — it overheated and permanently stopped enumerating over USB. Root cause was never conclusively diagnosed. Leading suspects: reversed polarity on the C7/C8 bulk electrolytics, or the D2/D3 gate-drive pins being shorted/driven past their series resistors. Rev N is the redesign onto the 3.3V Pico, and **it has not been built or powered yet.** Your review is the last gate before physical construction.

## The design under review (Rev N deltas — focus here)

Full schematic: `rotary_dial_circuit_revN.svg.txt` (SVG source, readable as text) and `rotary_dial_circuit_revN.png` (rendered). Prior revision for diff context: `rotary_dial_circuit_revM.svg.txt`.

1. **Bell driver (carried over from Rev M):** Q2/Q3 = IRFZ44N (55V, NOT logic-level, Vgs(th) 2–4V) alternately ground the two halves of T1's centre-tapped LV winding; centre tap on USB VBUS 5V through C7/C8 (2×470µF/16V). T1 = Hammond 161G24 mains transformer run backwards (24V CT secondary as 12-0-12 primary, single 115V winding as secondary, ~9.6:1, 60Hz-only core), giving ~±48V at ~7–8mA into the bell through R18 220Ω. RC snubbers R16/R17 (100Ω) + C9/C10 (10nF) across each half-winding. Ring frequency 30Hz (clamp 28–40Hz), 1ms deadband, half-length first half-cycle soft-start, 2s burst / 4s gap / 2 bursts.
2. **NEW — Q5/Q6 NPN gate-drive level shifters:** because 3.3V GPIO cannot reliably enhance an IRFZ44N (Vgs(th) max 4V), each gate is driven by an inverting open-collector stage: GPIO →Rb 1kΩ→ NPN base ←Rbp 10kΩ← 5V; emitter→GND; collector ←Rc 1kΩ← 5V, output into the existing R12/R13 100Ω gate series resistors, with R14/R15 10kΩ gate pulldowns still fitted. Claimed ON-state gate voltage ≈ 5V·10k/11.1k ≈ 4.5V. Claimed boot-safety: a floating GPIO ⇒ base pulled up ⇒ NPN ON ⇒ FET OFF. Firmware consequently drives BELL_A/BELL_B **active-low**. Proposed parts: 2N3904 or equivalent. **All resistor values are unverified starting points.**
3. **NEW — IR receiver moved to 3V3:** the bare-phototransistor emitter follower (Q4, load R11 10kΩ into the ADC) previously ran its collector from 5V; Rev N moves it to 3V3 because GP26/ADC0 is not 5V-tolerant. The IR emitter LED (R10 150Ω from GPIO) now runs from a 3.3V pin, dropping drive from ~24mA to ~12–14mA. Ambient rejection is synchronous sampling in software (ADC read with emitter off, then on, subtract); trigger = delta above a boot-time-calibrated crosstalk baseline.
4. **Firmware (MicroPython, all files included):** `main.py` (IRQ-driven dial/hook with ring-buffer event queue, `bell.update(now)` serviced every main-loop pass with **no sleep**, HID volume reports), `bell.py` (ring state machine), `ir_trigger.py`, `hid_consumer.py`, plus `bell_ir_test.py` (standalone bring-up tool).

## Specific questions you must answer (with numbers)

### A. Gate-drive level shifter (highest priority — this is the newest, least-reviewed circuit)

1. Verify the ON-state gate voltage divider claim (Rc 1k + R12 100Ω source vs R14/R15 10k pulldown). Is ≈4.5V correct, and is 4.5V sufficient to fully enhance a **worst-case** (Vgs(th)=4V at 25°C) IRFZ44N at the ~75–150mA drain currents involved? Use the IRFZ44N datasheet transfer/output characteristics, and consider Vgs(th) temperature coefficient over 0–50°C ambient.
2. Turn-on is via Rc 1kΩ charging the FET's Ciss (+Miller charge as the drain swings ~10V); turn-off is via the saturated NPN. Compute both transition times. Does the asymmetry (slow ON, fast OFF) create any shoot-through window given the firmware's 1ms deadband, or is it inherently safe?
3. The NPN runs at forced β≈2 (≈2.6–3mA base, ≈5mA collector) — deeply saturated. Compute the storage/turn-off delay and confirm it is negligible vs the deadband.
4. **RP2040 boot/reset pad states:** verify from the RP2040 datasheet what GP17/GP18 actually do during (a) power-up before firmware runs, (b) BOOTSEL/UF2 mode, (c) a MicroPython soft reset, (d) a firmware crash with pins configured as outputs. Does the claimed boot-safety (Rbp pull-up wins when the pin floats) hold in ALL of these states, including against the RP2040's internal pull resistors if any default on?
5. Are the proposed values (Rb 1k, Rbp 10k, Rc 1k) sensible, or would you change them? Justify with the GPIO sink-current budget, NPN dissipation, and gate-transition-speed tradeoffs.
6. Is there a simpler or strictly better on-hand-parts topology (e.g., NPN + PNP totem, or the NPN driving the gate directly as a common-emitter with the FET reconfigured) that the designers should consider before building? Parts on hand: small-signal NPNs (2N3904-class), IRFZ44Ns, ordinary resistors. Buying logic-level FETs was explicitly rejected by the owner.

### B. Bell driver / magnetics (verify the carried-over math survives the 3.3V port)

7. Verify the core-saturation argument: 5V square drive across a 12V/60Hz half-winding at 30Hz, including the half-length soft-start first half-cycle from zero flux. Is the 28Hz floor genuinely safe? (The design's own flux-ratio formula is in `bell.py` and `transformer_primer.md` — check it, don't trust it.)
8. Verify the snubber sizing (100Ω + 10nF across each half-winding) against a plausible leakage-inductance estimate for a 161G24-class transformer, and that the peak drain voltage stays under the IRFZ44N's 55V rating with margin. Is drain-to-centre-tap the right snubber placement vs drain-to-ground RCD alternatives?
9. Power budget: ring bursts (~75mA claim at 5V), Pico (~25–50mA), through a USB 2.0 hub. Check the ~940µF bulk capacitance against USB inrush-current limits at plug-in, and whether a bus-powered hub is acceptable or a self-powered hub should be mandatory.
10. Given the ~2× dead time in each half-cycle and the actual drive waveform (active-low, deadband, soft-start), estimate the real secondary voltage/current into the 5.97kΩ + R18 220Ω load, and comment on whether it will audibly ring a ~90V/20Hz-spec polarized ringer. Cite any literature on minimum ring voltage for AE/WE-style polarized ringers if findable.

### C. IR trigger at 3.3V

11. With the phototransistor collector on 3V3 and a 10k emitter load into the RP2040 ADC (nominally 12-bit, known ENOB/DNL erratum — cite RP2040 datasheet section 4.9 and errata), what is the usable signal range and headroom? Is the emitter-follower topology still appropriate, or should it become a common-emitter/transimpedance arrangement at 3.3V?
12. The GPIO drives the IR LED through 150Ω: (3.3−1.2)/150 ≈ 14mA, but RP2040 pad drive strength maxes at 12mA (configurable, default 4mA). What actually happens — how much current really flows at the default drive strength, is the pad at risk, and should R10 change or the pad drive strength be raised in firmware?
13. Review the synchronous-sampling scheme (settle time 200µs placeholder, 32-sample calibration, margin/confirm/lockout constants in `ir_trigger.py`) for susceptibility to 100/120Hz mains flicker from LED room lighting and PWM-dimmed lamps. Suggest a concrete sampling schedule that rejects these, if the current one doesn't.

### D. Firmware and system safety

14. **Watchdog gap:** the failed ItsyBitsy build added an AVR watchdog (250ms) specifically so a firmware hang could never leave a bell gate latched on. Audit whether the Rev N MicroPython firmware has an equivalent (`machine.WDT`?), and analyze the consequence of a hang or unhandled exception mid-ring **given the new active-low drive**: which state do the gates latch in, what does a latched-ON FET do to T1 (DC across a half-winding) and to VBUS, and what interlock(s) would you require before first power-on?
15. Review `bell.py`'s state machine for correctness: deadband actually enforced across ALL transitions (including stop(), burst→gap, and hold-mode), tick-wraparound safety, and behavior if `update()` is starved for tens of ms (e.g., by a long garbage-collection pause in MicroPython — quantify plausible GC pause times on RP2040 and their effect on the 16.7ms half-cycles).
16. Review `main.py`'s IRQ ring buffer (single producer per pin, single consumer) for race conditions under MicroPython's IRQ semantics, and the dial-decoding debounce constants (15ms dial, 30ms hook) against standard rotary-dial pulse timing (10 pps, ~60/40 make/break).
17. Anything about the USB composite device (CDC + vendor HID, 1-byte report, VID:PID 2e8a:0005) that is fragile or non-compliant.

### E. Failure-mode analysis

18. FMEA table for the bell subsystem: for each plausible single fault (each solder/wiring error class, each component failure mode, firmware hang, USB brownout mid-ring), state the immediate electrical consequence, worst-case dissipation, and whether the Rev N design contains it — explicitly including the two suspected ItsyBitsy killers (reversed C7/C8; gate pin shorted past its series resistor). Would either of those faults, repeated identically on this build, damage the Pico?
19. A prioritized "**must fix before first power-on**" list vs "fix eventually" vs "acceptable as-is."

## Ground rules

- Work from the attached datasheets (`infineon-irfz44n-datasheet-en.pdf`, Hammond 160/161 series PDF) and the official RP2040/Pico documentation; search for anything else you need (2N3904 datasheet, USB 2.0 inrush spec, MicroPython IRQ/GC documentation).
- The schematic SVG sources are authoritative for the circuit; the `.md` design-review files are prior analysis that you should **check, not inherit**. `copilot_rev_K_review.md` and the `0x_*.md` files document the previous review cycle and which of its findings were validated.
- Numeric claims in the attached files have been wrong before. Re-derive anything you rely on.
- Output: a structured report — executive summary, then findings numbered per the questions above, each with severity (BLOCKER / MAJOR / MINOR / INFO), your calculation, and citations. End with the prioritized fix list (question 19).

## File manifest

Ten attachments. The four `combined` text bundles concatenate several original files, each introduced by a `== FILE: <original name> ==` banner — treat each banner-delimited section as its own document.

| Attachment | Contents |
|---|---|
| `00_RESEARCH_PROMPT.md` | This document |
| `01_schematic_revN_render.png` | **The design under review**, rendered |
| `02_schematic_revN_source.svg.txt` | Rev N schematic SVG source (authoritative), incl. all revision-history summary boxes |
| `03_schematic_revM_source.svg.txt` | Previous revision (5V ItsyBitsy) for diffing |
| `04_firmware_micropython.txt` | All 5 MicroPython firmware files as deployed: `main.py`, `bell.py`, `ir_trigger.py`, `hid_consumer.py`, `bell_ir_test.py` |
| `05_design_docs.md` | `transformer_primer.md` (project's own transformer theory — check it), `pico_port_handoff_prompt.md` (port mandate + ItsyBitsy failure narrative), `bell_bench_test_setup.svg.txt` (planned bench bring-up, bell disconnected, TP-A/B/C test points) |
| `06_prior_review_part1.md` | Prior review cycle: `copilot_rev_K_review.md`, review README, `01_big_picture.md`, `07_gemini_review_audit.md` (accuracy audit of a previous Gemini review) |
| `07_prior_review_part2.md` | Prior review cycle, subsystem deep-dives: `02_bell_ring_generator.md`, `03_bell_failure_modes.md`, `04_ir_trigger.md`, `05_dial_hook_leds.md`, `06_findings_summary.md` |
| `08_datasheet_irfz44n.pdf` | Q2/Q3 datasheet |
| `09_datasheet_hammond_160_161.pdf` | T1 (Hammond 161G24) datasheet |

# Rev K design review — adversarial edition

> **Note (2026-08-01):** this review is of the Rev K schematic, which was
> designed around a Hammond 160G24 (dual-primary) transformer. The part
> actually on hand turned out to be the 161G24 (single-primary, 60Hz-only),
> which has different pin numbers (see `docs/rotary_dial_circuit_revL.svg`
> and the "T1 CHOICE" comment in `rotary_volume.ino`/`bell_ir_test.ino`).
> The analysis below (topology, failure modes, math) still applies — only
> pin numbers and the resulting voltage/current/frequency figures changed.

> **What this is:** an adversarial teardown of `rotary_dial_circuit_revK.svg`.
> Every design choice gets asked *"why is this right, and how could it fail?"* —
> with the math shown, so you can check the reviewer instead of trusting it.
>
> **What this is not:** a review of the Logitech USB audio integration
> (straightforward, excluded per request).

---

## 🗺️ Read in this order

| # | File | What it covers | Difficulty |
|---|------|----------------|------------|
| 1 | [01_big_picture.md](01_big_picture.md) | One-page mental model of the whole board | 🟢 easy |
| 2 | [02_bell_ring_generator.md](02_bell_ring_generator.md) | **The red box.** Push-pull transformer stage, piece by piece | 🔴 the hard one |
| 3 | [03_bell_failure_modes.md](03_bell_failure_modes.md) | Adversarial findings on the bell stage — what can bite | 🔴 the hard one, pt 2 |
| 4 | [04_ir_trigger.md](04_ir_trigger.md) | **The orange box.** IR proximity trigger, and why it's firmware-heavy | 🟡 medium |
| 5 | [05_dial_hook_leds.md](05_dial_hook_leds.md) | Input channels N1/N2/N3 + LEDs (the easy 60% of the schematic) | 🟢 easy |
| 6 | [06_findings_summary.md](06_findings_summary.md) | **Every finding, ranked.** Start here if you only read one file | ⚡ skim-friendly |
| 7 | [07_gemini_review_audit.md](07_gemini_review_audit.md) | A second AI reviewer's adversarial pass *on this review*, audited claim-by-claim | 🟡 medium |

---

## ⚡ 30-second verdict

> **Status (2026-08-01):** the 2 significant findings and 2 of the medium
> findings below are **fixed in firmware** (both sketches recompile clean).
> A second AI adversarial pass audited this review itself and found one
> real physics correction — see [07_gemini_review_audit.md](07_gemini_review_audit.md).

The design is **fundamentally sound** — the topology choices are the ones a
seasoned designer would make with these constraints (5 V only, parts on hand,
vintage load). But the adversarial pass found real items:

- 🔴 **2 significant findings, now fixed** — the `bell_ir_test.ino` `'a'`/`'b'`
  DC test used to short the 5 V rail through ~2 Ω for a full second (now
  10 ms), and push-pull **start-up flux doubling** used to saturate the core
  at the beginning of *every* ring burst (now soft-started with a
  half-length first half-cycle).
- 🟡 **Several medium findings** — the ring-frequency floor was raised
  15→23 Hz and an AVR watchdog was added (both fixed); bell current is
  overestimated (inductance ignored, informational only); no snubber on
  leakage-inductance spikes (saved by avalanche-rated FETs, dependency now
  noted directly on the schematic); IR settle time is marginal vs.
  phototransistor speed (needs real hardware to tune, left as-is).
- 🟢 **A pile of green-lights** — things that *look* wrong but are actually
  fine, documented so future-you doesn't "fix" them.

Details and receipts: [06_findings_summary.md](06_findings_summary.md).

---

## 📐 Conventions used in these docs

- **Numbers first.** Every claim gets arithmetic you can redo on paper.
- **⚠️ = adversarial finding** (something that could bite).
- **✅ = verified-fine** (looks scary, checked, actually OK).
- **📖 = background** (the EE-curriculum depth that CE breadth skipped).
- Component names (`Q2`, `R18`, `T1`…) match the Rev K schematic exactly.

## 🔗 Primary sources consulted

| Fact | Source |
|------|--------|
| STP55NF06L: 60 V, 0.014 Ω typ, logic-level, "100% avalanche tested" | [ST product page](https://www.st.com/en/power-transistors/stp55nf06l.html) |
| Hammond 160G24: dual 115/230 V primary, 10 VA, 24 V C.T. @ 450 mA | [Hammond part page](https://www.hammfg.com/part/160G24) |
| ItsyBitsy 32u4 5V: "5V" pin good for 500 mA when USB-powered | [Adafruit pinout guide](https://learn.adafruit.com/introducting-itsy-bitsy-32u4/pinouts) |
| Push-pull: deadtime/shoot-through, back-EMF peaks when both switches off | [Wikipedia: push–pull converter](https://en.wikipedia.org/wiki/Push%E2%80%93pull_converter) |
| Fluorescent flicker: magnetic ballast = 2× line freq; electronic = 20–60 kHz | [Wikipedia: flicker](https://en.wikipedia.org/wiki/Flicker_(light)), [fluorescent lamp](https://en.wikipedia.org/wiki/Fluorescent_lamp#Flicker_problems) |

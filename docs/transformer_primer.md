# Multi-Winding Mains Transformers — a refresher for the bell ringer

**Context:** picking T1 for the Rev J bell ring generator.
**Verdict:** Hammond **160G24**. Why, and how to read the sheet that says so.

> **UPDATE (2026-08-01, Rev L):** the part actually on hand turned out to be
> the **161G24** (single-primary, 60Hz-only), not the 160G24 this whole
> document argues for. Everything below is kept as-is because the reasoning
> (why a 24V C.T./10VA winding, the flux-vs-frequency math, why dual-primary
> is *better*) is still correct and still the reason to upgrade later — it
> just isn't what got built. With the 161G24: ratio is 115:12 = 9.6:1 (not
> 19:1), so expect ~±48V/~7mA (not ~±96V/~15mA) — audible, just softer than
> the original ringing spec. Pin numbers differ too: the 161G24's secondary
> (drive) side is pins 3-4-5-6 (jumper 4-5 = centre tap, pins 3 & 6 = the
> two ends) instead of the 160G24's 5-6-7-8 (jumper 6-7, pins 5 & 8), and its
> single primary is just pins 1-2 with no series jumper. See
> `docs/rotary_dial_circuit_revL.svg` and the Rev L summary box on it for
> the current, as-built numbers; a 160G24 or Triad VPL24-210 remain drop-in
> upgrades later with no firmware change.

> **UPDATE (2026-08-01, Rev M):** T1 is unchanged from Rev L; what changed is
> the push-pull FETs Q2/Q3. The parts on hand are **IRFZ44N** (55V, not true
> logic-level) instead of the spec'd 60V STP55NF06L. Because 55V is under the
> 60V rule, an RC snubber (R16/R17 100Ω + C9/C10 10nF, one across each
> half-winding) is now fitted to clamp the leakage spike. This does not touch
> any transformer reasoning below. See `docs/rotary_dial_circuit_revM.svg` and
> `docs/revK_design_review/03_bell_failure_modes.md`.

---

## TL;DR

| | |
|---|---|
| **Buy** | Hammond **160G24** — 10 VA, dual 115/230 V primary, 24 V C.T. secondary |
| **Why that one** | Dual primary → series them for 19:1. 12 V half-winding → 25 Hz stays under saturation. 10 VA → winding resistance doesn't eat the output |
| **Wiring** | Jumper pins **6–7** (that junction = center tap → 5 V). Pins 5 & 8 → Q2/Q3 drains. Jumper pins **2–3**. Pins 1 & 4 → bell |
| **Expected** | ~±96 V square @ 25 Hz, ~13–15 mA through the ringer coils |
| **Datasheets** | Both PDFs you attached are **identical** — same Hammond 160-161 sheet |

---

## 1. Your instincts were right

You remembered three things. All three are correct and all three matter here:

| You said | Verdict | How it shows up in this project |
|---|---|---|
| Core material matters | ✅ | Laminated silicon steel. Fine at 25 Hz, useless at 100 kHz (that's ferrite territory) |
| Turns ratio sets voltage | ✅ | This is *the* knob. $V_P/V_S = N_P/N_S$ |
| Spacing/coupling matters | ✅ — this was **leakage inductance** | Flux that links one winding but not the other. Hurts regulation. Negligible for us at 25 Hz |

The one thing that wasn't in your two-wire mental model: **a transformer can have any number of windings on the same core.** That's the whole story below.

---

## 2. The single idea you're missing

> A transformer is **N independent coils sharing one magnetic core.** "Primary" and "secondary" are *job titles you assign*, not physical properties.

Every winding obeys the same rule: **volts per turn is identical across all windings.** That's it. That's the whole device.

```
        ┌──────────┐
  1 ──▓▓│          │▓▓── 5
  2 ──▓▓│   CORE   │▓▓── 6     ← 4 separate coils
  3 ──▓▓│          │▓▓── 7        all see the same flux
  4 ──▓▓│          │▓▓── 8
        └──────────┘
```

### Why 4 windings instead of 2?

Pure manufacturing economics. One part number sells into both the US (115 V) and Europe (230 V):

- Two 115 V primaries → **parallel** for 115 V, **series** for 230 V
- Two 12 V secondaries → **parallel** for 12 V @ 2×, **series** for 24 V @ 1×

You get 4 wiring options from one SKU. **We are hijacking that flexibility**, which is why this part works so well for us.

### 🔑 The exploit

Nothing says the 115 V winding must be the input. Drive the 12 V winding and the 115 V winding becomes a **step-up output**. Same core, same physics, ratio just runs the other way. This is called "running it backwards" and it's completely legitimate.

---

## 3. Your questions, answered directly

### ❓ "20 output voltages — is the input range the same?"

**No.** Two different things got listed next to each other:

| | What it means |
|---|---|
| **Primary: 115 V or 115/230 V** | Fixed. Only two options, and only if it's a dual-primary part |
| **"20 output voltages (5–120 VAC)"** | A **catalog** of ~20 *different part numbers*. Not a range one part covers |

### ❓ "How is the output voltage set?"

**At the factory, by turn count.** It is not adjustable. You pick a part number and you get that ratio, permanently.

Your *only* field-configurable choice is series vs. parallel on each side — a **2× factor**, nothing more:

| Config | Result | Why |
|---|---|---|
| Secondary **parallel** | 12 V @ 900 mA | Same turns, double the copper |
| Secondary **series** | 24 V @ 450 mA | Double the turns |
| Primary **parallel** | 115 V | |
| Primary **series** | 230 V | Double the turns ← **we want this** |

### ❓ "How do you decode `160G24`?"

```
160    G     24
 │     │      └── Secondary voltage (24 V, center-tapped when series-wired)
 │     └───────── Frame size → VA rating (G = 10 VA)
 └─────────────── Series: 160 = DUAL primary, 161 = SINGLE primary
```

> ⚠️ **This convention is NOT portable.** In Hammond's *166* series the same-looking suffix means something different, and that series is single-primary only. **Always read the description line, never the part number.**

---

## 4. How to read the spec table

From your attached datasheet, page 3:

```
161G24    160G24    10    24V C.T. @ 450ma    12V @ 900ma
   │         │      │            │                 │
   │         │      │            │                 └── SERIES config
   │         │      │            └── PARALLEL config (what we use)
   │         │      └── VA (volt-amps)
   │         └── Dual-primary part number  ← BUY THIS ONE
   └── Single-primary part number          ← avoid
```

**Note the column headers are swapped relative to intuition** — Hammond lists "Series" first. 24 V C.T. is the *series* connection; 12 V is *parallel*.

### VA in one line

$$\text{VA} = V \times I$$

10 VA at 24 V = 416 mA. It's a **thermal** limit (how much heat the copper can shed), not a hard cutoff.

---

## 5. Why 160G24 and not the others

Three independent filters. Only one part survives all three.

### Filter 1 — Dual primary (kills the whole 161 series)

Straight from your datasheet's feature list:

> "Choice of economical single primary 115V - **60 Hz only (161 series)** or the universal dual primary 115/230V - **50/60 Hz (160 series)**."

| | 115 V primary | 230 V (series) |
|---|---|---|
| Ratio vs. 12 V half-winding | 9.6:1 | **19.2:1** |
| Output | ±48 V | **±96 V** |
| Bell current | 7.7 mA | **15.5 mA** |
| Result | audible but soft | **original spec** |

Free. No extra parts, no firmware change. **This is the single highest-value decision in the part selection.**

### Filter 2 — The 12 V half-winding is not arbitrary

This is the constraint that surprised me too. Flux depends on **volts per hertz**:

$$B_{peak} \propto \frac{V}{f}$$

Lower frequency at the same voltage → **more** flux → saturation. (AllAboutCircuits covers this under *"Operation at Frequencies Lower than Normal"* — it's the classic 60 Hz-transformer-on-50 Hz problem.)

For a 5 V square wave into a 50/60 Hz-rated winding:

$$\boxed{\text{flux ratio} = \frac{277.5}{f \times V_{half}}} \qquad \text{keep} \le 1$$

| Part | $V_{half}$ | @ 25 Hz | Verdict |
|---|---|---|---|
| 160K12 (12.6 V C.T.) | 6.3 V | **1.76** | ❌ saturates hard |
| **160G24 (24 V C.T.)** | **12 V** | **0.93** | ✅ |
| 160G40 (40 V C.T.) | 20 V | 0.56 | ✅ safe, but ratio drops to 11.5:1 |

> 💡 A *smaller* LV winding would give a bigger step-up — but it saturates. 12 V is the sweet spot where ratio and flux margin both work out. That's why 24 V C.T. and not something else.

### Filter 3 — VA (kills the 1 VA parts)

In the 230 V config the bell load is ~1.5 W, so the LV side pulls **~300 mA**.

The subtle killer is **winding resistance**. A 1 VA part's 115 V winding is ~1–2 kΩ, which forms a voltage divider against the 6.19 kΩ bell:

| Part | VA | Est. loss to winding DCR |
|---|---|---|
| 160D24 | 1 | **25–40%** ❌ |
| 160F24 | 4.4 | ~10% |
| **160G24** | **10** | **~5%** ✅ |

Cost difference is a couple of dollars. Take the 10 VA.

---

## 6. 🔌 Exact wiring (from your connection diagrams)

The 160-series diagram gives real pin numbers, which removes all the guesswork:

**Secondary → our drive winding (12-0-12)**
| Do this | Result |
|---|---|
| Jumper pin **6** to pin **7** | This junction is the **center tap** → 5 V rail |
| Pin **5** | → Q2 drain |
| Pin **8** | → Q3 drain |

**Primary → our HV output**
| Do this | Result |
|---|---|
| Jumper pin **2** to pin **3** | Series-aiding (leave this junction floating) |
| Pin **1** | → R18 220 Ω → bell **RED** |
| Pin **4** | → bell **BLACK** |

```
    Q2 ──5 ▓▓▓ 6──┐                 1 ──▓▓▓── R18 ── RED
                  ├── +5V              ║ (jumper 2–3)
    Q3 ──8 ▓▓▓ 7──┘                 4 ──▓▓▓───────── BLACK
       SECONDARY (drive)              PRIMARY (output)
```

### 🎯 The phasing trap — now solved for you

Series-connected windings can be wired **series-opposing**, where the two halves cancel and you get ~0 V. The dots on the datasheet (pins 1, 3, 5, 7) mark matching polarity; series-aiding means dotted-end to un-dotted-end.

**You don't have to reason about this** — the datasheet's connection diagram already shows the correct jumpers. Just follow the pin numbers above.

**Sanity check before powering up:** with a DMM on continuity, pins 5→8 should read roughly *twice* the resistance of 5→6.

---

## 7. The math, start to finish

**Given:** 5 V drive, 12 V half-winding, 230 V primary, 5.97 kΩ coils + 220 Ω

$$a = \frac{230}{12} = 19.2 \qquad V_{out} = 5 \times 19.2 = 96\text{ V peak}$$

$$I = \frac{96}{5970 + 220} = 15.5\text{ mA} \quad\text{(ideal)}$$

Derating for real winding resistance (~300 Ω primary + ~550 Ω reflected secondary):

$$I_{real} \approx \frac{96}{7040} \approx 13.6\text{ mA}$$

Original spec was ~15 mA. **We land at ~90% of a real telephone exchange.**

> 📐 Reflected impedance: secondary resistance appears on the primary side multiplied by $a^2$. With $a = 19.2$, that's **368×** — which is why a 1 Ω winding becomes a 368 Ω problem, and why VA rating matters more than it first appears.

---

## 8. ⚠️ Things that can still bite

| Risk | Why | Mitigation |
|---|---|---|
| **USB current budget** | ~300 mA during a 2 s ring, on top of the MCU + audio board. USB 2.0 gives 500 mA | Use a **self-powered** hub, or add a 1000 µF bulk cap at the center tap |
| **Shock** | ±96 V @ ~15 mA is genuinely the jolt phone installers know | Insulate the secondary. Never probe while ringing |
| **Series-opposing** | Nets ~0 V, looks like a dead circuit | Follow the pin numbers; DMM check above |
| **Magnetostriction hum** | Core physically buzzes at 2× drive freq | Cosmetic. If loud, raise `RING_FREQ_HZ` toward 30 |
| **Inrush / DC offset** | Any DC in a winding biases flux toward saturation | Firmware's symmetric push-pull + 1 ms deadband already prevents this |

---

## 9. Glossary

| Term | Plain meaning |
|---|---|
| **C.T.** | Center Tap — a wire at the electrical midpoint of a winding |
| **VA** | Volt-amps. Thermal rating. ≈ watts for a resistive load |
| **Dot convention** | Marks which winding ends share polarity. Governs series-aiding vs. opposing |
| **Leakage inductance** | Flux linking one winding only. The "spacing" effect you remembered |
| **Saturation** | Core maxed out; more current stops producing more flux |
| **Reflected impedance** | Secondary-side impedance seen from primary, scaled by $a^2$ |
| **Split bobbin** | Windings in separate compartments → low coupling capacitance, no shield needed |

---

## 10. Sources

- **Hammond 160-161 datasheet** — the PDF you attached (both copies identical)
- [Hammond 160G24 part page](https://www.hammfg.com/part/160G24)
- [Wikipedia — Transformer](https://en.wikipedia.org/wiki/Transformer) — EMF equation $E_{rms} = 4.44 fNAB_{peak}$, dot convention, center-tapped push-pull output stages
- [AllAboutCircuits — Winding Configurations](https://www.allaboutcircuits.com/textbook/alternating-current/chpt-9/winding-configurations/) — multiple windings, taps
- [AllAboutCircuits — Practical Considerations](https://www.allaboutcircuits.com/textbook/alternating-current/chpt-9/practical-considerations-transformers/) — VA ratings, core saturation vs. frequency, leakage inductance

---

## Confidence

**~97%** this works as designed.

**What I'm certain of:** the part exists and is in distribution; the pin-level wiring comes straight from the manufacturer's own connection diagram; the turns ratio and flux math are textbook and cross-checked against the datasheet's own ratings.

**The residual 3%:** winding DC resistance is *estimated*, not from a datasheet (Hammond doesn't publish DCR for this series). If my estimate is pessimistic you get more than 13.6 mA; if optimistic, less. Either way it rings — the uncertainty is loudness, not function.

**Measure before committing:** confirm ~190 Vpp on pins 1–4 with a scope or AC meter *before* connecting the bell's RED/BLACK leads.

# 03 — Bell stage: adversarial findings

> **TL;DR:** the topology is right, but the adversarial pass found two
> significant items — one in the *test firmware* ('a'/'b' DC test ≈ shorting
> the 5 V rail through 2 Ω for a second) and one inherent to push-pull
> converters (*start-up flux doubling*: the core saturates briefly at the
> start of **every** ring). Both have cheap firmware fixes. Everything else
> is medium/low.

Severity legend: 🔴 will bite · 🟡 could bite · 🟢 noted, fine

---

## 🔴 FINDING: the `'a'`/`'b'` DC continuity test is a rail short

**Where:** `bell_ir_test.ino`, serial commands `a`/`b` — "drive one gate
HIGH (DC) for **1 s** — half-winding continuity test."

**The problem:** transformers only oppose *changing* current. Apply 5 V DC
to a half-winding and the current ramps as $i(t) = \frac{V}{R}(1 - e^{-t/\tau})$
toward $V/R_{DCR}$ — and the core saturates long before 1 s, collapsing the
inductance. Final current is limited only by copper:

$$I_{DC} \approx \frac{5\,\text{V}}{R_{DCR(half)} + R_{DS(on)}} \approx \frac{5}{2\,\Omega + 0.014\,\Omega} \approx \textbf{2.5 A}$$

for a winding rated **450 mA** and a USB budget of **500 mA** — held for a
**full second**. Expected symptoms: 5 V rail collapse, MCU brownout-reset
(which ironically releases the gate via R14/R15 — accidental crowbar
protection), possible polyfuse trip on the ItsyBitsy or the PC port.

**Why it slipped through:** the mental model "1 s of DC at 5 V is gentle"
is right for *resistive* loads. A transformer winding is a 2 Ω resistor in
disguise once you hold DC on it.

**Fixes (pick one):**
1. **Delete the test.** It's redundant — the documented DMM check
   (R(5-8) ≈ 2× R(5-6)) already proves winding continuity, unpowered. ✅ best
2. Shorten to ≤ 10 ms (current stays on the inductive ramp, well under 1 A).
3. Run it only from a current-limited bench supply, never USB.

---

## 🔴 FINDING: start-up flux doubling — the core saturates at every ring start

**The problem (textbook push-pull behavior):** in steady state the core flux
swings **symmetrically**, −0.93 → +0.93 of rated, each half-cycle
contributing the full swing of volt-seconds. But at the start of a burst the
core is at ≈ zero flux, and firmware applies a **full-length** (19–20 ms)
first half-cycle:

```
steady state:   -0.93 ══════▶ +0.93   (full V·t swing, centered)
first cycle:     0    ══════▶ +1.86   (same V·t — but starting from 0!)
```

1.86× rated flux is **deep saturation** (typical mains cores rate ~1.2–1.5 T
and saturate ~1.7 T). For the last several ms of that first half-cycle the
winding is effectively just its DCR, and current spikes toward the same
~2 A ceiling as the finding above — briefly, from C7/C8.

**Consequences:** a several-ms, amp-class gulp from the bulk caps at every
burst start. 940 µF sourcing 2 A droops at $dV/dt = I/C ≈ 2.1\,\text{V/ms}$,
so even the caps can't hold the rail through it — expect a visible rail sag
and, worst case, MCU brownout **exactly when the phone tries to ring**.
(If the bring-up symptom is ever "board resets when the bell starts," this
is why. It would look maddeningly like a wiring fault.)

**Fix (standard, cheap, firmware-only):** make the **first half-cycle after
any idle/gap period half-length (10 ms)**. Half the volt-seconds → flux ends
the first half-cycle at +0.93 instead of +1.86 → symmetric from the second
half-cycle onward. This is the classic voltage-mode push-pull soft-start.
One `if (firstHalfCycle)` in `bellUpdate()`/`oscillate()`.

*Residual caveat:* core **remanence** from the previous burst is
uncontrolled (burst always restarts on phase A), so even the T/2 trick isn't
mathematically exact — but it bounds the first-cycle flux to ~0.93 + remanence
(≪ 1.86) which is comfortably survivable.

---

## 🟡 FINDING: the `'-'` tuning command allows saturating frequencies

`bell_ir_test.ino` clamps `setRingFreq()` to **15–40 Hz**. From the flux
equation ([02 §4](02_bell_ring_generator.md)),
flux ratio = 23.1/f — so the floor should be **23 Hz**, not 15:

| f | flux vs rated | state |
|---|---|---|
| 15 Hz | 1.54× | 🔴 heavy saturation, amp-class current every half-cycle |
| 20 Hz | 1.16× | 🟡 saturating — buzz + heat |
| 23 Hz | 1.00× | floor |
| 25 Hz | 0.93× | ✅ default |

The header comment even says "raise RING_FREQ_HZ toward 30 if the
transformer buzzes" — right instinct, but the clamp still lets a curious
`-`-press walk into the red zone during exactly the kind of bench session
where you'd try it.

**Fix:** change `if (hz < 15) hz = 15;` → `if (hz < 23) hz = 23;` (or
document 15–22 Hz as "expect buzz + heavy current, short tests only").

---

## 🟡 FINDING: USB power budget only balances with the self-powered hub

Adding it up during a ring burst on a **bus-powered** hub (one 500 mA
allocation for everything):

| Consumer | Est. draw |
|----------|----------:|
| ItsyBitsy (MCU + LEDs) | ~50 mA |
| Logitech audio PCB (idle–active) | ~100–200 mA |
| Ring burst average | ~300 mA |
| Start-up flux spike (above) | amps, ms-scale |
| **Total during ring** | **~450–550 mA + spikes** |

Over budget at the worst moment. The schematic's "prefer a SELF-POWERED hub"
note is **the** load-bearing mitigation — with it, each port gets its own
500 mA and the analysis closes with margin. Without it, you're betting on
the PC port's generosity.

📖 Also worth knowing: **USB 2.0 allows only 10 µF** of downstream
capacitance at hot-plug without inrush limiting; C7/C8 = 940 µF violates
that on paper (charging inrush at connect). In practice hosts tolerate it
routinely — filed as a compliance nit, not a risk. A self-powered hub also
makes this moot.

---

## 🟡 FINDING: <a name="-finding-no-snubber"></a>no snubber — leakage spikes ride on the FETs' avalanche rating

At every turn-off, the energy in the *leakage* inductance (the flux linking
one half-winding but not the other) has nowhere coupled to go and rings the
drain above the 10.7 V clamp ([02 §6](02_bell_ring_generator.md)).

- Energy per event: $\tfrac{1}{2} L_{lk} I^2 ≈ \tfrac{1}{2}(few\,\text{mH})(0.3\,\text{A})^2$ ≈ **tens of µJ**
- STP55NF06L single-pulse avalanche rating: **hundreds of mJ** (ST: "100%
  avalanche tested") → ~4 orders of magnitude of margin ✅

So no snubber is a *defensible* omission — **but it's an undocumented
dependency**: substitute a non-avalanche-rated or lower-voltage FET later
(the IRFZ44N on hand is 55 V — see the Rev M note below) and the margin
quietly shrinks. If a scope ever shows drain spikes flirting with 60 V, an
RC snubber (~100 Ω + 10 nF across each half-winding) is the textbook retrofit.

**Action:** ✅ **Done (Rev M, 2026-08-01).** The FET actually on hand is the
IRFZ44N (55 V) — a *lower-voltage* part than the 60 V rule wants, which is
exactly the "margin quietly shrinks" case above. Rather than lean on the
avalanche rating of a sub-60 V part, the RC snubber (R16/R17 100 Ω +
C9/C10 10 nF, one across each half-winding, each Q drain → 5 V tap) is now
**fitted** on [rotary_dial_circuit_revM.svg](../rotary_dial_circuit_revM.svg).
The IRFZ44N is itself fully avalanche-rated (E_AS 530 mJ, E_AR 9.4 mJ
repetitive) as a backstop, so the snubbed 55 V part has ample margin — and
fitting the snubber also retires the repetitive-avalanche concern from
[07](07_gemini_review_audit.md).

---

## 🟢 FINDING: <a name="-finding-flux-walking"></a>flux walking (push-pull DC imbalance) — real, but self-limiting here

**The classic push-pull disease:** if the two half-cycles don't apply
*exactly* equal volt-seconds (timing jitter, RDS(on) mismatch), the flux
swing drifts off-center each cycle — "staircase saturation." Industrial
designs fix it with current-mode control.

**Here:** `millis()`-based timing on AVR has ~1 ms granularity, so up to
~1 ms asymmetry per 40 ms period → average DC voltage across the winding
≈ $5 × \tfrac{1}{40} = 125\,\text{mV}$. The winding's own DCR (~2 Ω) turns
that into a bounded ~60 mA DC magnetizing offset rather than a runaway —
copper resistance is the (lossy but effective) stabilizer in low-power
push-pull. Slightly asymmetric current spikes on one phase; not a failure.

**Action:** none. If a scope shows one drain's current spike much fatter
than the other's, this is what you're seeing.

---

## 🟢 FINDING: fault matrix — what happens when things go wrong downstream

| Fault | What happens | Protected by |
|-------|--------------|--------------|
| Bell unplugged mid-ring | Secondary unloaded; drains still clamped ~10.7 V; secondary rises to full ±96 V | topology (body-diode clamp); insulation |
| Secondary shorted (pinched wire) | Reflected to LV side ≈ 1 Ω → ~1.7 A rail drag during bursts | nothing but the polyfuse/brownout 🟡 |
| MCU crash with one gate HIGH | DC through half-winding → the 🔴 DC-test scenario | *only* the watchdog you haven't added; R14/R15 handle reset/Hi-Z but **not** a firmware hang with the pin latched high 🟡 |
| Both gates HIGH (firmware bug) | MMFs cancel → 2 windings × ~2 Ω across the rail → ~5 A | deadband-by-construction in `oscillate()` — single code path sets pins, easy to audit ✅ |

**Cheap hardening (optional):** enable the AVR watchdog (`wdt_enable(WDTO_250MS)`)
so a hang can't leave a gate latched. That converts the worst residual row
into a 250 ms blip.

---

## 🟢 SAFETY: quantifying "±96 V bites"

The schematic's warning is correct; here's the arithmetic behind it. Touch
the live secondary and the source impedance is R18 (220 Ω) + HV winding DCR
(~150 Ω) + reflected LV copper (~740 Ω) ≈ **1.1 kΩ**:

- Dry skin (10–100 kΩ): ~1–9 mA → bite/tingle, like a real phone line.
- Wet skin (~1 kΩ): peaks toward ~45 mA — **above the let-go threshold**.

It's isolated from mains and USB, energy-limited, and burst-limited (2 s) —
genuinely non-lethal-class — but "limited by R18" understates it: R18 is
only 20% of the limiting impedance. Insulate the whole HV side, never probe
while ringing, and treat RED/BLACK with phone-line respect. The schematic
already says this; now you know *why* it's exactly right.

# 05 — Dial, hook, and LEDs (the easy 60%)

> **TL;DR:** three switches to ground, three LEDs, one non-obvious resistor.
> Everything here has been validated on hardware already (dial path
> end-to-end, 2026-07-29). Included for completeness and because R3's story
> is the best small lesson in the whole schematic.

---

## 1️⃣ N1 (WHITE / shunt) — the one channel that needed an external part

**The gotcha:** the dial's shunt contact isn't a clean switch. It has a
**14.5 kΩ bleeder resistor permanently wired across the contacts**
(spark-quench, a telephone-era arc suppression trick). So even with the
contact *open*, the GPIO node is tied to GND through 14.5 kΩ.

**Why the internal pull-up loses:** the ATmega's internal pull-up is
20–50 kΩ. That forms a divider with the bleeder:

$$V_{node} = 5 · \frac{14.5k}{14.5k + R_{pu}} = \begin{cases} 2.1\,\text{V} & R_{pu}=20k \quad 🔴 \\ 1.1\,\text{V} & R_{pu}=50k \quad 🔴 \end{cases}$$

Both below the 32u4's $V_{IH} ≈ 0.6·V_{cc} = 3.0\,\text{V}$ → pin reads a
solid, permanent LOW. **This is not a marginal failure — it's deterministic.**

**Why R3 = 2.2 kΩ wins:**

$$V_{node} = 5 · \frac{14.5k}{14.5k + 2.2k} = 4.34\,\text{V} \; ✅ \quad (\gg 3.0\,\text{V})$$

Closed-contact current: $5/2.2k = 2.3\,\text{mA}$ — trivially safe, and 📖
actually *beneficial*: aged contacts want ~1–10 mA of **wetting current** to
punch through oxide films. A high-impedance sense (µA) on 70-year-old
contacts can read intermittently open even when closed; 2.3 mA is in the
sweet spot by accident. ✅

⚠️ *Bring-up memory:* the "dead dial" of 2026-07-29 was R3's rail end not
actually reaching 5 V. Diagnostic signature worth keeping: **solid LOW even
with internal pull-up enabled = external pull-up rail side is dead** (only
the 14.5 kΩ bleeder can win against the internal pull-up). "Hi-Z LOW but
internal-pullup HIGH" = pin genuinely disconnected. Two reads, no DMM.

---

## 2️⃣ N2 (BLUE / pulse) and N3 (GREEN-WHITE / hook) — true dry contacts

Both are clean switches to GND (DMM: ≈0 Ω closed, open otherwise), so the
internal 20–50 kΩ pull-up is sufficient — no divider to fight. ✅
Empirically proven by the working dial path.

**C6 (100 nF, D7 node → GND):** EMI keep-out for the long handset cord
acting as an antenna. Adversarial check on the side effect: rising edges now
charge through the internal pull-up, $\tau = R_{pu}·C = 2\text{–}5\,\text{ms}$
→ the release edge is slow. The 30 ms hook debounce eats that with 6–15×
margin. ✅ Closing the contact discharges C6 through ≈0 Ω — a brief spark of
contact current that, per §1, old contacts actively enjoy. ✅

⚠️ **Known open hardware item (not a design flaw):** as of the 2026-07-29
session, D7 never registered *external* closures even though its silicon pad
self-tests healthy (drive-LOW readback OK, internal pull-up OK). The on-die
self-test cannot clear the **header solder joint** between pad and pin —
that joint is the prime suspect. Design review has nothing to add; this is a
soldering-iron item.

---

## 3️⃣ LEDs (D9/D10/D11 → 330 Ω → LED → GND)

$I = (5 - V_f)/330 ≈ (5-2)/330 ≈ 9\,\text{mA}$ per LED — inside the 20 mA
per-pin recommendation, and all three lit simultaneously (~27 mA total) is
nowhere near the AVR's per-port or package limits. ✅ Nothing adversarial
survives contact with this subcircuit.

---

## 4️⃣ Polled (not interrupt) firmware — reviewed as a design choice

The inputs change at ~10 Hz with 38–62 ms edges (measured,
`dial_test_log.txt`); a ~1 ms poll loop oversamples the fastest edge ~38×.
Interrupts would add ISR/`volatile`/race complexity in 2.5 KB of RAM for
zero functional gain. ✅ Right call — *with one caveat now that Rev J/K
exists:* the poll loop's other new duty is the bell half-cycle timing, and
anything that blocks the loop (HID send, serial prints, the 0.6 ms IR pair)
adds jitter to the 20 ms half-cycles. Bounded, self-correcting via winding
DCR, analyzed in [03 §flux-walking](03_bell_failure_modes.md#-finding-flux-walking)
— fine, but it's why the firmware runs `bellUpdate()` before the 1 ms poll
gate, and that ordering should be treated as load-bearing.

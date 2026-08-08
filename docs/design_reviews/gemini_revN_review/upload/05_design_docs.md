

================================================================
== FILE: transformer_primer.md
================================================================

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


================================================================
== FILE: pico_port_handoff_prompt.md
================================================================

# Handoff prompt: full port of this project to the Raspberry Pi Pico

Paste this whole file as the opening message to the next planning session.

## Context (read first)

This repo is a vintage rotary phone converted into a USB HID volume-control
dial/hook + (in-progress) a real bell ringer + IR proximity trigger. The
project started on a Raspberry Pi Pico (MicroPython) but was migrated to an
Adafruit ItsyBitsy 32u4 (Arduino C++) in Rev I because the RP2040 was overkill
once audio moved off-MCU onto a gutted USB headset PCB.

**The ItsyBitsy 32u4 hardware has now failed** during bell-driver bring-up:
the chip got very hot and the board stopped enumerating over USB entirely (no
`/dev/ttyACM*`, no `239a:800e` in `lsusb`, unresponsive even to a manual
double-tap-reset into the bootloader). Root cause was never conclusively
proven with a DMM before the decision was made to abandon this MCU rather
than keep debugging it. Leading suspects, in case the Pico build wants to
avoid repeating the same mistake:
- C7/C8 (bulk electrolytic caps on the 5V centre-tap feed) wired with
  reversed polarity.
- D2/D3 (bell gate-drive pins) accidentally bridged past their R12/R13
  series resistors straight to a rail.
Whichever it was, **triple-check both of these specific things** on the new
build before first power-up, and make the capacitor polarity marking on the
new schematic unambiguous.

The git history has a tag `itsybitsy-32u4-final` marking the last commit of
the ItsyBitsy-era work (this is that commit). The ItsyBitsy-era firmware has
been moved to `legacy_itsybitsy/` (parallel to the existing `legacy_pico/`,
which is the OLDER, pre-bell/IR Pico snapshot from before the Rev I
migration -- don't confuse the two; the new Pico work described here is a
superset of both, and legacy_pico/'s dial/hook/HID code is a **useful
reference/starting point**, not something to throw away).

Repo memory at `/memories/repo/vintage_headset.md` (if your tool has access
to it) has the full blow-by-blow design history -- read it before making
electrical decisions, it has a lot of hard-won gotchas (header pin-miscount
traps, transformer part-selection math, MicroPython performance pitfalls,
USB HID/mpremote quirks, etc.). If you don't have access to it, the
equivalent detail is spread across `docs/revK_design_review/`,
`docs/transformer_primer.md`, and the schematic files below -- read those
instead.

## Your mandate

Accomplish a **full port of every feature currently designed for the
ItsyBitsy 32u4 back onto the Raspberry Pi Pico (RP2040, MicroPython)** --
not just the dial/hook subset legacy_pico/ already had, but ALSO the bell
ring generator and IR trigger that were designed and firmware-complete on
the ItsyBitsy but never got a Pico equivalent. Nothing should be left as
"ItsyBitsy-only" when this is done. Concretely, that means:

### 1. Firmware -- dial / hook / LEDs / HID (mostly restoring legacy_pico/)
- Port `legacy_pico/main.py` + `hid_consumer.py` forward: dial pulse
  decoding, digit -> volume% mapping (1-9 -> 10-90%, 0 -> 100%), on-hook
  mute/restore, SHUNT/PULSE/HOOK debounce (15ms/-/30ms), 3 status LEDs
  (shunt/pulse/hook -- the HOOK LED was added post-legacy_pico, on the
  ItsyBitsy side only, so it needs a NEW Pico GPIO assignment).
- Re-verify the R3 2.2k external pull-up requirement on the SHUNT line
  still applies (it should -- this was always Pico-native knowledge,
  the ItsyBitsy just inherited it).
- USB HID: decide report format. legacy_pico's original vendor HID (page
  0xFF00, usage 0x01) sent a bare 1-byte percent report with no Report ID.
  The ItsyBitsy version added a leading Report ID byte (an Arduino/
  PluggableUSB requirement, NOT an RP2040 one). Recommend reverting to the
  simpler 1-byte format to match the Pico's native `usb.device.hid` stack,
  but whichever you choose, update `host/volume_daemon.py` (VID/PID back
  to `2e8a:0005`, report parsing) to match, and test the full pipeline
  end-to-end (`pactl`/PipeWire volume actually changes).
- Watch the known usb.device gotchas before you touch USB init twice in a
  session: re-enumeration on `usb.device.get().init()` is normal, but
  re-initializing a second time while a composite config is already active
  can wedge the RP2040's USB peripheral hard enough to need a real power
  cycle.

### 2. Firmware -- bell ring generator (NEW, no Pico version ever existed)
Port the push-pull driver from `legacy_itsybitsy/rotary_volume/rotary_volume.ino`
and `legacy_itsybitsy/bell_ir_test/bell_ir_test.ino`:
- Two GPIO outputs (BELL_A/BELL_B equivalent) alternately driving Q2/Q3
  gates, 1ms deadband so both gates are NEVER high together.
- Soft-start: the first half-cycle after idle must be half-length (avoids
  the ~1.86x rated flux spike a full-length first cycle causes from zero
  flux).
- Configurable ring frequency with a saturation floor for whichever
  transformer ends up installed (currently a Hammond 161G24, single
  115V/60Hz-only primary -- floor was 28Hz, default 30Hz; see
  `docs/transformer_primer.md` and revK_design_review for the flux-ratio
  math if the transformer changes).
- Cadence state machine (2s ring / 4s pause / N bursts) AND a
  continuous "hold" mode for bench testing.
- **Timing note**: this is a ~30-60Hz square wave (16-20ms half-periods),
  NOT sample-rate audio. The old Pico audio work hit real timing trouble at
  8kHz-in-plain-Python (see memory: `@micropython.native` was tried, made
  things WORSE, was removed -- the eventual fix was a precomputed lookup
  table, not the native decorator). Do not blindly assume this bell timing
  needs the same treatment -- it has ~1000x more slack than that audio
  loop did. Verify empirically (log actual half-period min/max via
  `time.ticks_us()` deltas) before adding any complexity; don't add
  `@micropython.native` preemptively.
- machine.WDT for RP2040 if you want a watchdog (the AVR version needed a
  special `.init3` MCUSR-clear hack because Caterina's bootloader doesn't
  reset the watchdog config -- that hack is AVR/Caterina-specific and does
  NOT apply to the RP2040's own ROM bootloader; don't port it verbatim,
  research RP2040 machine.WDT semantics fresh).
- Standalone bring-up script first (e.g. `bell_test.py`, no HID/dial code
  loaded), following this repo's established phased-bring-up pattern
  (see the old `mic_meter.py`/`receiver_test.py` Phase 1/2 approach in
  memory) -- do not merge into `main.py` until it's bench-verified.
- **CRITICAL ELECTRICAL RE-CHECK, do not skip:** the ItsyBitsy is a 5V
  board (GPIO HIGH = 5V) and the IRFZ44N gate-drive analysis in Rev M was
  done for a 5V gate drive. The **Pico's GPIO HIGH is 3.3V**. Re-verify from
  the IRFZ44N (or whatever FET you use) datasheet transfer curve whether it
  still fully enhances at Vgs=3.3V for this ~0.3A load -- do not assume the
  Rev M analysis carries over. If it doesn't hold up, you may need a
  different logic-level FET (rated for full enhancement at ~2.5-3.3V) or a
  small gate driver/buffer stage. This is a new constraint the ItsyBitsy
  build never had to deal with.

### 3. Firmware -- IR trigger (NEW, no Pico version ever existed)
Port from `legacy_itsybitsy/bell_ir_test/bell_ir_test.ino`:
- Synchronous sampling (read ADC with emitter off, then on, subtract) for
  ambient rejection -- these are bare 2-leg phototransistors, no TSOP
  demodulator module, so this software trick is mandatory, not optional.
- Baseline calibration at boot (resting emitter->detector crosstalk),
  threshold = baseline + margin, lockout timer after a trigger.
- Re-tune `IR_SETTLE_US` and the trigger margin from scratch against real
  hardware -- the RP2040's ADC (12-bit) has different noise/timing
  characteristics than the AVR's (10-bit); don't copy the AVR constants
  and assume they're right.

### 4. Hardware / schematic
- Produce a **new, complete wiring diagram re-specced for the Pico's GPIO
  numbering** covering every subsystem above: dial SHUNT/PULSE/HOOK, all 3
  status LEDs, the bell driver (gate resistors, snubbers R16/R17+C9/C10,
  bulk caps C7/C8, T1's 161G24 pinout, R18, bell RED/BLACK), and the IR
  emitter/detector pair. This supersedes `rotary_dial_circuit_revM.svg` --
  do not just relabel it, re-verify every pin assignment is Pico-appropriate
  (remember the ORIGINAL Pico had its own GP2/GP3/GP4/GP14/GP15 pin map,
  visible in the pre-Rev-I schematics/legacy_pico -- that mapping is your
  starting point for the dial/hook/LED section).
- Follow this repo's existing SVG conventions if you're hand-authoring SVG:
  render with `rsvg-convert -w W -h H file.svg -o out.png` then crop+view
  to check for text overflow -- there is a well-documented history in
  memory of new text lines silently overflowing box edges; verify with a
  rightmost-non-background-pixel scan (PIL), not just eyeballing.
- Re-run (don't skip) the same bench-test discipline already established in
  `docs/bell_bench_test_setup.svg`: bell physically disconnected, DMM
  across the R18->RED/BLACK gap first, scope check on the FET drains for
  the leakage spike staying under the FET's voltage rating, only then
  reconnect the bell. The electrical risk here has NOT been re-validated
  for a 3.3V-gate-drive build at all yet.
- USB current budget: the ring pulls ~300mA bursts from the 5V rail on top
  of whatever else shares the bus; a self-powered hub or adequate bulk
  capacitance is still required, same as before.

### 5. Repo structure
- `legacy_itsybitsy/` now holds the ItsyBitsy-era sketches (already moved).
  Leave it alone except to reference wiring history.
- `legacy_pico/` is the OLDER pre-bell/IR Pico snapshot. Leave it alone too
  -- use it as a reference, don't edit in place.
- Put the new Pico work at the repo root (matching the original
  pre-migration layout: `main.py`, `hid_consumer.py`, plus new standalone
  bring-up scripts), OR in a clearly-named new directory if you prefer --
  just don't reuse `legacy_pico/` or `legacy_itsybitsy/` for new code.
- Update `host/volume_daemon.py` for whatever HID report format you land on
  (see section 1).
- Keep appending to `/memories/repo/vintage_headset.md` as you go (if
  available) rather than creating new memory files -- this repo has a
  strong existing convention of recording gotchas there.

## Verification checklist (must actually be executed on real hardware, not
just designed)
1. USB HID enumerates on the Pico; confirm the udev rule for VID 2e8a
   still exists/works (it may have been superseded by the 239a ItsyBitsy
   rule added later -- check `/etc/udev/rules.d/`).
2. Dial digits 1-9,0 each produce the right volume%; on-hook mutes and
   restores. Compare pulse timing against the existing
   `dial_test_log.txt` as a sanity baseline.
3. Bell bench test (Section 4's disconnected-bell procedure) passes with a
   real non-zero AC reading before the bell is ever reconnected.
4. IR trigger fires reliably on an intentional wave/approach and does NOT
   false-trigger at rest, tuned against your real ambient lighting.
5. Full end-to-end smoke test: dial a digit, lift/rest the handset, wave to
   trigger a test ring -- all in one session, no re-flash between them.

## Explicit non-goals
- Do not re-litigate the USB-headset-for-audio decision (Rev H pivot) --
  audio is out of scope for this port, it's handled by the separate
  Logitech PCB + hub, unaffected by which MCU drives the dial/bell/IR.
- Do not re-derive the transformer part selection from scratch --
  `docs/transformer_primer.md` and `docs/revK_design_review/` already have
  that reasoning; only the MCU/GPIO-voltage side needs fresh analysis.


================================================================
== FILE: bell_bench_test_setup.svg.txt
================================================================

<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1300 980" font-family="monospace" font-size="14">
  <style>
    .wire   { stroke:#111; stroke-width:2; fill:none; }
    .dash   { stroke:#555; stroke-width:1.5; fill:none; stroke-dasharray:5,4; }
    .lbl    { fill:#111; font-size:13px; }
    .lbl-b  { fill:#111; font-size:13px; font-weight:bold; }
    .lbl-sm { fill:#222; font-size:11px; }
    .ic     { fill:#fff; stroke:#111; stroke-width:2; }
    .node   { fill:#111; }
    .res    { fill:#fff; stroke:#111; stroke-width:2; }
    .cap    { stroke:#111; stroke-width:3; fill:none; }
    .tp     { fill:#c0392b; stroke:#7a1f1f; stroke-width:1.5; }
    .tplbl  { fill:#7a1f1f; font-size:12px; font-weight:bold; }
  </style>

  <rect x="0" y="0" width="1300" height="980" fill="#f3ecda"/>
  <text x="20" y="28" class="lbl-b" font-size="18">Bell driver bench test setup -- BELL DISCONNECTED, snubber/voltage checks (Rev M)</text>
  <text x="20" y="48" class="lbl-sm">Every measurement below happens with the bell's RED/BLACK leads physically unplugged from R18/T1 -- T1 runs unloaded (open secondary) for these steps.</text>

  <!-- Q2 -->
  <rect x="60" y="150" width="90" height="60" class="ic"/>
  <text x="105" y="174" text-anchor="middle" class="lbl-sm">Q2</text>
  <text x="105" y="189" text-anchor="middle" class="lbl-sm" fill="#555">N-ch</text>
  <text x="105" y="204" text-anchor="middle" class="lbl-sm" fill="#a03a3a">IRFZ44N</text>
  <text x="30" y="182" text-anchor="end" class="lbl-sm">D2 gate</text>
  <text x="52" y="176" text-anchor="end" class="lbl-sm">G</text>
  <line x1="10" y1="180" x2="60" y2="180" class="wire"/>
  <text x="156" y="176" class="lbl-sm">D</text>
  <text x="112" y="216" class="lbl-sm">S</text>
  <line x1="105" y1="210" x2="105" y2="218" class="wire"/>
  <line x1="75" y1="218" x2="105" y2="218" class="wire"/>
  <text x="20" y="222" class="lbl-sm">GND</text>
  <circle cx="180" cy="130" r="7" class="tp"/>
  <text x="196" y="126" class="tplbl">TP-A: Q2 drain</text>
  <text x="196" y="141" class="lbl-sm">scope +, GND clip near Q2 source</text>

  <!-- Q3 (moved down, more room for the snubber corridor) -->
  <rect x="60" y="500" width="90" height="60" class="ic"/>
  <text x="105" y="524" text-anchor="middle" class="lbl-sm">Q3</text>
  <text x="105" y="539" text-anchor="middle" class="lbl-sm" fill="#555">N-ch</text>
  <text x="105" y="554" text-anchor="middle" class="lbl-sm" fill="#a03a3a">IRFZ44N</text>
  <text x="30" y="532" text-anchor="end" class="lbl-sm">D3 gate</text>
  <text x="52" y="527" text-anchor="end" class="lbl-sm">G</text>
  <line x1="10" y1="530" x2="60" y2="530" class="wire"/>
  <text x="156" y="527" class="lbl-sm">D</text>
  <text x="112" y="497" class="lbl-sm">S</text>
  <line x1="105" y1="500" x2="105" y2="492" class="wire"/>
  <line x1="75" y1="492" x2="105" y2="492" class="wire"/>
  <text x="20" y="496" class="lbl-sm">GND</text>
  <circle cx="180" cy="580" r="7" class="tp"/>
  <text x="196" y="596" class="tplbl">TP-C: Q3 drain</text>
  <text x="196" y="611" class="lbl-sm">scope + here (2nd channel, or repeat the TP-A test)</text>

  <!-- drain nodes -->
  <line x1="150" y1="180" x2="230" y2="180" class="wire"/>
  <circle cx="180" cy="180" r="4" class="node"/>
  <line x1="150" y1="530" x2="230" y2="530" class="wire"/>
  <circle cx="180" cy="530" r="4" class="node"/>

  <!-- Q2 snubber: R16+C9, drain(180,180) down to shared 5V tap at y=355 -->
  <line x1="180" y1="180" x2="180" y2="220" class="wire"/>
  <rect x="172" y="220" width="16" height="40" class="res"/>
  <text x="196" y="235" class="lbl-sm" fill="#a03a3a">R16</text>
  <text x="196" y="249" class="lbl-sm" fill="#a03a3a">100&#8486;</text>
  <line x1="180" y1="260" x2="180" y2="278" class="wire"/>
  <line x1="170" y1="278" x2="190" y2="278" class="cap"/>
  <line x1="170" y1="286" x2="190" y2="286" class="cap"/>
  <text x="196" y="286" class="lbl-sm" fill="#a03a3a">C9 10nF</text>
  <line x1="180" y1="286" x2="180" y2="355" class="wire"/>

  <!-- Q3 snubber: R17+C10, drain(180,530) up to the same shared 5V tap -->
  <line x1="180" y1="530" x2="180" y2="470" class="wire"/>
  <rect x="172" y="430" width="16" height="40" class="res"/>
  <text x="196" y="445" class="lbl-sm" fill="#a03a3a">R17</text>
  <text x="196" y="459" class="lbl-sm" fill="#a03a3a">100&#8486;</text>
  <line x1="180" y1="430" x2="180" y2="412" class="wire"/>
  <line x1="170" y1="412" x2="190" y2="412" class="cap"/>
  <line x1="170" y1="404" x2="190" y2="404" class="cap"/>
  <text x="196" y="410" class="lbl-sm" fill="#a03a3a">C10 10nF</text>
  <line x1="180" y1="404" x2="180" y2="355" class="wire"/>

  <line x1="180" y1="355" x2="260" y2="355" class="wire"/>
  <circle cx="180" cy="355" r="4" class="node"/>
  <text x="266" y="351" class="lbl-sm">5V tap</text>
  <text x="266" y="365" class="lbl-sm">(C7/C8 bulk caps)</text>

  <!-- T1 -->
  <text x="470" y="150" class="lbl-b">T1 (161G24)</text>
  <path d="M420,180 a10,10 0 0 0 0,20 a10,10 0 0 0 0,20 a10,10 0 0 0 0,20 a10,10 0 0 0 0,20 a10,10 0 0 0 0,20 a10,10 0 0 0 0,20 a10,10 0 0 0 0,20" class="wire"/>
  <text x="400" y="176" text-anchor="end" class="lbl-sm" fill="#555">pin 3</text>
  <line x1="420" y1="320" x2="420" y2="390" class="wire"/>
  <path d="M420,390 a10,10 0 0 0 0,20 a10,10 0 0 0 0,20 a10,10 0 0 0 0,20 a10,10 0 0 0 0,20 a10,10 0 0 0 0,20 a10,10 0 0 0 0,20 a10,10 0 0 0 0,20" class="wire"/>
  <text x="400" y="526" text-anchor="end" class="lbl-sm" fill="#555">pin 6</text>
  <line x1="420" y1="180" x2="230" y2="180" class="wire"/>
  <line x1="420" y1="530" x2="230" y2="530" class="wire"/>
  <line x1="440" y1="355" x2="420" y2="355" class="wire"/>
  <text x="446" y="340" class="lbl-sm">centre tap (5V)</text>
  <line x1="460" y1="200" x2="460" y2="510" class="wire"/>
  <line x1="468" y1="200" x2="468" y2="510" class="wire"/>
  <path d="M510,220 a10,10 0 0 1 0,20 a10,10 0 0 1 0,20 a10,10 0 0 1 0,20 a10,10 0 0 1 0,20 a10,10 0 0 1 0,20 a10,10 0 0 1 0,20 a10,10 0 0 1 0,20 a10,10 0 0 1 0,20 a10,10 0 0 1 0,20" class="wire"/>
  <text x="536" y="400" class="lbl-sm">HV: single 115V winding</text>
  <text x="515" y="216" class="lbl-sm" fill="#555">pin 1</text>
  <text x="515" y="484" class="lbl-sm" fill="#555">pin 2</text>

  <!-- Secondary to R18 to disconnected bell terminals, DMM across the gap -->
  <line x1="510" y1="220" x2="600" y2="220" class="wire"/>
  <rect x="600" y="212" width="60" height="16" class="res"/>
  <text x="600" y="202" class="lbl-sm">R18 220&#8486;</text>
  <line x1="660" y1="220" x2="693" y2="220" class="wire"/>
  <text x="715" y="224" class="lbl-sm" fill="#a03a3a">RED (open)</text>

  <line x1="510" y1="490" x2="693" y2="490" class="wire"/>
  <text x="715" y="494" class="lbl-sm" fill="#a03a3a">BLACK (open)</text>

  <!-- gap markers showing disconnected bell -->
  <line x1="693" y1="212" x2="693" y2="228" stroke="#a03a3a" stroke-width="3"/>
  <line x1="693" y1="482" x2="693" y2="498" stroke="#a03a3a" stroke-width="3"/>
  <text x="620" y="530" class="lbl-sm" fill="#a03a3a">bell RED/BLACK leads UNPLUGGED for this whole test -- T1 secondary runs open/unloaded</text>

  <!-- DMM across the R18/bell-disconnect gap -->
  <circle cx="850" cy="220" r="7" class="tp"/>
  <text x="865" y="200" class="tplbl">TP-B: R18-&gt;RED vs BLACK</text>
  <line x1="785" y1="220" x2="850" y2="220" class="dash"/>
  <line x1="785" y1="490" x2="850" y2="490" class="dash"/>
  <rect x="820" y="330" width="90" height="60" class="ic"/>
  <text x="865" y="355" text-anchor="middle" class="lbl-sm">DMM</text>
  <text x="865" y="371" text-anchor="middle" class="lbl-sm" fill="#555">AC volts</text>
  <line x1="850" y1="220" x2="850" y2="330" class="wire"/>
  <line x1="850" y1="390" x2="850" y2="490" class="wire"/>

  <!-- Legend / step box -->
  <rect x="20" y="700" width="1260" height="270" fill="#eaf3ea" stroke="#3a8a3a" stroke-width="1.5"/>
  <text x="32" y="722" class="lbl-b" fill="#1e5c1e">Step order (bell stays disconnected the whole time)</text>
  <text x="32" y="744" class="lbl-sm" fill="#1e5c1e">1. POWER OFF. DMM continuity/resistance: T1 pins R(3-6) &#8776; 2x R(3-4) (161G24 sanity check); R16/C9 and R17/C10 legs not open, not dead-shorted; Q2/Q3 not D-S shorted (diode mode).</text>
  <text x="32" y="762" class="lbl-sm" fill="#1e5c1e">2. Confirm bell RED/BLACK are physically unplugged (red gap tick marks above, TP-B open). This protects the bell coil and clapper mechanism during first power-up.</text>
  <text x="32" y="780" class="lbl-sm" fill="#1e5c1e">3. Power the ItsyBitsy over USB. Open the serial monitor at 115200 baud (bell_ir_test.ino), do NOT open at 1200 baud.</text>
  <text x="32" y="798" class="lbl-sm" fill="#1e5c1e">4. Send 'h' (hold/continuous ring) so the driver runs steadily instead of a 2s burst -- easier to catch a stable reading on a DMM, which is slow to settle.</text>
  <text x="32" y="816" class="lbl-sm" fill="#1e5c1e">5. TP-B, DMM in AC VOLTS (auto-range): expect roughly 48Vac across RED vs BLACK (161G24 unloaded, Rev L/M). This confirms T1 and its wiring/turns ratio, independent of the FETs.</text>
  <text x="32" y="834" class="lbl-sm" fill="#1e5c1e">6. TP-A / TP-C, scope only (a DMM cannot see this): probe a drain vs GND. Expect ~0V while on, a ~10V flat top while off, and a brief spike riding on that flat top.</text>
  <text x="32" y="852" class="lbl-sm" fill="#1e5c1e">   PASS = spike stays clearly under 55V (the IRFZ44N's rated V_DSS). If it's flirting with 55V, STOP and re-check the snubber wiring/values before going further.</text>
  <text x="32" y="870" class="lbl-sm" fill="#a03a3a">NO SCOPE ON HAND? A DMM cannot catch a microsecond-scale spike -- it only reads the (much lower) average/RMS. You are then trusting the calculated margin</text>
  <text x="32" y="888" class="lbl-sm" fill="#a03a3a">(snubber + IRFZ44N avalanche rating, see docs/revK_design_review/03_bell_failure_modes.md), not a direct measurement. Two cheap ways to hedge without a scope:</text>
  <text x="32" y="906" class="lbl-sm" fill="#a03a3a">  a) run step 4 for only a few seconds at first, feeling Q2/Q3 for warmth right after (excess heat = a clue) before running it continuously;</text>
  <text x="32" y="924" class="lbl-sm" fill="#a03a3a">  b) borrow a scope for just this one check -- it is the single measurement in this whole design that a DMM structurally cannot make.</text>
  <text x="32" y="942" class="lbl-sm" fill="#1e5c1e">7. Send 's' to stop. DMM in DC volts on the 5V rail near T1's centre tap while ringing (step 4 again) -- confirm it doesn't sag close to the AVR's ~4.5V brownout floor.</text>
  <text x="32" y="960" class="lbl-sm" fill="#1e5c1e">8. Only once 5/6/7 look right: power off, reconnect bell RED/BLACK, power on, 'r' for one real ring, listen/feel the clapper. 9. Insulate exposed HV wiring -- ~48V real shock.</text>
</svg>

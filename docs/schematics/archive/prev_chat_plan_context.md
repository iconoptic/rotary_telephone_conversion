# Researched Outline: Rotary Phone Conversion Project Audio Addition

Fetched 2 resources

Research confirms the key physics that makes this project very doable with just your parts bin — carbon microphones are literally the one mic type that **needs no amplifier**: they're variable resistors that produce high-level signals straight from a small DC bias current (that's how they drove miles of phone line with zero electronics). And the earpiece receiver is a high-impedance electromagnetic coil (~50–300Ω typical), which means a single transistor can drive it — no amp IC needed there either.

Quick answers to your side questions:
- **Port names**: the wall-cord jack is an **RJ11** (6P4C modular); the handset jack with 4 contacts is a **4P4C**, colloquially **RJ9/RJ22**. If it's older hardwired style, those were spade lugs on a terminal block. Either way, the vacated wall-port hole is a perfect USB cable feed.
- **Wire mapping**: your observation (speaker = white+green inside the handset) means by elimination **mic = black+red** at the jack. Cord conductors are normally straight through, but we'll DMM-verify.
- **Logitech headset**: yes, it contains both converters (a USB audio codec chip, likely C-Media class). The chip will be SMD and undocumented — but the winning future move is **don't harvest the chip, keep the whole PCB**: it's a complete USB sound card, and you'd just solder the phone's mic/speaker wires to its (usually through-hole) speaker/mic pads. Noted as future Plan B, excluded from this version per your instruction. 

Created memory file [](file:///home/btgrant/.config/Code/User/workspaceStorage/5c33566817f67465e287c4b457436175/GitHub.copilot-chat/memory-tool/memories/MmRmZGM0MDktNmU0ZC00MzNkLTg5OTAtZjkxOGZmNTViMDQ5/plan.md)

## Plan: Handset audio with discrete parts only

Use the carbon mic's superpower (self-amplifying, needs only DC bias) and the receiver's high impedance (single-transistor drivable) to get authentic telephone-band audio (8 kHz, 300–3400 Hz) with nothing but resistors, caps, one transistor, and one diode.

**Steps**

*Phase 0 — DMM verification (you, before any wiring)*
1. Continuity from the 4P4C jack pins: confirm white+green → receiver, black+red → mic.
2. Mic across black/red: expect **30–350Ω that jitters when you shake/talk into it** — that confirms carbon type. (If it reads open or fixed kΩ, it's a different transducer and we re-plan.)
3. Receiver across white/green: expect ~50–300Ω; the value sets our current-limit math.

*Phase 1 — Mic front end → GP26/ADC0*
4. Bias chain: 3V3 → **220–330Ω** → mic → GND (~10mA through the carbon button). Decouple the bias rail with **100µF + 100nF**.
5. AC-couple the mic junction through **1–10µF**, into a **4.7kΩ + 10nF** RC low-pass (cutoff ≈ 3.4kHz — literally the telephone band), with a **2×100kΩ divider** centering the ADC pin at 1.65V. Carbon mics are *loud* — we'll likely tune attenuation, not add gain.

*Phase 2 — Speaker driver → GP10 PWM*
6. PWM (~125kHz carrier) → **1kΩ** base resistor → **NPN (2N2222/BC337/BC547)** low-side switch; receiver from 3V3 to collector; **flyback diode (1N4148/1N400x)** across the coil (it's inductive). Series resistor only if the receiver measures under ~100Ω. Silence = 50% duty; audio modulates duty; the coil itself filters the carrier.

*Phase 3 — Firmware, staged (each independently testable)*
7. **Tone test**: PWM beep out the earpiece.
8. **Mic meter**: 8kHz sampling, print RMS levels, record a 2s snippet to flash → play on host to judge quality and set attenuation.
9. **Local loopback**: mic → earpiece sidetone on the Pico.
10. **USB streaming** (the risky one, last): extend the vendor HID (64-byte reports = 32 samples/4ms per direction) or add a CDC channel; extend the host daemon to bridge into a PipeWire virtual mic/sink (`module-pipe-source`/`module-pipe-sink`). Mitigations if MicroPython can't keep up: 8-bit samples, `rp2.DMA` ADC capture, viper loops. Escape hatch: C SDK + TinyUSB UAC2 (deferred decision).

*Phase 4 — Docs*
11. New revE diagram (mic front end, speaker driver, 4P4C pinout, USB feed through the old RJ11 hole) + main.py header update.

**Component hunt list**
- Resistors: 220 or 330Ω, 1kΩ, 4.7kΩ, 2× 100kΩ (optional: 10–47Ω, 47–100Ω)
- Caps: 100µF, 100nF, 1–10µF, 10nF
- One NPN transistor (2N2222/BC337/BC547 — any general-purpose NPN), one 1N4148 or 1N4001-class diode

**Relevant files**
- main.py — Phase 3 firmware stages; reuse the existing event-queue/IRQ pattern and `VolumeHID` integration
- volume_daemon.py — Phase 3d extension for audio bridging
- docs/rotary_dial_circuit_revE.svg (new) — based on rotary_dial_circuit_revD.svg

**Verification**
1. Phase 0 DMM readings recorded before wiring
2. Clean audible tone from earpiece, transistor stays cool
3. Recorded mic snippet intelligible on host (`sox` raw import, 8kHz mono)
4. Live sidetone loopback works
5. Virtual mic shows up in `pavucontrol` carrying handset speech; audio played to virtual sink heard in earpiece

**Decisions**
- Built-in carbon mic + receiver only; no DAC/ADC chips; telephone-band quality is the target (and honestly, the authentic aesthetic)
- Logitech headset = future Plan B: keep its PCB **intact** as a USB sound card, wire phone transducers to its pads — no SMD harvesting ever needed
- Full-duplex USB streaming deliberately sequenced last as the highest-risk item

**Further Considerations**
1. **Sample format for USB streaming** — 8-bit (µ-law-ish, halves bandwidth, period-authentic) vs 16-bit. Recommendation: start 16-bit, drop to 8-bit only if throughput suffers.
2. **Speaker supply rail** — 3V3 (safe, quieter) vs VBUS 5V (louder, but watch current). Recommendation: 3V3 first; the earpiece sits against your ear, it doesn't need much.

Ready to start with Phase 0 whenever you are — grab the DMM and those three measurements will lock in the resistor values.


# Response to User's Follow-Up Query RE: Film Capacitors

Film caps are "better" in the audiophile sense (lower dielectric absorption, no leakage current, no polarity, more stable value over time/temperature) — but that mostly matters for high-fidelity signal paths, not a telephone-bandwidth carbon-mic circuit. For this project it's a mixed bag depending on which cap:

- **Coupling cap (1–10µF) at the mic junction**: This is the one place film quality could theoretically  (it's directly in the audio signal path). But film caps at 1–10µF are physically large and less common in hobbyist bins than at that size — if you have polyester/mylar/polypropylene caps in that range, use them; if not, a plain electrolytic is genuinely fine here. The bottleneck on quality is the ~300–3400Hz carbon mic and RC filter, not dielectric absorption you'd never notice at telephone bandwidth.
- **Anti-alias filter cap (10nF) and any small bias/timing caps**: Film or ceramic (C0G/NP0 ideally) — small values, cheap, no downside, use whichever you have.
- **Bias-rail decoupling (100µF)**: Definitely electrolytic. Film at 100µF would be comically large; this cap's job is bulk smoothing of the mic's fluctuating supply current, not signal fidelity, so electrolytic's leakage/tolerance quirks don't matter here.

**Bottom line**: use film where it's small and convenient (the 10nF filter cap, maybe the coupling cap if you have one in range), electrolytic where you need bulk capacitance (the 100µF bias decoupling) — don't go out of your way sourcing large-value film caps for this circuit, the payoff isn't there given the telephone-quality target.

matter
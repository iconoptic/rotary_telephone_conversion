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

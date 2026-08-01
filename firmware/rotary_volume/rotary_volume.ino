/*
  Rotary dial decoder + switchhook + LED status + USB HID absolute volume
  control + IR-triggered bell ringer, for the Adafruit ItsyBitsy 32u4
  (ATmega32u4, 5V/16MHz).

  Rev J adds the bell (ringer) and an IR link, see the bottom of this
  comment block and docs/rotary_dial_circuit_revJ.svg.

  Rev I -- MCU migration from a Raspberry Pi Pico (RP2040/MicroPython)
  prototype. After Rev H moved ALL audio handling off the microcontroller
  (a gutted Logitech USB headset PCB now drives the earpiece/mic), the
  Pico's ARM Cortex-M0+ / 264KB RAM / 2MB flash were massive overkill for
  what is now a pure "dial+hook -> USB HID volume/mute" input device. The
  ItsyBitsy 32u4 has native USB HID support in silicon and just enough I/O,
  at a fraction of the size/cost.

  Behavior is a faithful, POLLED (not interrupt-driven) port of the
  original main.py -- dial pulses and hook transitions are slow mechanical
  events (10Hz pulses, tens-of-ms edges) so a ~1ms polling loop on a 16MHz
  AVR has enormous timing margin and avoids ISR/volatile complexity in the
  ATmega32u4's 2.5KB of RAM.

  WIRING (see docs/rotary_dial_circuit_revI.svg):
    SHUNT_PIN (D0)  -- White pair (dial off-normal). Has a 14.5kohm internal
                       bleeder resistor in parallel with the contact at
                       rest, so an EXTERNAL 2.2kohm pull-up to 5V is
                       MANDATORY (this board's internal pull-ups, ~20-50k,
                       are too weak: divider would sit ~2.1V, below the
                       ~3.0V VIH at 5V logic).
    PULSE_PIN (D1)  -- Blue pair (dial pulse contact). True dry contact,
                       ~0ohm; internal INPUT_PULLUP is sufficient.
    HOOK_PIN  (D7)  -- Green/White pair (switchhook lever). True dry
                       contact; internal INPUT_PULLUP is sufficient. Keep
                       the 100nF EMI filter cap from this pin to GND (long
                       handset cord).
    LED_SHUNT (D9)  -- 330ohm series resistor -> LED -> GND. Lit whenever
                       the dial is off-normal (moving).
    LED_PULSE (D10) -- 330ohm series resistor -> LED -> GND. Mirrors the
                       raw pulse contact (~10Hz square wave during spring
                       return), visible to the naked eye.
    LED_HOOK  (D11) -- 330ohm series resistor -> LED -> GND. Lit whenever
                       the switchhook (N3) is ON-HOOK (handset resting,
                       muted); off whenever OFF-HOOK (handset lifted).

  REV J WIRING ADDITIONS:
    IR_TX     (D5)  -- R10 150ohm -> IR emitter LED anode; cathode to GND.
                       ~24mA, within the 32u4's 40mA absolute pin limit.
    IR_RX     (A0)  -- IR phototransistor collector to 5V, emitter to this
                       pin AND through R11 10kohm to GND (emitter follower
                       load). More IR -> higher voltage.
    BELL_A    (D2)  -- gate of push-pull MOSFET Q2 (via R12 100ohm, with
                       R14 10k gate pulldown).
    BELL_B    (D3)  -- gate of push-pull MOSFET Q3 (via R13 100ohm, with
                       R15 10k gate pulldown).

  BELL DRIVE THEORY: the ringer coils measure 5.97kohm DC, so 5V straight
  across them is 0.84mA -- nowhere near enough to move the clapper (these
  coils expect ~90V/20Hz, i.e. ~15mA). The driver is therefore a push-pull
  step-up: BELL_A/BELL_B alternately ground the two halves of a small mains
  transformer's centre-tapped low-voltage winding (centre tap on 5V), and
  the mains-side winding feeds the bell. That gives a true bipolar drive
  (needed by a polarised ringer, whose armature must swing both ways) with
  NO high-voltage switching devices.

  T1 CHOICE (revised 2026-08-01: the part actually on hand is a Hammond
  161G24, SINGLE-primary 115V/60Hz-only -- not the dual-primary 160G24
  this design originally targeted). With only one primary there is no
  series-for-230V trick: ratio against the 12V half-winding is 115:12 =
  9.6:1, giving ~+/-48V and ~7.7mA ideal (~7mA realistic) -- audible but
  noticeably softer than the ~15mA original ringing spec. A dual-primary
  160G24 (10VA, 24V C.T. @ 450mA; Mouser 546-160G24) or Triad VPL24-210
  remain drop-in upgrades later for the full ~96V/~15mA original spec --
  series their two 115V primaries for 19:1; only T1's pin numbers change,
  firmware is identical.
  161G24 pinout (verified against Hammond's own connection diagram, not
  just the part-number table): secondary (LV, drive) jumper pins 4-5 =
  centre tap -> 5V; pin 3 -> Q2 drain, pin 6 -> Q3 drain. Primary (HV
  out, single winding, no jumper needed): pin 1 -> R18 220ohm -> bell
  RED, pin 2 -> BLACK.
  Bulk caps C7+C8 (2x 470uF/16V parallel) at the centre-tap 5V feed: the
  ring pulls bursts from 5V (smaller now, ~75mA vs the 160G24's ~300mA --
  output power scales with the square of the voltage ratio, and this
  ratio is half), so a self-powered USB hub is no longer strictly required
  but is still good practice.

  Why 30Hz and not 25Hz: peak flux scales as V/f, so a 5V square into a
  12V winding sits at 333/(hz*12) rated flux on a 60Hz-only-rated core
  like 161G24 (vs 277.5/(hz*12) for a 50/60Hz-rated core like 160G24).
  25Hz would be 1.11x rated (saturates); 30Hz is 0.93x, the same safety
  margin the original 160G24 design used at 25Hz. Real exchanges used
  20/25/30Hz, so 30Hz is still well inside the ringer's mechanical
  resonance band. Raise RING_FREQ_HZ further if the transformer buzzes.

  BELL_A and BELL_B are NEVER high at the same time -- a deadband of one
  poll tick (>=1ms) is inserted at every half-cycle transition, because
  energising both half-windings at once just burns current in opposing
  flux.

  SOFT-START: from zero flux, a full-length (20ms) first half-cycle would
  drive the core to ~1.86x rated flux (deep saturation, amp-class current
  spike, possible brownout right as the phone tries to ring). The first
  half-cycle after any idle period or inter-burst gap is therefore
  half-length (10ms), the textbook push-pull soft-start fix -- see
  bellFirstHalfCycle in bellStart()/bellUpdate().

  WATCHDOG: wdt_enable(WDTO_250MS) + a per-loop wdt_reset() guarantee that a
  firmware hang can never leave a bell gate latched HIGH indefinitely (the
  gate pulldowns R14/R15 only protect reset/Hi-Z, not a live-but-stuck pin).
  A .init3 handler clears MCUSR/disables the WDT immediately after any
  reset, because the 32u4's Caterina bootloader does not do this itself --
  without that guard, a watchdog-caused reset can loop forever in the
  bootloader instead of ever reaching setup().

  IR DETECTION THEORY: with a bare (2-leg) phototransistor there is no
  38kHz demodulator, so ambient light is rejected by SYNCHRONOUS sampling
  instead: read A0 with the emitter off, read it again with the emitter on,
  and use the difference. Slowly-varying room light cancels out. Because
  the emitter and detector sit next to each other on the board, there is
  always some direct optical crosstalk; that resting delta is measured once
  at boot (irBaseline) and the trigger threshold sits above it, making this
  a reflective proximity sensor -- wave a hand (or a retroreflector on the
  future remote) in front of the pair and the bell rings.

  NOTE for the future MCU-less remote: this synchronous scheme can only see
  light from OUR OWN emitter. To detect a foreign transmitter, swap the
  bare detector for a 3-leg 38kHz demodulator module (TSOP38238/VS1838B)
  and read it as a plain digital input -- the bell/hook/HID code here is
  unaffected.

  HID REPORT FORMAT: vendor-defined usage page 0xFF00, usage 0x01, single
  INPUT report with Report ID 1 (required by Arduino's HID.h/PluggableUSB
  for custom descriptors -- the original Pico firmware didn't need one).
  Wire bytes: [reportId=0x01][percent 0-100]. See host/volume_daemon.py,
  which now reads 2 bytes per report instead of 1.

  Serial monitoring note: do NOT open the CDC port at 1200 baud -- that is
  the touch-reset signal Arduino/avrdude use to jump into the bootloader
  for uploads, and will reset the board mid-session.

  Serial test commands (single characters): 'r' ring now, 's' stop ringing,
  'c' recalibrate the IR baseline.
*/

#include <HID.h>
#include <avr/wdt.h>

// The 32u4's Caterina bootloader does not clear MCUSR/disable the watchdog
// on its own, so a watchdog-caused reset can loop forever in the bootloader
// instead of ever reaching setup(). This runs in .init3, before global init,
// and clears it -- setup() re-enables the watchdog deliberately below.
void wdtEarlyDisable(void) __attribute__((naked)) __attribute__((section(".init3")));
void wdtEarlyDisable(void) {
  MCUSR = 0;
  wdt_disable();
}

// ---- Pin assignments ----
static const uint8_t SHUNT_PIN = 0;      // D0 / INT2 -- White pair, ext. 2.2k pull-up to 5V
static const uint8_t PULSE_PIN = 1;      // D1 / INT3 -- Blue pair, internal pull-up
static const uint8_t HOOK_PIN  = 7;      // D7 / INT6 -- Green/White pair, internal pull-up
static const uint8_t LED_SHUNT_PIN = 9;  // D9  -- dial off-normal indicator
static const uint8_t LED_PULSE_PIN = 10; // D10 -- mirrors raw pulse contact
static const uint8_t LED_HOOK_PIN  = 11; // D11 -- lit while on-hook (N3, muted)
static const uint8_t BELL_A_PIN = 2;     // D2  -- push-pull gate A (via R12)
static const uint8_t BELL_B_PIN = 3;     // D3  -- push-pull gate B (via R13)
static const uint8_t IR_TX_PIN  = 5;     // D5  -- IR emitter LED (via R10)
static const uint8_t IR_RX_PIN  = A0;    // A0  -- IR phototransistor emitter

// ---- Timing constants (ms) ----
static const unsigned long DEBOUNCE_MS = 15;       // dial contacts (SHUNT, PULSE)
static const unsigned long HOOK_DEBOUNCE_MS = 30;  // heavier spring-loaded lever
static const unsigned long POLL_MS = 1;            // main loop poll cadence

// ---- Bell ring generator ----
static const unsigned long RING_HALF_PERIOD_MS = 17;  // ~29.4Hz, 0.94x rated flux (161G24, 60Hz-only core)
static const unsigned long RING_DEADBAND_MS = 1;      // both gates low across a transition
static const unsigned long RING_BURST_MS = 2000;      // "ring" portion of the cadence
static const unsigned long RING_GAP_MS = 4000;        // "silence" portion
static const uint8_t RING_BURSTS = 2;                 // bursts per trigger

// ---- IR link ----
static const unsigned long IR_SAMPLE_INTERVAL_MS = 25;
static const unsigned int  IR_SETTLE_US = 200;   // emitter + phototransistor settling
static const uint8_t IR_CALIBRATION_SAMPLES = 32;
static const int IR_TRIGGER_MARGIN = 40;         // ADC counts above the resting delta
static const uint8_t IR_CONFIRM_SAMPLES = 3;     // consecutive hits needed to fire
static const unsigned long IR_LOCKOUT_MS = 5000; // ignore retriggers for this long
static const unsigned long IR_REPORT_INTERVAL_MS = 2000;

// ---- HID: vendor-defined usage page 0xFF00, usage 0x01 ----
// Report ID 1, single byte 0-100 = absolute target volume percent.
static const uint8_t HID_REPORT_DESCRIPTOR[] PROGMEM = {
  0x06, 0x00, 0xFF,  // Usage Page (Vendor Defined 0xFF00)
  0x09, 0x01,        // Usage (0x01)
  0xA1, 0x01,        // Collection (Application)
  0x85, 0x01,        //   Report ID (1)
  0x15, 0x00,        //   Logical Minimum (0)
  0x26, 0x64, 0x00,  //   Logical Maximum (100)
  0x75, 0x08,        //   Report Size (8)
  0x95, 0x01,        //   Report Count (1)
  0x09, 0x01,        //   Usage (0x01)
  0x81, 0x02,        //   Input (Data,Var,Abs)
  0xC0,              // End Collection
};

static bool sendVolumePercent(uint8_t percent) {
  if (percent > 100) percent = 100;
  return HID().SendReport(1, &percent, 1) == 1;
}

// ---- State ----
bool shuntAtRest = true;   // SHUNT pin HIGH == at rest
bool pulseClosed = false;  // PULSE pin LOW == closed (make)
bool onHook = false;       // HOOK pin LOW == pressed (on-hook)

unsigned long lastShuntChangeMs = 0;
unsigned long lastPulseChangeMs = 0;
unsigned long lastHookChangeMs = 0;
unsigned long lastPollMs = 0;

bool dialActive = false;
int makeCount = 0;
uint8_t lastVolumePercent = 50;

enum BellState : uint8_t { BELL_IDLE, BELL_BURST, BELL_GAP };
BellState bellState = BELL_IDLE;
uint8_t bellBurstsLeft = 0;
unsigned long bellCadenceStartMs = 0;  // start of the current burst or gap
unsigned long bellToggleMs = 0;        // start of the current half-cycle
bool bellPhaseB = false;               // which half-winding is next
bool bellInDeadband = false;
// Push-pull soft-start: from zero flux, a full-length first half-cycle would
// drive the core to ~1.86x rated flux (deep saturation, amp-class current
// spike, possible brownout). Halving only the first half-cycle after any
// idle/gap bounds it to ~0.93x, matching steady-state symmetry from the
// second half-cycle onward.
bool bellFirstHalfCycle = false;

int irBaseline = 0;
uint8_t irHits = 0;
unsigned long irLastSampleMs = 0;
unsigned long irLastTriggerMs = 0;
unsigned long irLastReportMs = 0;
int irLastDelta = 0;

static int digitToPercent(int digit) {
  return digit == 0 ? 100 : digit * 10;
}

// ---- Bell ----

static void bellGatesOff() {
  digitalWrite(BELL_A_PIN, LOW);
  digitalWrite(BELL_B_PIN, LOW);
}

static void bellStop() {
  bellGatesOff();
  bellState = BELL_IDLE;
  bellBurstsLeft = 0;
  bellInDeadband = false;
}

static void bellStart(unsigned long now) {
  if (!onHook) {  // never ring into a lifted handset
    Serial.println(F("*** BELL: refused, handset is off-hook ***"));
    return;
  }
  bellBurstsLeft = RING_BURSTS;
  bellState = BELL_BURST;
  bellCadenceStartMs = now;
  bellToggleMs = now;
  bellPhaseB = false;
  bellInDeadband = true;  // first half-cycle starts after one deadband tick
  bellFirstHalfCycle = true;
  bellGatesOff();
  Serial.println(F("*** BELL: ringing ***"));
}

static void bellUpdate(unsigned long now) {
  switch (bellState) {
    case BELL_IDLE:
      return;

    case BELL_GAP:
      if (now - bellCadenceStartMs >= RING_GAP_MS) {
        bellState = BELL_BURST;
        bellCadenceStartMs = now;
        bellToggleMs = now;
        bellInDeadband = true;
        bellFirstHalfCycle = true;
      }
      return;

    case BELL_BURST:
      if (now - bellCadenceStartMs >= RING_BURST_MS) {
        bellGatesOff();
        bellInDeadband = false;
        if (--bellBurstsLeft == 0) {
          bellState = BELL_IDLE;
          Serial.println(F("*** BELL: done ***"));
        } else {
          bellState = BELL_GAP;
          bellCadenceStartMs = now;
        }
        return;
      }
      {
        unsigned long thisHalfMs = bellFirstHalfCycle ? (RING_HALF_PERIOD_MS / 2) : RING_HALF_PERIOD_MS;
        if (now - bellToggleMs >= thisHalfMs) {
          bellGatesOff();
          bellToggleMs = now;
          bellPhaseB = !bellPhaseB;
          bellInDeadband = true;
          bellFirstHalfCycle = false;
        } else if (bellInDeadband && (now - bellToggleMs) >= RING_DEADBAND_MS) {
          digitalWrite(bellPhaseB ? BELL_B_PIN : BELL_A_PIN, HIGH);
          bellInDeadband = false;
        }
      }
      return;
  }
}

// ---- IR ----

// Ambient-cancelling sample: (detector with emitter on) - (emitter off).
static int irReadDelta() {
  digitalWrite(IR_TX_PIN, LOW);
  delayMicroseconds(IR_SETTLE_US);
  int dark = analogRead(IR_RX_PIN);
  digitalWrite(IR_TX_PIN, HIGH);
  delayMicroseconds(IR_SETTLE_US);
  int lit = analogRead(IR_RX_PIN);
  digitalWrite(IR_TX_PIN, LOW);
  return lit - dark;
}

static void irCalibrate() {
  long sum = 0;
  for (uint8_t i = 0; i < IR_CALIBRATION_SAMPLES; i++) sum += irReadDelta();
  irBaseline = (int)(sum / IR_CALIBRATION_SAMPLES);
  irHits = 0;
  Serial.print(F("IR baseline (emitter/detector crosstalk) = "));
  Serial.print(irBaseline);
  Serial.print(F(" counts; trigger above "));
  Serial.println(irBaseline + IR_TRIGGER_MARGIN);
}

void setup() {
  Serial.begin(115200);

  pinMode(SHUNT_PIN, INPUT);           // no internal pull -- external R3 does the job
  pinMode(PULSE_PIN, INPUT_PULLUP);
  pinMode(HOOK_PIN, INPUT_PULLUP);
  pinMode(LED_SHUNT_PIN, OUTPUT);
  pinMode(LED_PULSE_PIN, OUTPUT);
  pinMode(LED_HOOK_PIN, OUTPUT);
  pinMode(BELL_A_PIN, OUTPUT);
  pinMode(BELL_B_PIN, OUTPUT);
  pinMode(IR_TX_PIN, OUTPUT);
  digitalWrite(LED_SHUNT_PIN, LOW);
  digitalWrite(LED_PULSE_PIN, LOW);
  digitalWrite(LED_HOOK_PIN, LOW);
  bellGatesOff();
  digitalWrite(IR_TX_PIN, LOW);

  static HIDSubDescriptor node(HID_REPORT_DESCRIPTOR, sizeof(HID_REPORT_DESCRIPTOR));
  HID().AppendDescriptor(&node);

  shuntAtRest = digitalRead(SHUNT_PIN) == HIGH;
  pulseClosed = digitalRead(PULSE_PIN) == LOW;
  onHook = digitalRead(HOOK_PIN) == LOW;
  digitalWrite(LED_HOOK_PIN, onHook ? HIGH : LOW);

  Serial.println(F("Rotary dial decoder (Rev J, ItsyBitsy 32u4) + HID volume + IR bell ringer ready."));
  Serial.println(F("SHUNT=D0 (White, ext. 2.2kohm pull-up)  PULSE=D1 (Blue, int. pull-up)"));
  Serial.println(F("HOOK=D7 (Green/White, int. pull-up)  BELL=D2/D3  IR TX=D5  IR RX=A0"));
  Serial.println(F("Dial a digit and watch the log + LEDs. digit N -> N*10% volume (0 -> 100%)"));
  Serial.println(F("Lift handset to unmute/restore volume, replace handset to mute."));
  Serial.println(F("Serial commands: r = ring, s = stop ringing, c = recalibrate IR."));
  Serial.println(F("------------------------------------------------------------"));

  irCalibrate();

  if (onHook) {
    Serial.println(F("Startup state: ON-HOOK (muted)"));
    sendVolumePercent(0);
  } else {
    Serial.print(F("Startup state: OFF-HOOK, volume "));
    Serial.print(lastVolumePercent);
    Serial.println(F("%"));
    sendVolumePercent(lastVolumePercent);
  }

  wdt_enable(WDTO_250MS);  // a firmware hang can never leave a bell gate latched HIGH
}

void loop() {
  unsigned long now = millis();

  wdt_reset();

  // The ring generator gets serviced on every pass, not just on poll ticks,
  // so its 20ms half-cycles stay square.
  bellUpdate(now);

  if (now - lastPollMs < POLL_MS) return;
  lastPollMs = now;

  // --- SHUNT (dial off-normal) ---
  bool shuntNowAtRest = digitalRead(SHUNT_PIN) == HIGH;
  if (shuntNowAtRest != shuntAtRest && (now - lastShuntChangeMs) >= DEBOUNCE_MS) {
    lastShuntChangeMs = now;
    shuntAtRest = shuntNowAtRest;
    digitalWrite(LED_SHUNT_PIN, shuntAtRest ? LOW : HIGH);

    Serial.print(F("["));
    Serial.print(now);
    Serial.print(F("ms] SHUNT -> "));
    Serial.println(shuntAtRest ? F("AT REST") : F("OFF-NORMAL (dial moving)"));

    if (!shuntAtRest && !dialActive) {
      dialActive = true;
      makeCount = 0;
    } else if (shuntAtRest && dialActive) {
      dialActive = false;
      int digit = (makeCount == 10) ? 0 : makeCount;
      Serial.print(F(">>> DIALED DIGIT: "));
      Serial.print(digit);
      Serial.print(F(" ("));
      Serial.print(makeCount);
      Serial.println(F(" pulses)"));

      lastVolumePercent = digitToPercent(digit);
      if (onHook) {
        Serial.print(F("    -> ON-HOOK (muted); volume target updated to "));
        Serial.print(lastVolumePercent);
        Serial.println(F("% but held muted"));
      } else {
        bool ok = sendVolumePercent(lastVolumePercent);
        Serial.print(F("    -> HID volume report sent: "));
        Serial.print(lastVolumePercent);
        Serial.print(F("% (ok="));
        Serial.print(ok ? F("true") : F("false"));
        Serial.println(F(")"));
      }
    }
  }

  // --- PULSE (dial pulse contact) ---
  bool pulseNowClosed = digitalRead(PULSE_PIN) == LOW;
  if (pulseNowClosed != pulseClosed && (now - lastPulseChangeMs) >= DEBOUNCE_MS) {
    lastPulseChangeMs = now;
    pulseClosed = pulseNowClosed;
    digitalWrite(LED_PULSE_PIN, pulseClosed ? HIGH : LOW);

    Serial.print(F("["));
    Serial.print(now);
    Serial.print(F("ms] PULSE -> "));
    Serial.println(pulseClosed ? F("MAKE (closed)") : F("BREAK (open)"));

    if (dialActive && pulseClosed) {
      makeCount++;
    }
  }

  // --- HOOK (switchhook lever) ---
  bool hookNowClosed = digitalRead(HOOK_PIN) == LOW;
  if (hookNowClosed != onHook && (now - lastHookChangeMs) >= HOOK_DEBOUNCE_MS) {
    lastHookChangeMs = now;
    onHook = hookNowClosed;
    digitalWrite(LED_HOOK_PIN, onHook ? HIGH : LOW);

    if (onHook) {
      Serial.print(F("["));
      Serial.print(now);
      Serial.println(F("ms] HOOK -> ON-HOOK (handset down) -> MUTE"));
      sendVolumePercent(0);
    } else {
      Serial.print(F("["));
      Serial.print(now);
      Serial.print(F("ms] HOOK -> OFF-HOOK (handset lifted) -> RESTORE "));
      Serial.print(lastVolumePercent);
      Serial.println(F("%"));
      sendVolumePercent(lastVolumePercent);
      if (bellState != BELL_IDLE) {
        Serial.println(F("    -> handset answered, bell silenced"));
        bellStop();
      }
    }
  }

  // --- IR proximity / remote detection ---
  // Skipped while the bell is ringing: the sample blocks for ~0.6ms, which
  // would distort the ring waveform, and we are already ringing anyway.
  if (bellState == BELL_IDLE && (now - irLastSampleMs) >= IR_SAMPLE_INTERVAL_MS) {
    irLastSampleMs = now;
    irLastDelta = irReadDelta();

    if (irLastDelta > irBaseline + IR_TRIGGER_MARGIN) {
      if (irHits < IR_CONFIRM_SAMPLES) irHits++;
    } else {
      irHits = 0;
    }

    if (irHits >= IR_CONFIRM_SAMPLES && (now - irLastTriggerMs) >= IR_LOCKOUT_MS) {
      irLastTriggerMs = now;
      irHits = 0;
      Serial.print(F("["));
      Serial.print(now);
      Serial.print(F("ms] IR TRIGGER (delta "));
      Serial.print(irLastDelta);
      Serial.print(F(" vs baseline "));
      Serial.print(irBaseline);
      Serial.println(F(")"));
      bellStart(now);
    }
  }

  if ((now - irLastReportMs) >= IR_REPORT_INTERVAL_MS) {
    irLastReportMs = now;
    Serial.print(F("IR delta "));
    Serial.print(irLastDelta);
    Serial.print(F(" (baseline "));
    Serial.print(irBaseline);
    Serial.print(F(", trigger "));
    Serial.print(irBaseline + IR_TRIGGER_MARGIN);
    Serial.println(F(")"));
  }

  // --- Serial test commands ---
  while (Serial.available() > 0) {
    switch (Serial.read()) {
      case 'r': bellStart(now); break;
      case 's': bellStop(); Serial.println(F("*** BELL: stopped ***")); break;
      case 'c': irCalibrate(); break;
      default: break;
    }
  }
}

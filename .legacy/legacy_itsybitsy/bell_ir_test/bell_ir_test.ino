/*
  Bell + IR bring-up sketch for the Adafruit ItsyBitsy 32u4 (Rev J).

  Standalone diagnostic, in the same spirit as led_blink_test.ino and
  pin_monitor.ino: NO USB HID, no dial/hook state machine. Flash this
  first when bringing up the new ringer driver and IR pair so a fault can
  only be in the new hardware.

  WIRING (docs/rotary_dial_circuit_revL.svg):
    D5  IR_TX   -> R10 150ohm -> IR emitter LED anode; cathode to GND.
    A0  IR_RX   -> IR phototransistor emitter; collector to 5V;
                   R11 10kohm from this pin to GND.
    D2  BELL_A  -> R12 100ohm -> gate of Q2 = IRFZ44N (R14 10k gate-to-GND).
                   RC snubber R16 100ohm + C9 10nF, Q2 drain -> 5V tap.
    D3  BELL_B  -> R13 100ohm -> gate of Q3 = IRFZ44N (R15 10k gate-to-GND).
                   RC snubber R17 100ohm + C10 10nF, Q3 drain -> 5V tap.
    Q2/Q3 sources to GND, drains to the two ends of T1's centre-tapped
    low-voltage winding; centre tap to 5V. T1's mains-side winding -> R18
    220ohm (>=0.25W is plenty: ~53mW actual) -> bell RED and BLACK leads.
    Leave the bell's two GREY leads insulated and unconnected, as they
    were in the phone. C7+C8 (2x 470uF/16V in parallel, ~940uF) from the
    centre-tap 5V feed to GND: the ring pulls ~300mA bursts from 5V.

    T1 = Hammond 161G24: SINGLE-primary 115V/60Hz-only mains transformer
    (confirmed the part actually on hand -- NOT the dual-primary 160G24
    this design originally targeted), 24V C.T. low-voltage winding, run
    backwards. With only one primary there is no series-for-230V trick:
    ratio is 115:12 = 9.6:1, giving ~+/-48V, ~7.7mA ideal (~7mA realistic
    after winding DCR) -- audible but noticeably softer than the ~15mA
    original ringing spec. Swapping in a Hammond 160G24 later (series its
    two 115V primaries for 19:1, ~+/-96V/~15mA) is a drop-in upgrade: same
    firmware, only the T1 pin numbers below change (see revK.svg history).
    161G24 pinout (Hammond 161-schematic-rev2, verified against the actual
    datasheet drawing): secondary (LV, drive) jumper pins 4-5 = centre tap
    -> 5V; pin 3 -> Q2 drain, pin 6 -> Q3 drain. Primary (HV out, single
    winding, no jumper needed): pin 1 -> R18 -> bell RED, pin 2 -> BLACK.
    DMM check before power: R(3-6) ~ 2x R(3-4).

    Q2/Q3 = IRFZ44N (on hand): 55V, not true logic-level, but fine at 5V
    for this ~0.3A load. 55V is under the 60V rule, so the R16/R17+C9/C10
    snubbers above clamp the leakage turn-off spike; the part is also
    fully avalanche-rated as a backstop. See docs/rotary_dial_circuit_revM.svg.

  SAFETY: T1's high-voltage winding swings roughly +/-48V at ~7mA -- softer
  than a real phone line's jolt but still a real shock. It is isolated from
  USB and limited by R18 plus the 5.97k coil, but insulate it properly and
  do not probe it while ringing.

  Serial commands (115200 baud, one character each):
    r  ring the standard cadence (2s ring / 4s pause, 2 bursts)
    h  hold a continuous ring until 's' (for measuring / tuning)
    s  stop immediately
    a  drive BELL_A gate on only (DC) for 10ms -- half-winding continuity test
    b  drive BELL_B gate on only (DC) for 10ms -- half-winding continuity test
    i  print one IR sample (dark / lit / delta)
    c  recalibrate the IR baseline
    +  raise the ring frequency by 1Hz    - lower it by 1Hz

  Do NOT open this CDC port at 1200 baud: that is the bootloader
  touch-reset signal and will reset the board.
*/

static const uint8_t BELL_A_PIN = 2;
static const uint8_t BELL_B_PIN = 3;
static const uint8_t IR_TX_PIN  = 5;
static const uint8_t IR_RX_PIN  = A0;

static const unsigned long RING_DEADBAND_MS = 1;
static const unsigned long RING_BURST_MS = 2000;
static const unsigned long RING_GAP_MS = 4000;
static const uint8_t RING_BURSTS = 2;
static const unsigned int IR_SETTLE_US = 200;
static const uint8_t IR_CALIBRATION_SAMPLES = 32;
// DC continuity test: a transformer winding held at DC current is just its
// ~2ohm DCR -- 1s at 5V would ramp toward ~2.5A. 10ms keeps it on the
// inductive rise, well under 1A, while still confirming the gate/FET/winding
// path is alive (the DMM R(5-8)~=2xR(5-6) check already proves continuity
// unpowered; this is a quick powered sanity check, not a substitute for it).
static const unsigned long DC_TEST_MS = 10;

// 161G24's LV winding is rated 60Hz-only (flux ratio = 333/(hz*12) vs
// 277.5/(hz*12) for a 50/60Hz-rated core like 160G24) -- needs a higher
// default frequency to stay under saturation: 30Hz -> 0.93x rated flux,
// matching the same safety margin the 160G24 design used at 25Hz.
uint8_t ringFreqHz = 30;
unsigned long halfPeriodMs = 500 / 30;

enum Mode : uint8_t { IDLE, CADENCE_BURST, CADENCE_GAP, HOLD, DC_A, DC_B };
Mode mode = IDLE;
uint8_t burstsLeft = 0;
unsigned long modeStartMs = 0;
unsigned long toggleMs = 0;
bool phaseB = false;
bool inDeadband = false;
// Push-pull soft-start: from zero flux, a full-length first half-cycle would
// drive the core to ~1.86x rated flux (deep saturation, amp-class current
// spike). Halving only the first half-cycle's length bounds it to ~0.93x.
bool firstHalfCycle = false;

int irBaseline = 0;
unsigned long lastIrPrintMs = 0;

static void gatesOff() {
  digitalWrite(BELL_A_PIN, LOW);
  digitalWrite(BELL_B_PIN, LOW);
}

static void setRingFreq(uint8_t hz) {
  // 28Hz is the saturation floor for a 5V square into 161G24's 60Hz-only-
  // rated 12V half-winding (flux ratio = 27.75/hz, i.e. 333/(hz*12));
  // lower and the core saturates hard. (160G24's 50/60Hz-rated core floor
  // was 23Hz -- lower, since that core has more margin at a given freq.)
  if (hz < 28) hz = 28;
  if (hz > 40) hz = 40;
  ringFreqHz = hz;
  halfPeriodMs = 500UL / hz;
  Serial.print(F("ring frequency = "));
  Serial.print(ringFreqHz);
  Serial.print(F("Hz (half period "));
  Serial.print(halfPeriodMs);
  Serial.println(F("ms)"));
}

static void startOscillation(Mode m, unsigned long now) {
  mode = m;
  modeStartMs = now;
  toggleMs = now;
  phaseB = false;
  inDeadband = true;
  firstHalfCycle = true;  // soft-start: first half-cycle from idle is half-length
  burstsLeft = (m == CADENCE_BURST) ? RING_BURSTS : 0;
  gatesOff();
}

static void stopAll() {
  gatesOff();
  mode = IDLE;
  inDeadband = false;
  Serial.println(F("stopped"));
}

static void oscillate(unsigned long now) {
  unsigned long thisHalfMs = firstHalfCycle ? (halfPeriodMs / 2) : halfPeriodMs;
  if (now - toggleMs >= thisHalfMs) {
    gatesOff();
    toggleMs = now;
    phaseB = !phaseB;
    inDeadband = true;
    firstHalfCycle = false;
  } else if (inDeadband && (now - toggleMs) >= RING_DEADBAND_MS) {
    digitalWrite(phaseB ? BELL_B_PIN : BELL_A_PIN, HIGH);
    inDeadband = false;
  }
}

static int irReadDelta(int *darkOut, int *litOut) {
  digitalWrite(IR_TX_PIN, LOW);
  delayMicroseconds(IR_SETTLE_US);
  int dark = analogRead(IR_RX_PIN);
  digitalWrite(IR_TX_PIN, HIGH);
  delayMicroseconds(IR_SETTLE_US);
  int lit = analogRead(IR_RX_PIN);
  digitalWrite(IR_TX_PIN, LOW);
  if (darkOut) *darkOut = dark;
  if (litOut) *litOut = lit;
  return lit - dark;
}

static void irCalibrate() {
  long sum = 0;
  for (uint8_t i = 0; i < IR_CALIBRATION_SAMPLES; i++) sum += irReadDelta(NULL, NULL);
  irBaseline = (int)(sum / IR_CALIBRATION_SAMPLES);
  Serial.print(F("IR baseline (direct emitter->detector crosstalk) = "));
  Serial.println(irBaseline);
}

void setup() {
  Serial.begin(115200);
  pinMode(BELL_A_PIN, OUTPUT);
  pinMode(BELL_B_PIN, OUTPUT);
  pinMode(IR_TX_PIN, OUTPUT);
  gatesOff();
  digitalWrite(IR_TX_PIN, LOW);
  setRingFreq(ringFreqHz);
  irCalibrate();
}

void loop() {
  unsigned long now = millis();

  switch (mode) {
    case HOLD:
      oscillate(now);
      break;
    case CADENCE_BURST:
      if (now - modeStartMs >= RING_BURST_MS) {
        gatesOff();
        inDeadband = false;
        if (--burstsLeft == 0) {
          mode = IDLE;
          Serial.println(F("cadence done"));
        } else {
          mode = CADENCE_GAP;
          modeStartMs = now;
        }
      } else {
        oscillate(now);
      }
      break;
    case CADENCE_GAP:
      if (now - modeStartMs >= RING_GAP_MS) {
        mode = CADENCE_BURST;
        modeStartMs = now;
        toggleMs = now;
        inDeadband = true;
      }
      break;
    case DC_A:
    case DC_B:
      if (now - modeStartMs >= DC_TEST_MS) {
        gatesOff();
        mode = IDLE;
        Serial.println(F("DC test done"));
      }
      break;
    case IDLE:
      break;
  }

  if (mode == IDLE && (now - lastIrPrintMs) >= 1000) {
    lastIrPrintMs = now;
    int dark, lit;
    int delta = irReadDelta(&dark, &lit);
    Serial.print(F("IR dark="));
    Serial.print(dark);
    Serial.print(F(" lit="));
    Serial.print(lit);
    Serial.print(F(" delta="));
    Serial.print(delta);
    Serial.print(F(" (baseline "));
    Serial.print(irBaseline);
    Serial.println(F(")"));
  }

  while (Serial.available() > 0) {
    char c = Serial.read();
    switch (c) {
      case 'r':
        Serial.println(F("cadence ring"));
        startOscillation(CADENCE_BURST, now);
        break;
      case 'h':
        Serial.println(F("continuous ring until 's'"));
        startOscillation(HOLD, now);
        break;
      case 's':
        stopAll();
        break;
      case 'a':
        Serial.println(F("DC on BELL_A gate for 10ms"));
        gatesOff();
        mode = DC_A;
        modeStartMs = now;
        digitalWrite(BELL_A_PIN, HIGH);
        break;
      case 'b':
        Serial.println(F("DC on BELL_B gate for 10ms"));
        gatesOff();
        mode = DC_B;
        modeStartMs = now;
        digitalWrite(BELL_B_PIN, HIGH);
        break;
      case 'i': {
        int dark, lit;
        int delta = irReadDelta(&dark, &lit);
        Serial.print(F("dark="));
        Serial.print(dark);
        Serial.print(F(" lit="));
        Serial.print(lit);
        Serial.print(F(" delta="));
        Serial.println(delta);
        break;
      }
      case 'c':
        irCalibrate();
        break;
      case '+':
        setRingFreq(ringFreqHz + 1);
        break;
      case '-':
        setRingFreq(ringFreqHz - 1);
        break;
      default:
        break;
    }
  }
}

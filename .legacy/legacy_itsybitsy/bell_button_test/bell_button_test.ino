/*
  Bell ring-generator button test for the Adafruit ItsyBitsy 32u4.

  Same push-pull driver as firmware/bell_ir_test/bell_ir_test.ino, but
  triggered by a physical momentary pushbutton instead of a serial
  command -- no need to fight arduino-cli monitor's line buffering to
  get a ring going. No IR, no HID: just the bell driver + a button.

  WIRING (in addition to the existing BELL_A/BELL_B/T1/Q2/Q3 wiring,
  unchanged from bell_ir_test.ino -- see that file's header for the full
  R12-R18/C9/C10 detail):
    D12 BUTTON  -> one leg of a momentary pushbutton; other leg -> GND.
                   No external resistor needed (internal pull-up used).
                   Find D12 by its SILKSCREEN LABEL printed next to the
                   hole (same long edge as D2/D3/D5) -- do not count header
                   positions, that's the exact mistake the D4/D6/D8
                   short-edge gotcha was about.

  DIAGNOSTICS (added because the button "had no effect" last round):
    - The onboard red D13 LED lights for as long as the driver thinks the
      button is held, so you can confirm the MCU sees the press WITHOUT
      trusting the serial monitor or the DMM at all. If this LED never
      lights while you hold the button, the fault is between the button
      and D12 (wrong pin, bad joint, dead switch) -- stop there, the
      transformer stage is not the problem yet.
    - A once-a-second heartbeat line prints the raw (undebounced) D12
      reading, the debounced pressed state, and the ringing state, so you
      can watch the sketch is actually alive and see bounce/noise on the
      pin directly.

  BENCH TEST PROCEDURE (bell NOT yet connected -- see
  docs/bell_bench_test_setup.svg):
    1. Multimeter set to AC VOLTS (auto-range), leads across the R18 ->
       RED/BLACK gap (TP-B in the bench diagram) in place of the bell.
    2. Power the board, open this sketch's serial monitor if you want the
       status prints, but you do NOT need to type anything into it.
    3. Press and HOLD the button. The driver free-runs continuously
       (like the old 'h' command) for as long as it's held, so the DMM
       has time to settle on a stable AC reading -- expect roughly
       30-40Vac on the 161G24 (well under its ~48Vpk swing, since a DMM's
       AC volts reading is calibrated for sine waves, not this square-ish
       drive -- a non-zero, non-trivial reading is what you're checking
       for, not an exact number).
    4. Release the button to stop. Only reconnect the bell once you see
       a real non-zero reading here.

  SAFETY: same as bell_ir_test.ino -- T1's HV winding swings roughly
  +/-48V. Isolated from USB and current-limited by R18 + the bell coil,
  but don't probe it while ringing, and insulate the HV side properly.

  Do NOT open this CDC port at 1200 baud: that is the bootloader
  touch-reset signal and will reset the board.
*/

static const uint8_t BELL_A_PIN = 2;
static const uint8_t BELL_B_PIN = 3;
static const uint8_t BUTTON_PIN = 12;
static const uint8_t LED_PIN = LED_BUILTIN;  // onboard red D13 LED

static const unsigned long RING_DEADBAND_MS = 1;
static const unsigned long BUTTON_DEBOUNCE_MS = 30;
static const unsigned long HEARTBEAT_MS = 1000;
unsigned long lastHeartbeatMs = 0;

// 161G24's LV winding is 60Hz-only rated -- 30Hz keeps flux ~0.93x rated
// (see bell_ir_test.ino for the full derivation).
uint8_t ringFreqHz = 30;
unsigned long halfPeriodMs = 500 / 30;

bool ringing = false;
unsigned long toggleMs = 0;
bool phaseB = false;
bool inDeadband = false;
// Push-pull soft-start: first half-cycle from zero flux is half-length to
// avoid the ~1.86x rated flux spike a full-length first cycle would cause.
bool firstHalfCycle = false;

bool buttonPressed = false;
bool buttonReadingLast = false;
unsigned long buttonLastChangeMs = 0;

static void gatesOff() {
  digitalWrite(BELL_A_PIN, LOW);
  digitalWrite(BELL_B_PIN, LOW);
}

static void startRinging(unsigned long now) {
  ringing = true;
  toggleMs = now;
  phaseB = false;
  inDeadband = true;
  firstHalfCycle = true;
  gatesOff();
  digitalWrite(LED_PIN, HIGH);
  Serial.println(F("ring: ON"));
}

static void stopRinging() {
  ringing = false;
  gatesOff();
  inDeadband = false;
  digitalWrite(LED_PIN, LOW);
  Serial.println(F("ring: OFF"));
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

void setup() {
  Serial.begin(115200);
  pinMode(BELL_A_PIN, OUTPUT);
  pinMode(BELL_B_PIN, OUTPUT);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(LED_PIN, OUTPUT);
  gatesOff();
  digitalWrite(LED_PIN, LOW);
  Serial.println(F("bell_button_test ready -- hold the button to ring"));
}

void loop() {
  unsigned long now = millis();

  bool reading = (digitalRead(BUTTON_PIN) == LOW);  // pressed = LOW
  if (reading != buttonReadingLast) {
    buttonLastChangeMs = now;
    buttonReadingLast = reading;
  }
  if ((now - buttonLastChangeMs) >= BUTTON_DEBOUNCE_MS && reading != buttonPressed) {
    buttonPressed = reading;
    if (buttonPressed && !ringing) {
      startRinging(now);
    } else if (!buttonPressed && ringing) {
      stopRinging();
    }
  }

  if (ringing) {
    oscillate(now);
  }

  if (now - lastHeartbeatMs >= HEARTBEAT_MS) {
    lastHeartbeatMs = now;
    Serial.print(F("heartbeat: button_raw="));
    Serial.print(reading);
    Serial.print(F(" pressed="));
    Serial.print(buttonPressed);
    Serial.print(F(" ringing="));
    Serial.println(ringing);
  }
}

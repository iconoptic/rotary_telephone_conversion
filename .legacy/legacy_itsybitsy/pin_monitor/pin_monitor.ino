/*
  Diagnostic sketch -- whole-header pin scanner + D7 pin health self-test.

  Rev 3. Rev 2 proved D7's silicon pad is healthy yet nothing external
  ever reached it, while a grounding touch aimed at "D7" showed up on D0
  instead. The ItsyBitsy's long header is numbered 0,1,2,3,5,7,9,10,11,
  12,13 -- pins 4, 6 and 8 live on the short edge -- so counting positions
  silently lands on the wrong pin.

  So this version stops trusting pin identification entirely: it watches
  EVERY free GPIO at once with pull-ups enabled, and reports which pin
  number actually changed. Ground a pin and the board names it for you.

  Latching is kept from rev 2 -- once a pin is seen LOW that is remembered
  with a timestamp, so test timing does not matter. The periodic D7
  drive-low readback self-test is also kept.

  Read at 115200 baud. NEVER open this port at 1200 baud (bootloader
  touch-reset).
*/

static const uint8_t SHUNT_PIN = 0;
static const uint8_t PULSE_PIN = 1;
static const uint8_t HOOK_PIN  = 7;
static const uint8_t LED_SHUNT_PIN = 9;
static const uint8_t LED_PULSE_PIN = 10;
static const uint8_t LED_HOOK_PIN  = 11;

// Every broken-out GPIO except the three LED outputs and D12 (driven LOW
// below as a known-good ground reference). A0..A5 are 18..23.
static const uint8_t SCAN_PINS[] = {0, 1, 2, 3, 5, 7, 13, 18, 19, 20, 21, 22, 23};
static const char *const SCAN_NAMES[] = {
  "D0(SHUNT)", "D1(PULSE)", "D2", "D3", "D5", "D7(HOOK)", "D13",
  "A0", "A1", "A2", "A3", "A4", "A5"
};
static const uint8_t NSCAN = sizeof(SCAN_PINS) / sizeof(SCAN_PINS[0]);

// Driven LOW so a jumper from D7 to D12 tests D7's input path using the
// MCU's own ground -- no breadboard rail involved.
static const uint8_t VIRTUAL_GND_PIN = 12;

static const unsigned long HEARTBEAT_MS = 1000;
static const unsigned long SELFTEST_INTERVAL_MS = 15000;

int lastLvl[NSCAN];
unsigned int edges[NSCAN];
bool everLow[NSCAN];
unsigned long firstLowMs[NSCAN];
unsigned long lastHeartbeat = 0;
unsigned long lastSelfTest = 0;

// Drives D7 low and reads the pad back. This never leaves the die, so it
// clears the silicon without saying anything about the header joint.
static void hookPinSelfTest() {
  pinMode(HOOK_PIN, OUTPUT);
  digitalWrite(HOOK_PIN, LOW);
  delay(5);
  int driven = digitalRead(HOOK_PIN);
  pinMode(HOOK_PIN, INPUT_PULLUP);
  delay(5);
  int pulled = digitalRead(HOOK_PIN);

  Serial.print(F("D7 SELF-TEST: driven-LOW readback="));
  Serial.print(driven == LOW ? F("LOW") : F("HIGH"));
  Serial.print(F("  internal-pullup="));
  Serial.print(pulled == HIGH ? F("HIGH") : F("LOW"));
  Serial.println(driven == LOW ? F("   => pad OK") : F("   => PAD DAMAGED"));
}

void setup() {
  Serial.begin(115200);

  for (uint8_t i = 0; i < NSCAN; i++) {
    pinMode(SCAN_PINS[i], SCAN_PINS[i] == SHUNT_PIN ? INPUT : INPUT_PULLUP);
    lastLvl[i] = -1;
    edges[i] = 0;
    everLow[i] = false;
    firstLowMs[i] = 0;
  }

  pinMode(LED_SHUNT_PIN, OUTPUT);
  pinMode(LED_PULSE_PIN, OUTPUT);
  pinMode(LED_HOOK_PIN, OUTPUT);
  digitalWrite(LED_SHUNT_PIN, HIGH);
  digitalWrite(LED_PULSE_PIN, HIGH);
  digitalWrite(LED_HOOK_PIN, HIGH);
  delay(600);
  digitalWrite(LED_SHUNT_PIN, LOW);
  digitalWrite(LED_PULSE_PIN, LOW);
  digitalWrite(LED_HOOK_PIN, LOW);

  pinMode(VIRTUAL_GND_PIN, OUTPUT);
  digitalWrite(VIRTUAL_GND_PIN, LOW);

  Serial.println(F("=== pin_monitor rev4: scanner + D12 virtual ground ==="));
  Serial.println(F("D12 is driven LOW. Jumper D7 -> D12 (both on the MCU header) to test"));
  Serial.println(F("D7's input path without touching any breadboard ground rail."));
}

void loop() {
  unsigned long now = millis();

  if (now - lastSelfTest >= SELFTEST_INTERVAL_MS) {
    lastSelfTest = now;
    hookPinSelfTest();
  }

  for (uint8_t i = 0; i < NSCAN; i++) {
    int lvl = digitalRead(SCAN_PINS[i]);
    if (lvl != lastLvl[i]) {
      if (lastLvl[i] != -1) {
        edges[i]++;
        Serial.print(F("["));
        Serial.print(now);
        Serial.print(F("ms] "));
        Serial.print(SCAN_NAMES[i]);
        Serial.print(lvl == LOW ? F(" -> LOW ") : F(" -> HIGH"));
        Serial.print(F("   (edges="));
        Serial.print(edges[i]);
        Serial.println(F(")"));
      }
      if (lvl == LOW && !everLow[i]) { everLow[i] = true; firstLowMs[i] = now; }
      lastLvl[i] = lvl;
    }
  }

  digitalWrite(LED_SHUNT_PIN, digitalRead(SHUNT_PIN) == LOW ? HIGH : LOW);
  digitalWrite(LED_PULSE_PIN, digitalRead(PULSE_PIN) == LOW ? HIGH : LOW);
  digitalWrite(LED_HOOK_PIN, digitalRead(HOOK_PIN) == LOW ? HIGH : LOW);

  if (now - lastHeartbeat >= HEARTBEAT_MS) {
    lastHeartbeat = now;
    Serial.print(F("["));
    Serial.print(now);
    Serial.print(F("ms] ever-LOW so far:"));
    bool any = false;
    for (uint8_t i = 0; i < NSCAN; i++) {
      if (everLow[i]) {
        any = true;
        Serial.print(F(" "));
        Serial.print(SCAN_NAMES[i]);
        Serial.print(F("@"));
        Serial.print(firstLowMs[i]);
        Serial.print(F("ms"));
      }
    }
    if (!any) Serial.print(F(" (none)"));
    Serial.print(F("   | D7 now="));
    Serial.println(digitalRead(HOOK_PIN) == LOW ? F("LOW") : F("HIGH"));
  }
}

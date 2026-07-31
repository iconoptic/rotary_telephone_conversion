/*
  Sanity-check sketch: just blink all three diagnostic LEDs, no dial logic
  at all. Port of legacy_pico/led_blink_test.py for the ItsyBitsy 32u4.

  Use this to confirm LED wiring/polarity/resistors are correct BEFORE
  trying to interpret any dial behavior. If the LEDs don't cycle in order
  here, the problem is in the LED wiring, not the dial/hook decoding logic
  in rotary_volume.ino.

  Wiring:
    LED A -> D9  -> 330ohm resistor -> LED -> GND (mirrors LED_SHUNT)
    LED B -> D10 -> 330ohm resistor -> LED -> GND (mirrors LED_PULSE)
    LED C -> D11 -> 330ohm resistor -> LED -> GND (mirrors LED_HOOK, new)
*/

static const uint8_t LED_A_PIN = 9;
static const uint8_t LED_B_PIN = 10;
static const uint8_t LED_C_PIN = 11;

void setup() {
  Serial.begin(115200);
  pinMode(LED_A_PIN, OUTPUT);
  pinMode(LED_B_PIN, OUTPUT);
  pinMode(LED_C_PIN, OUTPUT);
  Serial.println(F("LED sanity check running: LED A, B, C should cycle in order every 500ms."));
}

void loop() {
  digitalWrite(LED_A_PIN, HIGH);
  digitalWrite(LED_B_PIN, LOW);
  digitalWrite(LED_C_PIN, LOW);
  delay(500);
  digitalWrite(LED_A_PIN, LOW);
  digitalWrite(LED_B_PIN, HIGH);
  digitalWrite(LED_C_PIN, LOW);
  delay(500);
  digitalWrite(LED_A_PIN, LOW);
  digitalWrite(LED_B_PIN, LOW);
  digitalWrite(LED_C_PIN, HIGH);
  delay(500);
}

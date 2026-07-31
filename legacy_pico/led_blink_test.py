"""
Sanity-check script: just blink both diagnostic LEDs, no dial logic at all.

Use this to confirm LED wiring/polarity/resistors are correct BEFORE trying
to interpret any dial behavior. If both LEDs don't blink alternately here,
the problem is in the LED wiring, not the dial-decoding logic.

Wiring:
  LED A -> GP14 (physical pin 19) -> 330ohm resistor -> LED -> GND
  LED B -> GP15 (physical pin 20) -> 330ohm resistor -> LED -> GND
"""

import time
from machine import Pin

LED_A_PIN = 14
LED_B_PIN = 15

led_a = Pin(LED_A_PIN, Pin.OUT)
led_b = Pin(LED_B_PIN, Pin.OUT)

print("LED sanity check running: LED A and LED B should alternate every 500ms.")
print("Press Ctrl-C to stop.")

while True:
    led_a.value(1)
    led_b.value(0)
    time.sleep_ms(500)
    led_a.value(0)
    led_b.value(1)
    time.sleep_ms(500)

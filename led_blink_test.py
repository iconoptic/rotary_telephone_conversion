"""
Sanity-check script: just cycle all three diagnostic LEDs, no dial logic at
all. Use this to confirm LED wiring/polarity/resistors are correct BEFORE
trying to interpret any dial/hook behavior.

Wiring:
  LED_SHUNT -> GP14 (physical pin 19) -> 330ohm resistor -> LED -> GND
  LED_PULSE -> GP15 (physical pin 20) -> 330ohm resistor -> LED -> GND
  LED_HOOK  -> GP16 (physical pin 21) -> 330ohm resistor -> LED -> GND
              (NEW this revision -- no Pico equivalent existed before)
"""

import time
from machine import Pin

LED_SHUNT_PIN = 14
LED_PULSE_PIN = 15
LED_HOOK_PIN = 16

leds = [Pin(LED_SHUNT_PIN, Pin.OUT), Pin(LED_PULSE_PIN, Pin.OUT), Pin(LED_HOOK_PIN, Pin.OUT)]

print("LED sanity check running: SHUNT/PULSE/HOOK LEDs should light one at a time.")
print("Press Ctrl-C to stop.")

i = 0
while True:
    for idx, led in enumerate(leds):
        led.value(1 if idx == i else 0)
    time.sleep_ms(500)
    i = (i + 1) % len(leds)

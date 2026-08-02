Read [](file:///home/btgrant/Projects/vintage_headset/docs/rotary_dial_circuit_revM.svg#1-1), lines 1 to 150

Read memory [](file:///home/btgrant/.config/Code/User/workspaceStorage/5c33566817f67465e287c4b457436175/GitHub.copilot-chat/memory-tool/memories/repo/vintage_headset.md)

Searched for regex `Q2|Q3|IRFZ44N|snubber|T1|centre tap|161G24` (`**/docs/rotary_dial_circuit_revM.svg`), 36 results

Read [](file:///home/btgrant/Projects/vintage_headset/docs/bell_bench_test_setup.svg)

Read [](file:///home/btgrant/Projects/vintage_headset/docs/rotary_dial_circuit_revM.svg#360-360), lines 360 to 500

Viewed image [](file:///home/btgrant/Projects/vintage_headset/docs/bell_bench_test_setup.png)

Now I'll add G/S/D pin labels to Q2/Q3 in the main schematic, and bring the bench-test diagram's Q2/Q3/T1 labeling in line with it (pin numbers, N-ch line, red IRFZ44N color, G/S/D letters). 

Replacing 81 lines with 100 lines in [](file:///home/btgrant/Projects/vintage_headset/docs/rotary_dial_circuit_revM.svg), [](file:///home/btgrant/Projects/vintage_headset/docs/bell_bench_test_setup.svg)


```

```

```

```
Now let's render both and verify no overlaps. 

Ran terminal command:  cd /home/btgrant/Projects/vintage_headset/docs && rsvg-convert -w 1300 -h 980 bell_bench_test_setup.svg -o /tmp/bench_v2.png && python3 -c "
from PIL import Image
im = Image.open('/tmp/bench_v2.png').convert('RGB')
im.crop((0,100,260,240)).resize((780,420)).save('/tmp/q2_crop.png')
im.crop((0,470,260,630)).resize((780,480)).save('/tmp/q3_crop.png')
im.crop((350,140,700,420)).resize((1050,840)).save('/tmp/t1_crop.png')
"

Completed with input:  cd /home/btgrant/Projects/vintage_headset/docs && rsvg-convert -w 1300 -h 980 bell_bench_test_setup.svg -o /tmp/bench_v2.png && python3 -c "
from PIL import Image
im = Image.open('/tmp/bench_v2.png').convert('RGB')
im.crop((0,100,260,240)).resize((780,420)).save('/tmp/q2_crop.png')
im.crop((0,470,260,630)).resize((780,480)).save('/tmp/q3_crop.png')
im.crop((350,140,700,420)).resize((1050,840)).save('/tmp/t1_crop.png')
"


Compacted conversation

Viewed image [](file:///tmp/q2_crop.png)

Viewed image [](file:///tmp/q3_crop.png)

Viewed image [](file:///tmp/t1_crop.png)

Found an overlap: the new "pins 4+5 (jumpered)" line collides with the HV coil's leftward bulge. Q2/Q3 boxes look clean though. Let me fix the T1 label positioning. 

Replacing 2 lines with 2 lines in [](file:///home/btgrant/Projects/vintage_headset/docs/bell_bench_test_setup.svg)


```

```


Ran terminal command:  cd /home/btgrant/Projects/vintage_headset/docs && rsvg-convert -w 1300 -h 980 bell_bench_test_setup.svg -o /tmp/bench_v3.png && python3 -c "
from PIL import Image
im = Image.open('/tmp/bench_v3.png').convert('RGB')
im.crop((250,140,650,420)).resize((1200,840)).save('/tmp/t1_crop2.png')
"

Completed with input:  cd /home/btgrant/Projects/vintage_headset/docs && rsvg-convert -w 1300 -h 980 bell_bench_test_setup.svg -o /tmp/bench_v3.png && python3 -c "
from PIL import Image
im = Image.open('/tmp/bench_v3.png').convert('RGB')
im.crop((250,140,650,420)).resize((1200,840)).save('/tmp/t1_crop2.png')
"


Viewed image [](file:///tmp/t1_crop2.png)

Read [](file:///home/btgrant/Projects/vintage_headset/docs/bell_bench_test_setup.svg#1-1), lines 1 to 40

Read [](file:///home/btgrant/Projects/vintage_headset/docs/bell_bench_test_setup.svg#40-40), lines 40 to 90

The corridor between the two coils is too narrow for a second text line at any position — I'll drop that line from the diagram (and just explain the pin 4/5 jumper detail in chat instead), keeping the original single "centre tap (5V)" label. 

Replacing 2 lines with 1 lines in [](file:///home/btgrant/Projects/vintage_headset/docs/bell_bench_test_setup.svg)


```

```
Now let's re-render and verify this area plus do a full-page overlap scan, and check the main schematic's Q2/Q3 too. 

Ran terminal command:  cd /home/btgrant/Projects/vintage_headset/docs && rsvg-convert -w 1300 -h 980 bell_bench_test_setup.svg -o /tmp/bench_v4.png && rsvg-convert -w 1600 -h 3060 rotary_dial_circuit_revM.svg -o /tmp/main_v2.png && python3 -c "
from PIL import Image
im = Image.open('/tmp/bench_v4.png').convert('RGB')
im.crop((250,140,650,420)).resize((1200,840)).save('/tmp/t1_crop3.png')
m = Image.open('/tmp/main_v2.png').convert('RGB')
m.crop((750,1420,1100,1560)).resize((1400,560)).save('/tmp/main_q2_crop.png')
m.crop((750,1560,1100,1700)).resize((1400,560)).save('/tmp/main_q3_crop.png')
"

Completed with input:  cd /home/btgrant/Projects/vintage_headset/docs && rsvg-convert -w 1300 -h 980 bell_bench_test_setup.svg -o /tmp/bench_v4.png && rsvg-convert -w 1600 -h 3060 rotary_dial_circuit_revM.svg -o /tmp/main_v2.png && python3 -c "
from PIL import Image
im = Image.open('/tmp/bench_v4.png').convert('RGB')
im.crop((250,140,650,420)).resize((1200,840)).save('/tmp/t1_crop3.png')
m = Image.open('/tmp/main_v2.png').convert('RGB')
m.crop((750,1420,1100,1560)).resize((1400,560)).save('/tmp/main_q2_crop.png')
m.crop((750,1560,1100,1700)).resize((1400,560)).save('/tmp/main_q3_crop.png')
"


Viewed image [](file:///tmp/t1_crop3.png)

Viewed image [](file:///tmp/main_q2_crop.png)

Viewed image [](file:///tmp/main_q3_crop.png)

Everything renders clean now — no overlaps in either diagram. Let's sync the `.svg.txt` mirrors. 

Ran terminal command:  cp rotary_dial_circuit_revM.svg rotary_dial_circuit_revM.svg.txt && cp bell_bench_test_setup.svg bell_bench_test_setup.svg.txt && rsvg-convert -w 1600 -h 3060 rotary_dial_circuit_revM.svg -o rotary_dial_circuit_revM.png && rsvg-convert -w 1300 -h 980 bell_bench_test_setup.svg -o bell_bench_test_setup.png && echo DONE

Now let me update repo memory with this round's changes. 

Read memory [](file:///home/btgrant/.config/Code/User/workspaceStorage/5c33566817f67465e287c4b457436175/GitHub.copilot-chat/memory-tool/memories/repo/vintage_headset.md)

No matches found. Your search pattern might be excluded completely by either the search.exclude settings or .*ignore files.
If you believe that it should have results, you can check into the .*ignore files and the exclude setting (here are some excluded patterns for reference:[**/node_modules,**/bower_components,**/*.code-search]).
Then if you want to include those files you can call the tool again by setting "includeIgnoredFiles" to true.

Read memory [](file:///home/btgrant/.config/Code/User/workspaceStorage/5c33566817f67465e287c4b457436175/GitHub.copilot-chat/memory-tool/memories/repo/vintage_headset.md)

Read memory [](file:///home/btgrant/.config/Code/User/workspaceStorage/5c33566817f67465e287c4b457436175/GitHub.copilot-chat/memory-tool/memories/repo/vintage_headset.md)

Read memory [](file:///home/btgrant/.config/Code/User/workspaceStorage/5c33566817f67465e287c4b457436175/GitHub.copilot-chat/memory-tool/memories/repo/vintage_headset.md)

Ran terminal command:  wc -l /home/btgrant/Projects/vintage_headset/.git 2>/dev/null; find / -maxdepth 0; echo "---"; 

Read memory [](file:///home/btgrant/.config/Code/User/workspaceStorage/5c33566817f67465e287c4b457436175/GitHub.copilot-chat/memory-tool/memories/repo/vintage_headset.md)

Searched for regex `REV M|Rev M|BENCH TEST|bell_bench_test_setup|IRFZ44N|G/S/D` (`vintage_headset`), 71 results

Read memory [](file:///home/btgrant/.config/Code/User/workspaceStorage/5c33566817f67465e287c4b457436175/GitHub.copilot-chat/memory-tool/memories/repo/vintage_headset.md)

Read memory [](file:///home/btgrant/.config/Code/User/workspaceStorage/5c33566817f67465e287c4b457436175/GitHub.copilot-chat/memory-tool/memories/repo/vintage_headset.md)

Read memory [](file:///home/btgrant/.config/Code/User/workspaceStorage/5c33566817f67465e287c4b457436175/GitHub.copilot-chat/memory-tool/memories/repo/vintage_headset.md)

Read memory [](file:///home/btgrant/.config/Code/User/workspaceStorage/5c33566817f67465e287c4b457436175/GitHub.copilot-chat/memory-tool/memories/repo/vintage_headset.md)

Read memory [](file:///home/btgrant/.config/Code/User/workspaceStorage/5c33566817f67465e287c4b457436175/GitHub.copilot-chat/memory-tool/memories/repo/vintage_headset.md)

Found the true end of the file. Now appending the new entry. 

Updated memory file [](file:///home/btgrant/.config/Code/User/workspaceStorage/5c33566817f67465e287c4b457436175/GitHub.copilot-chat/memory-tool/memories/repo/vintage_headset.md)

Now the primary deliverable: a detailed, beginner-friendly explanation of the bench test procedure and how it differs from the normal schematic connections. 

Read [](file:///home/btgrant/Projects/vintage_headset/docs/bell_bench_test_setup.svg#100-100), lines 100 to 148

Both diagrams are updated, verified overlap-free, rendered, and the `.svg.txt` mirrors are back in sync. Here's the full explanation you asked for.

## The two diagrams' *starting connections* — what's different, and why

The single biggest difference between bell_bench_test_setup.svg and the full rotary_dial_circuit_revM.svg is this: **in the bench diagram, the bell is drawn physically unplugged.**

- In the **main schematic**, T1's HV winding runs through R18 (220Ω) straight to the bell's RED and BLACK leads — a closed loop, exactly as it'll be wired when the phone is finished and working.
- In the **bench diagram**, those same RED/BLACK wires are drawn with a visible gap (the two short red tick marks at x≈693) — deliberately open. T1's secondary is running unloaded (nothing drawing current from it) for the entire test.

Why disconnect the bell first? Because until you've confirmed the transformer and gate-drive electronics behave, you don't know what voltage/current the bell is about to see. The original 90V ringing convention was for phones designed to take it — but if a wiring mistake sent DC or a bigger-than-expected spike down that line, you could cook the bell coil or (worse) leave 48V+ sitting on exposed leads while you're still hands-on with the board. Testing "dry" first turns a possible hardware-destroying mistake into just a wrong number on a meter.

The bench diagram also adds three **test points that don't exist in the real circuit** — TP-A, TP-B, TP-C — plus a drawn DMM symbol. These are measurement fixtures only: alligator clips and probe tips you attach temporarily. They're not new components you're supposed to solder in permanently; the finished phone has no meter parked on it.

## Walking through the 9 steps

1. **Power off, DMM continuity/resistance checks.** This is the "look before you leap" pass — with no power applied, you can't hurt anything, so it's the safest place to catch a wiring mistake. You're checking: T1's winding ratio looks right (pin3-to-pin6 resistance should be about double pin3-to-pin4, since pin 5 is the centre tap — sanity-checks that you've actually got a 161G24 wired the way you think), the two snubber legs (R16/C9, R17/C10) aren't open or dead-shorted, and Q2/Q3 aren't shorted drain-to-source (which would mean 5V straight to ground the instant you power up).

2. **Confirm the bell is really unplugged.** Just a visual double-check before power — the red gap marks in the diagram mirror what you should see on the bench.

3. **Power the board over USB, open the serial monitor at 115200 baud — not 1200.** 1200 baud isn't a "wrong speed for text," it's the specific signal the Caterina bootloader watches for to trigger a firmware-upload reset. Opening a monitor at that speed will unexpectedly reboot the board mid-test.

4. **Send `h` for continuous ring instead of a timed burst.** A DMM needs roughly half a second to a couple of seconds to settle on a stable reading (its internal ADC is averaging/sampling, not instantaneous like a scope). A 2-second burst might end before the meter has locked onto a number; holding the ring on lets you actually read it.

5. **TP-B, DMM in AC volts: expect ~48Vac.** This is the "prove the transformer stage works, independent of everything downstream" check. If T1's turns ratio and wiring are right, you should see the stepped-up AC voltage sitting across the open RED/BLACK gap — with nothing connected there, this is a pure open-circuit voltage measurement, not affected by the bell coil's resistance at all.

6. **TP-A/TP-C, scope only.** This is the one measurement a DMM cannot do. Here's the physics: Q2/Q3 alternately pull each half of T1's primary to ground. While a FET is "on," its drain sits near 0V. When it switches "off," the *opposite* FET's body diode clamps that drain to roughly 2×5V + 0.7V ≈ 10.7V (this is the normal push-pull behavior, not a fault). But real transformer windings have a small amount of "leakage inductance" — energy that doesn't perfectly couple between the two halves — and when the FET turns off, that leftover energy causes a brief voltage spike riding on top of the clamped level, lasting only microseconds. A DMM's averaging can't see something that short; only an oscilloscope, which samples fast enough to catch the spike's actual peak, can. That's why this step is scope-only, and why the diagram is explicit that a DMM structurally cannot substitute here.

   **Pass condition:** that spike needs to stay clearly under 55V — the IRFZ44N's rated maximum drain-source voltage. This is the core safety check for the whole switch to the on-hand FETs.

7. **Send `s` to stop, then check the 5V rail while ringing (repeat step 4).** Ringing the bell pulls real current out of the 5V rail through T1's centre tap. If your USB source or wiring can't supply it, the rail could sag toward the ATmega32u4's brownout threshold (~4.5V) — which would reset or glitch the microcontroller mid-ring. This step catches a "power budget" problem, which is a completely different failure mode from the FET-voltage check in step 6.

8. **Only after 5–7 look right: reconnect the bell, ring for real.** This is the first time actual current flows into the bell coil and clapper mechanism.

9. **Insulate exposed HV wiring.** ~48V is a real, feelable shock — not lethal in this configuration, but worth treating with normal respect once the bell circuit is live.

### If you don't have a scope
Steps 6 has a documented fallback (also in the diagram, in red): run the ring for just a few seconds first and feel Q2/Q3 for warmth immediately after — unexpected heat is a rough proxy for "something's dissipating way more energy than expected." But it's explicitly flagged as a fallback, not a substitute — you're then trusting the calculated safety margin (snubber + the FET's built-in avalanche rating) rather than directly measuring it.

## The diagram consistency updates

- **G/S/D pin labels** added to Q2 and Q3 in both diagrams. Convention (same in both): **Gate on the left, Source on the bottom, Drain on the right** of the box symbol. One nuance: in the bench diagram only, Q3's source wire is drawn exiting the **top** of its box instead of the bottom — a leftover layout choice from an earlier session to leave room for the snubber wiring between Q2 and Q3. It's the same net, just mirrored for drawing space — nothing electrically different, but worth knowing so the two diagrams don't look contradictory side by side.
- Also worth remembering: **this schematic G-S-D layout is not the same order as the IRFZ44N's physical TO-220 leads** (which read G-D-S left-to-right when you're facing the part with the leads pointing down at you, tab = drain). The schematic tells you which *net* each pin belongs to, not the physical order you'll see holding the part in your hand — don't wire straight off the schematic's left-to-right order.
- **T1 pin numbers** (pin 1, pin 2 = HV/secondary terminals; pin 3, pin 6 = the two ends of the centre-tapped LV winding) added to the bench diagram to match the numbering already used in the main schematic. I also tried adding a "pins 4+5 (jumpered)" note for the centre tap, but the gap between the two coil windings in that diagram turned out too narrow for any text to fit without overlapping the coils — so that detail stays verbal only: **pins 4 and 5 are jumpered together** to form the 5V centre tap, same as in the main schematic.

Made changes.
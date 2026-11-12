# Automated audio audit

Offline deterministic speech-like signal: quiet, normal and loud voiced sections, consonant-like noise, pauses and a two-second tail. This is not a listening score or an intelligibility measurement.

| Voice / effect | Worst p99 ms | Peak | Pre-limiter peak | Clipped samples | Errors | Sanitized samples | Pitch underruns |
|---|---:|---:|---:|---:|---:|---:|---:|
| Broadcast | 0.34 | 0.723 | 0.418 | 0 | 0 | 0 | 0 |
| Warm Low | 0.56 | 0.729 | 0.422 | 0 | 0 | 0 | 0 |
| Bright | 0.43 | 0.672 | 0.389 | 0 | 0 | 0 | 0 |
| Clean (Normal) | 0.29 | 0.706 | 0.409 | 0 | 0 | 0 | 0 |
| Deep (Vader) | 0.39 | 0.720 | 0.417 | 0 | 0 | 0 | 0 |
| Monster / Demon | 0.44 | 0.600 | 0.347 | 0 | 0 | 0 | 0 |
| Chipmunk | 0.56 | 0.652 | 0.377 | 0 | 0 | 0 | 0 |
| Cyborg Robot | 0.45 | 0.635 | 0.368 | 0 | 0 | 0 | 0 |
| Walkie-Talkie | 0.49 | 0.479 | 0.277 | 0 | 0 | 0 | 0 |
| Telephone | 0.38 | 0.560 | 0.324 | 0 | 0 | 0 | 0 |
| Astronaut | 0.34 | 0.905 | 0.617 | 0 | 0 | 0 | 0 |
| 8-Bit Arcade | 0.29 | 0.660 | 0.382 | 0 | 0 | 0 | 0 |
| Cathedral Echo | 0.31 | 0.842 | 0.582 | 0 | 0 | 0 | 0 |
| Alien | 0.58 | 0.570 | 0.330 | 0 | 0 | 0 | 0 |
| Space Marine | 1.35 | 0.509 | 0.294 | 0 | 0 | 0 | 0 |
| Ghost | 1.81 | 0.830 | 0.521 | 0 | 0 | 0 | 0 |
| Goblin | 1.20 | 0.820 | 0.532 | 0 | 0 | 0 | 0 |
| Hive Mind | 0.69 | 0.872 | 0.510 | 0 | 0 | 0 | 0 |
| Kid (DSP prototype) | 1.15 | 0.825 | 0.498 | 0 | 0 | 0 | 0 |
| Stress / Boosted tone EQ | 0.34 | 0.809 | 0.479 | 0 | 0 | 0 | 0 |
| Stress / Cut tone EQ | 0.29 | 0.608 | 0.352 | 0 | 0 | 0 | 0 |
| Stress / Telephone channel | 0.33 | 0.430 | 0.249 | 0 | 0 | 0 | 0 |
| Stress / Extreme pitch | 0.52 | 0.706 | 0.408 | 0 | 0 | 0 | 0 |
| Stress / Extreme formant | 1.07 | 0.802 | 0.470 | 0 | 0 | 0 | 0 |
| Stress / Strong ring | 0.23 | 0.791 | 0.458 | 0 | 0 | 0 | 0 |
| Stress / Low bit depth | 0.21 | 0.698 | 0.404 | 0 | 0 | 0 | 0 |
| Stress / Strong distortion | 0.17 | 0.486 | 0.281 | 0 | 0 | 0 | 0 |
| Stress / Long reverb | 0.30 | 0.853 | 0.613 | 0 | 0 | 0 | 0 |
| Stress / Strong doubler | 0.21 | 0.705 | 0.408 | 0 | 0 | 0 | 0 |
| Stress / Two harmony layers | 0.75 | 0.707 | 0.409 | 0 | 0 | 0 | 0 |
| Stress / Maximum resonator decay | 0.23 | 0.522 | 0.302 | 0 | 0 | 0 | 0 |
| Stress / Long feedback echo | 0.27 | 0.755 | 0.438 | 0 | 0 | 0 | 0 |
| Stress / Strong parallel saturation | 0.24 | 0.382 | 0.221 | 0 | 0 | 0 | 0 |
| Stress / Stacked effects | 1.73 | 0.533 | 0.308 | 0 | 0 | 0 | 0 |
| Stress / Radio with texture | 0.47 | 0.386 | 0.223 | 0 | 0 | 0 | 0 |

Each row combines mono/stereo at 44.1/48 kHz. A 512-frame callback allows 10.67 ms at 48 kHz; scheduling under game load is not covered. A bounded final peak does not mean the upstream chain is transparent. High pre-limiter peaks identify chains needing less input/effect gain. Long tails are intentional in echo/reverb stress cases.

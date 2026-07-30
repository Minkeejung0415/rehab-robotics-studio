---
status: partial
phase: 20-full-identity-and-confirmed-identify
source: [20-VERIFICATION.md]
started: 2026-07-30T14:41:28-07:00
updated: 2026-07-30T14:41:28-07:00
---

# Phase 20 Hardware UAT

## Current Test

Awaiting offline testing while the computer is connected to the STEP_ESP network.

## Tests

### 1. Exact-target LED, polarity, timing, and restoration

expected: With at least two official XIAO ESP32S3 devices powered, only the selected full-MAC target blinks for the requested 1 s, 3 s, and 5 s durations; the witness device stays still; GPIO 21 behaves active-low; and the exact prior LED level returns afterward.

result: [pending]

### 2. Identify during live acquisition

expected: Repeating Identify while acquisition is streaming does not stop or materially alter acquisition; sample rate, continuity, drops, and errors remain acceptable before, during, and after each command.

result: [pending]

### 3. Identify during SD recording and finalization

expected: Repeating Identify during active SD recording and finalization does not alter session state, saved samples, file size, checksum/status, or data continuity.

result: [pending]

### 4. Physical identity and outcome correlation

expected: The recorded base, STA, AP, and ESP-NOW MAC relationship belongs to the physically observed target, and only a matching command ID plus exact target with `outcome=confirmed` is paired with a successful blink observation.

result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps

None reported yet.

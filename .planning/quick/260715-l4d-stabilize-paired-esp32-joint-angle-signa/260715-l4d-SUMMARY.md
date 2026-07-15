---
quick_id: 260715-l4d
status: complete
---

# Stabilize paired ESP32 joint-angle signal with still calibration and low-pass filtering

## Delivered

- Added a pair-angle stabilizer at the rosbridge data boundary.
- It waits for a quiet 0.5 second startup window, uses the measured relative angle as neutral, filters subsequent readings at 1.5 Hz, and suppresses less than 0.012 rad of residual rest wander.
- Estimator state resets with each acquisition start or stop.

## Verification

- `npm run build` passed.
- Playwright connected to the live preview at `http://127.0.0.1:5174` with the two USB-backed ROS topics `/esp/raw/master` and `/esp/raw/slave`.
- With both ESPs stationary, the Front Panel Knee readout was `35.0 deg` across 20 samples over 3 seconds (0.0 degree span); ROS and ESP stream indicators were connected/streaming and the browser reported no errors.

## Manual Follow-up

- After pressing Run, keep both ESPs still for the first half second so neutral calibration can complete. Then move the slave relative to the master to confirm the knee value changes and smoothly settles when motion stops.

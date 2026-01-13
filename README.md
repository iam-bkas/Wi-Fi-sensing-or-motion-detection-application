# Wi-Fi-sensing-or-motion-detection-application
Changes in wireless signals to infer movement without cameras. Algorithms track these changes over time to detect occupancy, gestures, or events. Key signal inputs include RSSI fluctuations, Channel State Information (CSI), and Doppler features. With multiple antennas, devices can estimate directionality and sometimes range.

Common Approaches:
- RSSI variance: simplest, works on most hardware; coarser, noisy but useful for “motion/no motion”.
- CSI processing: per‑subcarrier amplitude/phase from 802.11n/ac; enables finer detection (breathing, falls).
- Doppler/STFT: frequency shifts reveal movement speed and periodic motion.
- Wi‑Fi RTT/FTM (802.11mc): time‑of‑flight adds distance; combined with CSI improves localization.
- ML pipelines: classify motion patterns from engineered features or neural models.

Real‑World Availability:
- Consumer deployments via ISPs and router vendors (e.g., Plume Motion, TP‑Link, OriginAI/Cognitive Systems, Qualcomm Wi‑Fi Sensing).
- Standards effort IEEE 802.11bf targets native WLAN sensing support.
- Research prototypes (WiSee, etc.) and CSI tools for specific chipsets (Intel 5300, Atheros, Broadcom/Nexmon, ESP32).

Accuracy & Limits:
- Sensitive to environment: furniture changes, people count, and multipath complexity affect performance.
- Router and driver access matter: CSI often requires specific NICs/firmware and monitor mode.
- Best for occupancy, coarse motion, and event detection; fine localization needs multi‑AP setups.
- Privacy benefits (no video), but can still infer presence/behaviors — treat as sensitive data.

  Before using this app
  - Install dependencies >> python -m pip install matplotlib numpy
  - Run the GUI: >> python -m motion_tracker.gui
  - Run CLI with visualize: >> python -m motion_tracker.cli --visualize

If You Want To Try It:
- Quick demo: sample Wi‑Fi signal strength and detect motion via variance thresholds (coarse, works broadly).
- Better fidelity: use hardware that exposes CSI (e.g., ESP32/Nexmon/Intel 5300) and run a Python pipeline for filtering, feature extraction, and classification.
- Highest quality: multi‑AP setup with synchronized sampling, Doppler features, and optional RTT for localization.
If you share what hardware you have and your goal (e.g., simple motion alerts vs. room‑level tracking), I’ll tailor a path and set up a prototype that fits your setup.

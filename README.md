# BEAPER Nano Autonomous Sumo Bot (ESP32 State Machine)

An autonomous MicroPython sumo robot project built on the **BEAPER Nano** chassis and driven by an **Arduino Nano ESP32**. This repository accompanies the YouTube video breakdown on taking an autonomous bot from linear spaghetti code to a structured **Finite State Machine (FSM)**.

---

## 📽️ Project Overview

* **Microcontroller:** Arduino Nano ESP32
* **Framework:** MicroPython (developed via Arduino Lab for MicroPython)
* **Architecture:** Finite State Machine (FSM)
* **Sensors:** Time-of-Flight (ToF) distance sensors, Gyroscope, Line/Floor sensors, Sonar, Magnetic switches
* **Interface:** On-board LCD menu system + Wi-Fi smartphone remote control

---

## 🧠 FSM Architecture

Rather than relying on continuous linear `if-then` checks, the robot operates using discrete state behaviors to react in real time:

1. **SEARCH:** Scans the mat using ToF and sonar sensors to locate an opponent.
2. **ATTACK:** Engages target with directional adjustments guided by gyroscope inputs.
3. **ESCAPE / RECOVERY:** Overrides attack logic when floor/line sensors detect the sumo mat boundary.
4. **MANUAL / WIFI:** Operates via local Wi-Fi menu interface for smartphone driving outside the arena.

---

## 📁 Repository Structure

```text
├── main.py                     # Main Finite State Machine loop & state controller
├── BEAPER_Nano.py               # Pin definitions, motor controls, & hardware constants
├── beaper_hardware_0903.py     # Hardware Abstraction Layer (HAL) with ToF, Gyro, & Morse
├── beaper_logger_0828.py       # Non-blocking telemetry & system logger
├── mode_sumo_0903.py           # Sumo Bot personality module
├── mode_pet_0903.py            # Pet Bot personality module
├── README.md                   # Project documentation
└── helpers/                    # Hardware drivers & UI utilities
    ├── LCD.py                  # FrameBuffer LCD driver (ST7789 base)
    ├── LCDconfig_nano.py       # Nano-specific display SPI configuration
    ├── bar_graph.py            # Custom visual bar graph module
    ├── VL53L4CD.py             # Time-of-Flight sensor driver
    └── mpu6050.py              # Gyro / Accelerometer sensor driver
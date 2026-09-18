"""
================================================================================
BEAPER Sumo Robot - Non-Blocking Telemetry & Logger
Original Integrated Creation Author: cache4pat
MODULE: beaper_logger.py
DATE: Sept 3, 2026 
================================================================================
"""

import time

class BeaperLogger:
    def __init__(self, debug_enabled=False, log_interval_ms=250):
        self.enabled = debug_enabled
        self.log_interval_ms = log_interval_ms
        self.last_log_time = 0

    def log_state_change(self, old_state_name, new_state_name, reason=""):
        if not self.enabled:
            return
        
        if reason:
            print(f"--> [STATE] {old_state_name} -> {new_state_name} ({reason})")
        else:
            print(f"--> [STATE] {old_state_name} -> {new_state_name}")

    def log_telemetry(self, current_time_ms, state_name, sonar_cm, tof_mm, heading_deg):
        if not self.enabled:
            return

        if time.ticks_diff(current_time_ms, self.last_log_time) >= self.log_interval_ms:
            print(f"[{state_name}] Sonar: {sonar_cm}cm | ToF: {tof_mm}mm | Heading: {heading_deg:.1f}°")
            self.last_log_time = current_time_ms

    def log_info(self, message):
        if self.enabled:
            print(f"[INFO] {message}")
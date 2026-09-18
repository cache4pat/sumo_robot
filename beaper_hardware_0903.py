"""
================================================================================
BEAPER Sumo Robot - Hardware Abstraction Layer (HAL)
Original Integrated Creation Author: cache4pat
MODULE: beaper_hardware_0903.py    adds ToF and Gyro sensors; plus Dynamic Morse Reader
DATE: Sept 3, 2026 VERSION
Uses June 2026 mirobotech cloned imports on modified BEAPER-Nano hardware
================================================================================
"""

from machine import I2C, Pin
import time
import BEAPER_Nano as beaper
from VL53L4CD import VL53L4CD
from mpu6050 import MPU6050

# Morse Code Dictionary
MORSE_MAP = {
    '.-': 'A', '-...': 'B', '-.-.': 'C', '-..': 'D', '.': 'E',
    '..-.': 'F', '--.': 'G', '....': 'H', '..': 'I', '.---': 'J',
    '-.-': 'K', '.-..': 'L', '--': 'M', '-.': 'N', '---': 'O',
    '.--.': 'P', '--.-': 'Q', '.-.': 'R', '...': 'S', '-': 'T',
    '..-': 'U', '...-': 'V', '.--': 'W', '-..-': 'X', '-.--': 'Y',
    '--..': 'Z', '.----': '1', '..---': '2', '...--': '3', '....-': '4',
    '.....': '5', '-....': '6', '--...': '7', '---..': '8', '----.': '9',
    '-----': '0'
}

def calculate_morse_timings(wpm=10, manual_fudge_factor=1.2):
    """
    Generates dynamic Morse timing thresholds based on target WPM.
    Applies a fudge factor to expand tolerances for manual hand keying.
    """
    base_dot = 1200 / wpm
    fudged_dot = base_dot * manual_fudge_factor
    fudged_dash = (base_dot * 3) * manual_fudge_factor
    
    midpoint_ms = int((fudged_dot + fudged_dash) / 2)
    letter_gap_ms = int((base_dot * 3) * (manual_fudge_factor * 1.5))
    word_timeout_ms = int(letter_gap_ms * 5.0)
    
    return {
        'min_pulse_ms': 35,
        'midpoint_ms': midpoint_ms,
        'letter_gap_ms': letter_gap_ms,
        'word_timeout_ms': word_timeout_ms,
        'wpm': wpm
    }


class MorseLightSensor:
    def __init__(self, threshold=25000, wpm=10, manual_fudge_factor=1.2):
        self.threshold = threshold
        self.is_high = False
        self.last_transition_time = time.ticks_ms()
        self.pulse_pattern = ""
        self.cfg = calculate_morse_timings(wpm, manual_fudge_factor)

    def process(self):
        raw_val = beaper.ADC2.read_u16()
        current_level = 65535 - raw_val
        now = time.ticks_ms()
        
        currently_lit = current_level > self.threshold

        # Transition: DARK -> LIGHT
        if currently_lit and not self.is_high:
            self.is_high = True
            self.last_transition_time = now
            
        # Transition: LIGHT -> DARK
        elif not currently_lit and self.is_high:
            light_duration = time.ticks_diff(now, self.last_transition_time)
            self.is_high = False
            self.last_transition_time = now

            if light_duration >= self.cfg['min_pulse_ms']:
                if light_duration < self.cfg['midpoint_ms']:
                    self.pulse_pattern += "."
                else:
                    self.pulse_pattern += "-"

        # Timeout: End of Letter Sequence
        if not self.is_high and len(self.pulse_pattern) > 0:
            if time.ticks_diff(now, self.last_transition_time) > self.cfg['letter_gap_ms']:
                pattern = self.pulse_pattern
                self.pulse_pattern = ""
                char = MORSE_MAP.get(pattern, "?")
                return pattern, char, current_level
                
        return None, None, current_level


class BeaperHardware:
    def __init__(self, target_wpm=10, detect_range_cm=45, edge_threshold=50000, 
                 tof_min_mm=30, tof_max_mm=150):
        # Operational Thresholds
        self.detect_range_cm = detect_range_cm
        self.edge_threshold = edge_threshold
        self.tof_min_mm = tof_min_mm
        self.tof_max_mm = tof_max_mm

        # Initialize I2C Bus (400 kHz)
        self.i2c = I2C(0, scl=Pin("A5"), sda=Pin("A4"), freq=400000)

        # Initialize Time-of-Flight Sensor
        try:
            self.tof = VL53L4CD(beaper.QWIIC)
            self.tof.set_range_timing(30, 0)
            self.tof.start_ranging()
        except Exception:
            self.tof = None

        # Initialize MPU6050 Gyro
        try:
            self.imu = MPU6050(self.i2c)
            self.gyro_scale = 131.0
            self.z_offset = 0.0
        except Exception:
            self.imu = None

        # Sensor Cache State
        self.sonar_distance = 999
        self.last_sonar_time = 0
        self.rear_dist_mm = 9999
        self.last_tof_time = 0
        self.tof_threat_count = 0

        # Optical Morse Engine Initialization
        self.morse_cfg = calculate_morse_timings(wpm=target_wpm, manual_fudge_factor=1.2)
        self.morse_sensor = MorseLightSensor(threshold=25000, wpm=target_wpm, manual_fudge_factor=1.2)
        self.morse_word_buffer = ""
        self.last_char_time = time.ticks_ms()

    # --- Optical Morse Decoder Interface ---
    def poll_morse_command(self):
        char = None
        for _ in range(5):
            p, c, level = self.morse_sensor.process()
            if c and c != "?":
                char = c
            time.sleep_us(500)

        now = time.ticks_ms()

        if char:
            self.morse_word_buffer += char
            self.last_char_time = now
            return char, self.morse_word_buffer

        # Dynamic buffer reset on inactivity
        if len(self.morse_word_buffer) > 0 and time.ticks_diff(now, self.last_char_time) > self.morse_cfg['word_timeout_ms']:
            self.morse_word_buffer = ""

        return None, self.morse_word_buffer

    def clear_morse_buffer(self):
        """Clears accumulated Morse word buffer."""
        self.morse_word_buffer = ""

    # --- Calibration & System Control ---
    def calibrate_gyro(self):
        if not self.imu: return
        total = 0
        samples = 100
        for _ in range(samples):
            total += self.imu.get_gyro_z()
            time.sleep_ms(3)
        self.z_offset = total / samples

    def get_gyro_z_deg_sec(self):
        if not self.imu: return 0.0
        gz_raw = self.imu.get_gyro_z() - self.z_offset
        deg_sec = gz_raw / self.gyro_scale
        if abs(deg_sec) < 1.5:
            return 0.0
        return deg_sec

    def stop_all(self):
        beaper.motors_stop()
        beaper.nano_led_off()

    def is_emergency_stop_pressed(self):
        return beaper.SW5.value() == 0

    def is_start_button_pressed(self):
        return beaper.SW2.value() == 0

    def play_tone(self, freq, duration_ms):
        beaper.tone(freq, duration_ms)

    def set_rgb(self, red=0, green=0, blue=0):
        beaper.nano_rgb_red(red)
        beaper.nano_rgb_green(green)
        beaper.nano_rgb_blue(blue)

    # --- Edge Sensing (Q1 Left, Q2 Right) ---
    def check_edge(self):
        left_on_edge = beaper.Q1_level() > self.edge_threshold
        right_on_edge = beaper.Q2_level() > self.edge_threshold

        if left_on_edge and right_on_edge:
            return "both"
        elif left_on_edge:
            return "left"
        elif right_on_edge:
            return "right"
        return None

    # --- Sonar & ToF Sensors ---
    def read_sonar(self, current_time_ms, interval_ms=30):
        if time.ticks_diff(current_time_ms, self.last_sonar_time) >= interval_ms:
            result = beaper.sonar_range(_max_range=self.detect_range_cm + 15)
            self.sonar_distance = result if result >= 0 else 999
            self.last_sonar_time = current_time_ms
        return self.sonar_distance

    def is_front_target_detected(self):
        return 0 < self.sonar_distance <= self.detect_range_cm

    def check_rear_threat(self, current_time_ms, required_cycles=2):
        if not self.tof: 
            self.rear_dist_mm = 999
            return False
            
        try:
            if self.tof.data_ready():
                res = self.tof.get_result()
                self.tof.clear_interrupt()
                self.last_tof_time = current_time_ms

                if res['range_status'] == 0:
                    dist = res['distance_mm']
                    if self.tof_min_mm <= dist <= self.tof_max_mm:
                        self.rear_dist_mm = dist
                        self.tof_threat_count += 1
                    else:
                        self.rear_dist_mm = 999  # Clear stale distance when out of bounds
                        self.tof_threat_count = max(0, self.tof_threat_count - 1)
                else:
                    self.rear_dist_mm = 999      # Clear stale distance on range error
                    self.tof_threat_count = max(0, self.tof_threat_count - 1)
        except Exception:
            pass

        return self.tof_threat_count >= required_cycles


    def clear_tof_queue(self):
        self.rear_dist_mm = 9999
        self.tof_threat_count = 0
        if not self.tof: return
        try:
            while self.tof.data_ready():
                self.tof.get_result()
                self.tof.clear_interrupt()
        except Exception:
            pass

    # --- Motor Kinematic Primitives ---
    def drive_forward(self):
        beaper.left_motor_forward()
        beaper.right_motor_forward()

    def drive_reverse(self):
        beaper.left_motor_reverse()
        beaper.right_motor_reverse()

    def spin_left(self):
        beaper.left_motor_reverse()
        beaper.right_motor_forward()

    def spin_right(self):
        beaper.left_motor_forward()
        beaper.right_motor_reverse()

    def pivot_right(self):
        beaper.left_motor_forward()
        beaper.right_motor_stop()

    def pivot_left(self):
        beaper.left_motor_stop()
        beaper.right_motor_forward()

    def motors_stop(self):
        beaper.motors_stop()
        
    def cleanup(self):
        self.stop_all()
        self.set_rgb(0, 0, 0)
        if self.tof:
            try:
                self.tof.stop_ranging()
            except Exception:
                pass
        try:
            self.i2c.deinit()
        except Exception:
            pass
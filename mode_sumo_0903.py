"""
================================================================================
BEAPER Sumo Robot - Master Execution Engine - GO - END Morse Keywords
MODULE: main.py (Final Integrated Morse + Sumo Architecture) 
Was "mode_sumo_0828.py" as a FLASH Import Object now mode_sumo_0903.py
DATE: Sept 3, 2026 Referencing new beaper_hardware_0903.py
================================================================================
"""

import time
import random
from machine import Pin, SPI
import BEAPER_Nano as beaper
import LCDconfig_Nano as lcd_config
import bar_graph
from beaper_hardware_0903 import BeaperHardware
from beaper_logger_0828 import BeaperLogger

# --- Configuration Constants ---
DEBUG_MODE           = False       # Set True for bench testing; False for match runs
TARGET_WPM           = const(10)   # Operational optical Morse WPM rate
START_DELAY          = const(5000) # ms: Mandatory 5-second sumo start delay
BEEP_INTERVAL        = const(1000) # ms: Countdown audio beep interval
BACKUP_TIME          = const(550)  # ms: Reverse duration upon hitting white edge
TURN_TIME            = const(350)  # ms: Base turn duration (~120 deg) to escape ring edge
DWELL_TIME_MS        = const(80)   # ms: Brief pause duration before/after rapid 180 flips
FLIP_COOLDOWN_MS     = const(800)  # ms: Cooldown timer preventing rapid rear flips
TARGET_LOSS_DELAY_MS = const(150)  # ms: Hysteresis delay before dropping target lock
PUSH_COMMIT_MS       = const(400)  # ms: Mandatory forward drive duration once locked
LOOP_DELAY           = const(10)   # ms: Main execution loop cadence (~100 Hz)
HUD_UPDATE_INTERVAL  = const(150)  # ms: GUI refresh cadence (~6.6 Hz)

# Sweep Pattern Settings
SWEEP_BASE_MS        = const(150)  # ms: Initial base sweep step duration
MAX_SWEEP_STEPS      = const(6)    # Maximum sweep arcs before resetting pattern

# --- Named State Enumerations ---
STATE_IDLE      = const(0)
STATE_COUNTDOWN = const(1)
STATE_SEARCH    = const(2)
STATE_PUSH      = const(3)
STATE_EDGE      = const(4)
STATE_STOPPED   = const(5)
STATE_REAR_FLIP = const(6)
STATE_REAR_STOP = const(7)

STATE_NAMES = {
    STATE_IDLE:      "IDLE",
    STATE_COUNTDOWN: "COUNTDOWN",
    STATE_SEARCH:    "SEARCH",
    STATE_PUSH:      "PUSH",
    STATE_EDGE:      "EDGE",
    STATE_STOPPED:   "STOPPED",
    STATE_REAR_FLIP: "REAR_FLIP",
    STATE_REAR_STOP: "REAR_STOP",
}

# --- Initialize Hardware & LCD ---
robot = BeaperHardware(target_wpm=TARGET_WPM, detect_range_cm=45, 
                       edge_threshold=50000, tof_min_mm=30, tof_max_mm=150)
logger = BeaperLogger(debug_enabled=DEBUG_MODE, log_interval_ms=250)

# SPI & LCD Initialization
spi = SPI(2, baudrate=60000000, sck=Pin(48), mosi=Pin(38), miso=None)
spi.deinit()
lcd = lcd_config.config()

# --- GUI Helper Functions ---
def get_battery_voltage():
    raw_adc = beaper.VDIV_level()
    return raw_adc * 3.3 / 65535 * 6.225

def draw_hud(status_msg, v_bat, morse_word="---"):
    lcd.fill(lcd.BLACK)
    
    # Status Header
    lcd.text16("CHECK BATTERY", 20, 10, lcd.CYAN)
    
    # Numeric Battery Display
    text_v = f"Level: {v_bat:4.2f}V"
    v_color = lcd.GREEN if v_bat >= 7.2 else lcd.RED
    lcd.text16(text_v, 20, 35, v_color)
    
    # Battery Bar Graph
    bar_graph.horizontal(
        lcd, x=20, y=55, width=200, length=15,
        value=v_bat, min_val=6.0, max_val=8.4,
        color=v_color, bg_color=lcd.BLUE50,
        border=1, border_color=lcd.WHITE50
    )
    
    # Live Morse Code Display
    disp_word = morse_word if morse_word else "---"
    lcd.text16(f"CODE: {disp_word}", 60, 80, lcd.GREEN)
    
    # State Status & Instructions
    lcd.text16(status_msg, 20, 115, lcd.YELLOW)
    lcd.text16("SW2 / 'GO' -> START", 20, 150, lcd.WHITE)
    lcd.text16("SW5 / 'END' -> STOP", 20, 180, lcd.YELLOW)
    
    lcd.update()

# --- Operational State Variables ---
state             = STATE_IDLE
state_start       = 0
last_beep_time    = 0
last_hud_update   = 0
last_flip_time    = 0
target_lost_time  = None
flip_done_time    = None
push_lock_active  = False
push_lock_time    = 0
dynamic_turn_time = TURN_TIME
display_word      = "---"

# Edge and Gyro state tracking
edge_direction    = "both"
edge_phase        = "backup"
current_heading   = 0.0
last_gyro_time    = 0

# Sweep pattern variables
sweep_direction   = 1
sweep_step        = 0
step_start_time   = 0
current_step_duration = 0

# --- Helper Functions ---
def start_sweep_step(step_idx, direction, current_time_ms):
    global step_start_time, current_step_duration
    current_step_duration = int(SWEEP_BASE_MS * (1.8 ** step_idx))
    step_start_time = current_time_ms
    
    if direction > 0:
        robot.pivot_right()
    else:
        robot.pivot_left()

def enter_state(new_state, current_time_ms, reason=""):
    global state, state_start, edge_phase, target_lost_time
    global current_heading, last_gyro_time, last_flip_time, flip_done_time
    global sweep_step, sweep_direction

    robot.motors_stop()
    old_state = state
    state = new_state
    state_start = current_time_ms

    if new_state in (STATE_IDLE, STATE_EDGE, STATE_SEARCH):
        robot.clear_tof_queue()

    # SCREEN POLICY: Wake display for IDLE
    if new_state == STATE_IDLE:
        last_flip_time = 0
        try:
            lcd.sleep_mode(False)
        except Exception:
            pass

    target_lost_time = None
    flip_done_time = None
    current_heading = 0.0
    last_gyro_time = current_time_ms

    # SCREEN POLICY: Sleep display during MATCH RUNNING
    if new_state == STATE_SEARCH:
        sweep_step = 0
        sweep_direction = 1
        try:
            draw_hud("MATCH RUNNING", get_battery_voltage(), display_word)
            lcd.sleep_mode(True)
        except Exception:
            pass
        start_sweep_step(sweep_step, sweep_direction, current_time_ms)

    # SCREEN POLICY: Wake display for STOPPED
    if new_state == STATE_STOPPED:
        try:
            lcd.sleep_mode(False)
            draw_hud("MATCH STOPPED", get_battery_voltage(), display_word)
        except Exception:
            pass

    if new_state == STATE_REAR_FLIP:
        robot.clear_tof_queue()

    edge_phase = "backup"
    logger.log_state_change(STATE_NAMES[old_state], STATE_NAMES[new_state], reason)

# --- Startup Initialization ---
robot.stop_all()
state_start = time.ticks_ms()
last_beep_time = state_start
enter_state(STATE_IDLE, state_start, "system boot")

# --- Main Core Execution Loop ---
try:
    while True:
        now = time.ticks_ms()
        elapsed = time.ticks_diff(now, state_start)
        v_bat = get_battery_voltage()
        
        # --- OPTICAL MORSE ENGINE POLLING ---
        last_char, current_word = robot.poll_morse_command()
        display_word = current_word

        # Signal Triggers (Buttons + New Action Words 'GO' / 'END')
        trigger_start = robot.is_start_button_pressed() or ("GO" in current_word)
        trigger_stop  = robot.is_emergency_stop_pressed() or ("END" in current_word)

        # 1. Non-Blocking Telemetry
        logger.log_telemetry(now, STATE_NAMES[state], robot.sonar_distance, 
                             robot.rear_dist_mm, current_heading)

        # 2. Safety Interrupt: Emergency Stop Button OR Optical 'END'
        if trigger_stop and state not in (STATE_IDLE, STATE_STOPPED):
            robot.stop_all()
            robot.play_tone(200, 300)
            robot.clear_morse_buffer()
            enter_state(STATE_STOPPED, now, "emergency stop (SW5 or END)")

        # 3. State: Idle
        elif state == STATE_IDLE:
            robot.set_rgb(red=16000)
            if time.ticks_diff(now, last_hud_update) >= HUD_UPDATE_INTERVAL:
                draw_hud("READY...", v_bat, display_word)
                last_hud_update = now

            if trigger_start:
                robot.clear_tof_queue()
                robot.calibrate_gyro()
                robot.clear_morse_buffer()
                last_beep_time = now
                enter_state(STATE_COUNTDOWN, now, "start triggered (SW2 or GO)")
        
        # 4. State: Countdown (GUI + Audio Sync)
        elif state == STATE_COUNTDOWN:
            seconds_left = max(0, int((START_DELAY - elapsed) / 1000) + 1)

            if time.ticks_diff(now, last_hud_update) >= HUD_UPDATE_INTERVAL:
                draw_hud(f"START IN: {seconds_left}s", v_bat, display_word)
                last_hud_update = now

            if time.ticks_diff(now, last_beep_time) >= BEEP_INTERVAL:
                robot.set_rgb(red=32000, green=16000)
                if seconds_left > 0:
                    robot.play_tone(800, 150)
                    robot.set_rgb(red=0)
                last_beep_time = now

            if elapsed >= START_DELAY:
                robot.play_tone(1200, 400)
                enter_state(STATE_SEARCH, now, "countdown complete")

        # 5. State: Search
        elif state == STATE_SEARCH:
            detected_edge = robot.check_edge()
            if detected_edge:
                edge_direction = detected_edge
                enter_state(STATE_EDGE, now, edge_direction + " edge")

            elif time.ticks_diff(now, last_flip_time) >= FLIP_COOLDOWN_MS and robot.check_rear_threat(now):
                enter_state(STATE_REAR_STOP, now, f"rear threat {robot.rear_dist_mm}mm")

            else:
                robot.read_sonar(now)
                if robot.is_front_target_detected():
                    enter_state(STATE_PUSH, now, f"target {robot.sonar_distance}cm")
                else:
                    if time.ticks_diff(now, step_start_time) >= current_step_duration:
                        sweep_direction *= -1
                        sweep_step += 1
                        if sweep_step > MAX_SWEEP_STEPS:
                            sweep_step = 0
                        start_sweep_step(sweep_step, sweep_direction, now)

        # 6. State: Push
        elif state == STATE_PUSH:
            detected_edge = robot.check_edge()
            if detected_edge:
                edge_direction = detected_edge
                push_lock_active = False
                target_lost_time = None
                enter_state(STATE_EDGE, now, edge_direction + " edge")

            else:
                if push_lock_active:
                    robot.drive_forward()
                    if time.ticks_diff(now, push_lock_time) >= PUSH_COMMIT_MS:
                        push_lock_active = False
                else:
                    if robot.check_rear_threat(now):
                        target_lost_time = None
                        enter_state(STATE_REAR_STOP, now, "rear threat during push pause")
                    else:
                        robot.read_sonar(now)
                        if robot.is_front_target_detected():
                            push_lock_active = True
                            push_lock_time = now
                            target_lost_time = None
                            robot.drive_forward()
                        else:
                            if target_lost_time is None:
                                target_lost_time = now
                            
                            if time.ticks_diff(now, target_lost_time) >= TARGET_LOSS_DELAY_MS:
                                target_lost_time = None
                                enter_state(STATE_SEARCH, now, "target lost")
                            else:
                                robot.drive_forward()

        # 7. State: Rear Flip
        elif state == STATE_REAR_FLIP:
            detected_edge = robot.check_edge()
            if detected_edge:
                edge_direction = detected_edge
                enter_state(STATE_EDGE, now, edge_direction + " edge")
            else:
                dt = time.ticks_diff(now, last_gyro_time) / 1000.0
                last_gyro_time = now
                
                gz = robot.get_gyro_z_deg_sec()
                current_heading += (gz * dt)

                if abs(current_heading) < 180.0 and flip_done_time is None:
                    robot.spin_right()
                else:
                    if flip_done_time is None:
                        flip_done_time = now
                        robot.motors_stop()

                    if time.ticks_diff(now, flip_done_time) >= DWELL_TIME_MS:
                        last_flip_time = now
                        robot.clear_tof_queue()
                        robot.read_sonar(now)

                        if robot.is_front_target_detected():
                            enter_state(STATE_PUSH, now, f"flip hit target {robot.sonar_distance}cm")
                        else:
                            enter_state(STATE_SEARCH, now, "flip complete - searching")

        # 8. State: Rear Stop
        elif state == STATE_REAR_STOP:
            robot.motors_stop()
            robot.check_rear_threat(now)

            if elapsed >= DWELL_TIME_MS:
                if robot.rear_dist_mm <= robot.tof_max_mm:
                    enter_state(STATE_REAR_FLIP, now, "verified -> spin 180")
                else:
                    enter_state(STATE_SEARCH, now, "target evaded -> resume search")

        # 9. State: Edge Avoidance
        elif state == STATE_EDGE:
            robot.clear_tof_queue()

            if edge_phase == "backup":
                robot.drive_reverse()
                if elapsed >= BACKUP_TIME:
                    robot.motors_stop()
                    edge_phase = "turn"
                    state_start = now
                    dynamic_turn_time = TURN_TIME + random.randint(50, 150)

            elif edge_phase == "turn":
                if edge_direction == "left":
                    robot.spin_right()
                elif edge_direction == "right":
                    robot.spin_left()
                else:
                    robot.spin_right()

                if elapsed >= dynamic_turn_time:
                    robot.motors_stop()
                    enter_state(STATE_SEARCH, now, "edge cleared")

        # 10. State: Stopped
        elif state == STATE_STOPPED:
            robot.set_rgb(red=16000)
            robot.clear_tof_queue()

            if robot.is_start_button_pressed():
                robot.play_tone(1000, 150)
                target_lost_time = None
                flip_done_time = None
                
                while robot.is_start_button_pressed():
                    time.sleep_ms(10)
                
                time.sleep_ms(200)
                robot.calibrate_gyro()
                enter_state(STATE_COUNTDOWN, time.ticks_ms(), "re-armed from STOPPED")

        time.sleep_ms(LOOP_DELAY)
        
except KeyboardInterrupt:
    logger.log_info("Execution interrupted by user.")

finally:
    logger.log_info("Performing hardware deinit and safety shutdown...")
    robot.cleanup()
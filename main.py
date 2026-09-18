"""
================================================================================
BEAPER Sumo Robot - Dual-Personality Boot Selector with Dynamic Morse Selection
Original Integrated Creation Author: cache4pat
MODULE: main.py
DATE: Sept 3, 2026 Version
Uses June 2026 mirobotech cloned imports on modified BEAPER-Nano hardware
================================================================================
"""

import time
from machine import Pin, SPI
import BEAPER_Nano as beaper
import LCDconfig_Nano as lcd_config
import bar_graph
from beaper_hardware_0903 import BeaperHardware

# --- Constants ---
HUD_UPDATE_MS = const(200)

# --- Initialize Hardware Abstraction & Display ---
robot = BeaperHardware(target_wpm=10)

spi = SPI(2, baudrate=60000000, sck=Pin(48), mosi=Pin(38), miso=None)
spi.deinit()
lcd = lcd_config.config()

def get_battery_voltage():
    raw_adc = beaper.VDIV_level()
    return raw_adc * 3.3 / 65535 * 6.225

def draw_boot_menu(v_bat, morse_word="---"):
    lcd.fill(lcd.BLACK)
  
    # Header & Battery Monitor
    lcd.text16("CHECK BATTERY", 20, 20, lcd.CYAN)
    text_v = f"Level: {v_bat:4.2f}V"
    v_color = lcd.GREEN if v_bat >= 7.2 else lcd.RED
    lcd.text16(text_v, 20, 40, v_color)
  
    bar_graph.horizontal(
        lcd, x=20, y=55, width=200, length=8,
        value=v_bat, min_val=6.0, max_val=8.4,
        color=v_color, bg_color=lcd.BLUE50,
        border=1, border_color=lcd.WHITE50
    )
    
    # Personality Selection Options
    lcd.text16("PICK ROBOT TYPE:", 20, 85, lcd.CYAN)
    lcd.text16("---------------", 20, 95, lcd.WHITE)
    
    lcd.text16("SW3 -> 'BOT'", 30, 130, lcd.WHITE)
    lcd.text16("SW4 -> 'PET'", 30, 150, lcd.YELLOW)

    # Live Morse Output Display
    disp_word = morse_word if morse_word else "---"
    lcd.text16(f"or CODE: {disp_word}", 30, 190, lcd.GREEN)
    
    lcd.update()

# --- Initial Setup ---
robot.stop_all()
selection = None
last_hud_update = 0
display_word = "---"

# Initial screen draw
draw_boot_menu(get_battery_voltage(), display_word)

# --- Main Launcher Polling Loop ---
while selection is None:
    now = time.ticks_ms()
    
    # 1. Hardware Button Polling
    if beaper.SW3.value() == 0:
        selection = "SUMO"
    elif beaper.SW4.value() == 0:
        selection = "PET"

    # 2. Optical Morse Polling
    last_char, current_word = robot.poll_morse_command()
    if current_word != display_word:
        display_word = current_word
        draw_boot_menu(get_battery_voltage(), display_word)
        last_hud_update = now

    # Check for Morse Trigger Keywords
    if "BOT" in current_word:
        selection = "SUMO"
    elif "PET" in current_word:
        selection = "PET"

    # 3. Periodic HUD Refresh for Battery Level
    if time.ticks_diff(now, last_hud_update) >= HUD_UPDATE_MS:
        draw_boot_menu(get_battery_voltage(), display_word)
        last_hud_update = now

    time.sleep_ms(10)

# --- Audio Confirmation ---
robot.play_tone(1000, 150)
robot.clear_morse_buffer()

# --- Personality Hand-off Execution ---
if selection == "SUMO":
    lcd.fill(lcd.BLACK)
    lcd.text16("LOADING SUMO...", 30, 90, lcd.GREEN)
    lcd.update()
    time.sleep_ms(500)
    import mode_sumo_0903  # Transfers execution directly to August 28 Sumo Engine

elif selection == "PET":
    lcd.fill(lcd.BLACK)
    lcd.text16("LOADING FLOOR PET...", 20, 90, lcd.YELLOW)
    lcd.update()
    time.sleep_ms(500)
    import mode_pet_0903   # Transfers execution to Wi-Fi Floor Pet Engine
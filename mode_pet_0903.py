"""
================================================================================
BEAPER Floor Pet - Full Screen Concentric Radar & Clean ToF Polling
Original Integrated Creation Author: cache4pat
MODULE: mode_pet_0903.py
DATE: Sept 3, 2026 
Uses June 2026 mirobotech cloned imports on modified BEAPER-Nano hardware
================================================================================
"""

import network
import socket
import time
import math
from machine import Pin, SPI
import BEAPER_Nano as beaper
import LCDconfig_Nano as lcd_config
from beaper_hardware_0903 import BeaperHardware

# --- Initialize Hardware ---
robot = BeaperHardware()

spi = SPI(2, baudrate=60000000, sck=Pin(48), mosi=Pin(38), miso=None)
spi.deinit()
lcd = lcd_config.config()

# Custom Dim Color for Grid
GRID_COLOR = const(0x18E5) 

# --- Setup Wi-Fi AP with Static IP (192.168.4.9) ---
ap = network.WLAN(network.AP_IF)
ap.active(True)
ap.ifconfig(('192.168.4.9', '255.255.255.0', '192.168.4.9', '8.8.8.8'))
ap.config(essid="BEAPER-PET", password="password123")

while not ap.active():
    time.sleep_ms(100)

# Non-Blocking Socket
server = socket.socket()
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(('0.0.0.0', 80))
server.listen(2)
server.setblocking(False)

# --- LCD Radar Engine Layout ---
CENTER_X = 120
CENTER_Y = 132
RADAR_RADIUS = 102  # Fits screen below top header

# Pre-calculate log divisors for performance
LOG_SONAR_MAX = math.log(1.0 + 50.0)   # Max 50 cm
LOG_TOF_MAX   = math.log(1.0 + 300.0)  # Max 300 mm

def draw_circle(lcd_obj, x0, y0, radius, color):
    """Bresenham's Midpoint Circle Algorithm for MicroPython LCD drivers."""
    x = radius
    y = 0
    err = 0

    while x >= y:
        lcd_obj.pixel(x0 + x, y0 + y, color)
        lcd_obj.pixel(x0 + y, y0 + x, color)
        lcd_obj.pixel(x0 - y, y0 + x, color)
        lcd_obj.pixel(x0 - x, y0 + y, color)
        lcd_obj.pixel(x0 - x, y0 - y, color)
        lcd_obj.pixel(x0 - y, y0 - x, color)
        lcd_obj.pixel(x0 + y, y0 - x, color)
        lcd_obj.pixel(x0 + x, y0 - y, color)

        if err <= 0:
            y += 1
            err += 2 * y + 1
        if err > 0:
            x -= 1
            err -= 2 * x + 1

def draw_radar_hud(sonar_cm, tof_mm, status_str="LINK ACTIVE"):
    lcd.fill(lcd.BLACK)
    
    # Top Single-Line Header
    lcd.text16("PET Live Link", 56, 6, lcd.CYAN)
    
    # Concentric Logarithmic Radar Circles Backdrop (5 Range Rings)
    log_rings = [10, 30, 70, 150, 300]  # Ring distance markers in mm
    for r_mm in log_rings:
        r_pixel = int((math.log(1.0 + r_mm) / LOG_TOF_MAX) * RADAR_RADIUS)
        draw_circle(lcd, CENTER_X, CENTER_Y, r_pixel, GRID_COLOR)
        
    # Crosshairs & Center Marker
    lcd.line(CENTER_X - RADAR_RADIUS, CENTER_Y, CENTER_X + RADAR_RADIUS, CENTER_Y, GRID_COLOR)
    lcd.line(CENTER_X, CENTER_Y - RADAR_RADIUS, CENTER_X, CENTER_Y + RADAR_RADIUS, GRID_COLOR)
    lcd.rect(CENTER_X - 4, CENTER_Y - 4, 8, 8, lcd.WHITE)
    
    # Plot Front Sonar (Log Scale Mapping)
    if 2.0 <= sonar_cm <= 50.0:
        log_val = math.log(1.0 + sonar_cm)
        scaled_sonar = int((log_val / LOG_SONAR_MAX) * RADAR_RADIUS)
        blip_y = CENTER_Y - scaled_sonar
        
        lcd.fill_rect(CENTER_X - 4, blip_y - 4, 8, 8, lcd.GREEN)
        lcd.text16(f"{int(sonar_cm)}cm", CENTER_X + 10, blip_y - 5, lcd.GREEN)

    # Plot Rear ToF (Log Scale Mapping)
    if 10 <= tof_mm <= 300:
        log_val = math.log(1.0 + tof_mm)
        scaled_tof = int((log_val / LOG_TOF_MAX) * RADAR_RADIUS)
        blip_y = CENTER_Y + scaled_tof
        
        lcd.fill_rect(CENTER_X - 4, blip_y - 4, 8, 8, lcd.RED)
        lcd.text16(f"{int(tof_mm)}mm", CENTER_X + 10, blip_y - 5, lcd.RED)

    # Emergency Overlay Bar
    if "BLOCK" in status_str:
        lcd.fill_rect(10, 26, 220, 22, lcd.RED)
        lcd.text16(status_str, 20, 29, lcd.WHITE)
        
    lcd.update()

# --- Web UI ---
HTML_PAGE = """<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>BEAPER Joystick</title>
    <style>
        body { background:#0d1117; color:#58a6ff; font-family:sans-serif; text-align:center; margin:0; overflow:hidden; touch-action:none; }
        h2 { margin-top:15px; margin-bottom:5px; }
        #canvas-container { display:flex; justify-content:center; align-items:center; height:320px; }
        canvas { background:#161b22; border:2px solid #30363d; border-radius:50%; }
        .stop-btn { background:#da3633; color:#fff; border:none; padding:15px 40px; font-size:18px; font-weight:bold; border-radius:10px; margin-top:10px; }
    </style>
</head>
<body>
    <h2>BEAPER JOYSTICK</h2>
    <p style="color:#8b949e; margin-top:0;">Drag stick to drive</p>
    
    <div id="canvas-container">
        <canvas id="joystick" width="260" height="260"></canvas>
    </div>
    
    <button class="stop-btn" onclick="sendCmd('STOP')">STOP</button>

    <script>
        const canvas = document.getElementById('joystick');
        const ctx = canvas.getContext('2d');
        const radius = 100;
        const centerX = canvas.width / 2;
        const centerY = canvas.height / 2;
        let active = false;
        let lastCmd = 'STOP';

        function drawStick(x, y) {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.beginPath();
            ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
            ctx.strokeStyle = '#30363d';
            ctx.lineWidth = 6;
            ctx.stroke();
            
            ctx.beginPath();
            ctx.arc(x, y, 35, 0, Math.PI * 2);
            ctx.fillStyle = '#58a6ff';
            ctx.fill();
            ctx.strokeStyle = '#79c0ff';
            ctx.lineWidth = 3;
            ctx.stroke();
        }

        function sendCmd(cmd) {
            if (cmd !== lastCmd) {
                lastCmd = cmd;
                fetch('/cmd?dir=' + cmd).catch(e => {});
            }
        }

        function handleMove(e) {
            if (!active) return;
            const touch = e.touches ? e.touches[0] : e;
            const rect = canvas.getBoundingClientRect();
            let dx = touch.clientX - rect.left - centerX;
            let dy = touch.clientY - rect.top - centerY;
            const dist = Math.hypot(dx, dy);

            if (dist > radius) {
                dx = (dx / dist) * radius;
                dy = (dy / dist) * radius;
            }

            drawStick(centerX + dx, centerY + dy);

            if (dist < 25) {
                sendCmd('STOP');
            } else if (Math.abs(dx) > Math.abs(dy)) {
                sendCmd(dx > 0 ? 'RIGHT' : 'LEFT');
            } else {
                sendCmd(dy > 0 ? 'REV' : 'FWD');
            }
        }

        function endMove() {
            active = false;
            drawStick(centerX, centerY);
            sendCmd('STOP');
        }

        canvas.addEventListener('touchstart', (e) => { active = true; handleMove(e); });
        canvas.addEventListener('touchmove', handleMove);
        canvas.addEventListener('touchend', endMove);
        canvas.addEventListener('mousedown', (e) => { active = true; handleMove(e); });
        window.addEventListener('mousemove', handleMove);
        window.addEventListener('mouseup', endMove);

        drawStick(centerX, centerY);
    </script>
</body>
</html>
"""

# Reset Motors & Render Radar
robot.motors_stop()
draw_radar_hud(99, 999, "READY")
last_radar_update = 0
last_turn_pulse = 0
pulse_state = False
current_dir = "STOP"

# --- Main Engine Loop ---
while True:
    now = time.ticks_ms()
    
    # 1. Non-Blocking Socket Handler
    try:
        conn, addr = server.accept()
        req = conn.recv(512).decode('utf-8')
        
        if 'GET /cmd?dir=' in req:
            cmd = req.split('GET /cmd?dir=')[1].split(' ')[0]
            current_dir = cmd
            conn.send('HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nOK')
        else:
            conn.send('HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n')
            conn.sendall(HTML_PAGE)
            
        conn.close()
    except OSError:
        pass

    # 2. Sensor Sampling & Safety Control
    if time.ticks_diff(now, last_radar_update) >= 120:
        sonar_d = robot.read_sonar(now)
        
        # Service ToF interrupts & update distance
        robot.check_rear_threat(now)
        tof_d = robot.rear_dist_mm

        status_msg = "LIVE LINK"

        # Direction Execution with Safety Stops
        if current_dir == 'FWD':
            if 1.0 <= sonar_d <= 8.0:
                robot.motors_stop()
                status_msg = "FRONT BLOCKED"
            else:
                robot.drive_forward()

        elif current_dir == 'REV':
            if 0 < tof_d <= 45:
                robot.motors_stop()
                status_msg = "REAR BLOCKED"
            else:
                robot.drive_reverse()

        elif current_dir in ('LEFT', 'RIGHT'):
            if time.ticks_diff(now, last_turn_pulse) >= (50 if pulse_state else 100):
                pulse_state = not pulse_state
                last_turn_pulse = now
                
                if pulse_state:
                    if current_dir == 'LEFT': robot.spin_left()
                    else: robot.spin_right()
                else:
                    robot.motors_stop()

        elif current_dir == 'STOP':
            robot.motors_stop()

        draw_radar_hud(sonar_d, tof_d, status_msg)
        last_radar_update = now

    time.sleep_ms(10)
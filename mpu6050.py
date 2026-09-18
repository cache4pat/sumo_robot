"""
================================================================================
Minimal MicroPython MPU6050 I2C Driver
Module: mpu6050.py
Project: BEAPER Nano Autonomous Sumo Bot
Author: Custom driver generated via Google Gemini / cache4pat
Created: August 1, 2026

Description:
    Lightweight, bare-metal MicroPython driver for reading raw accelerometer,
    gyroscope, and Z-axis yaw values from an MPU-6050 sensor via I2C.
    Designed for state-machine rotation tracking without heavy library overhead.

Reference:
    InvenSense MPU-6050 Register Map and Descriptions Rev 4.2 (Registers 0x3B, 0x47, 0x6B)
================================================================================
"""

import ustruct
from machine import I2C

class MPU6050:
    def __init__(self, i2c, addr=0x68):
        self.i2c = i2c
        self.addr = addr
        # Wake up MPU-6050 (clear sleep bit in PWR_MGMT_1 register)
        self.i2c.writeto_mem(self.addr, 0x6B, bytes([0x00]))

    def get_raw_values(self):
        # Read 14 bytes starting at register 0x3B (Accel X/Y/Z, Temp, Gyro X/Y/Z)
        data = self.i2c.readfrom_mem(self.addr, 0x3B, 14)
        v = ustruct.unpack('>hhhhhhh', data)
        return {
            'Ax': v[0], 'Ay': v[1], 'Az': v[2],
            'Temp': v[3] / 340.0 + 36.53,
            'Gx': v[4], 'Gy': v[5], 'Gz': v[6]
        }

    def get_gyro_z(self):
        """Returns raw Z-axis gyro value (Yaw rate)."""
        data = self.i2c.readfrom_mem(self.addr, 0x47, 2)
        return ustruct.unpack('>h', data)[0]
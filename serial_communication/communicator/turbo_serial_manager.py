#!/usr/bin/env python3
"""
turbo_serial_manager.py

This module provides functions to configure the serial port for turbo pump controllers,
with full support for RS485-specific settings. Using pySerial's RS485Settings, this module
configures the port for half-duplex communication with correct RTS levels and timing delays.

RS485 Configuration Details:
  - rts_level_for_tx: The RTS level used during transmission.
  - rts_level_for_rx: The RTS level used during reception.
  - delay_before_tx: Delay after setting RTS for transmission (in seconds).
  - delay_before_rx: Delay after switching RTS to reception (in seconds).

These settings ensure compatibility with industry-standard RS485 devices. In addition,
baud rate, parity, and other serial parameters are configured as required.

Usage Example:
    from turbo_serial_manager import configure_turbo_serial
    ser = configure_turbo_serial(
        port="COM3",
        baudrate=9600,
        use_rs485=True,
        rts_level_for_tx=False,
        rts_level_for_rx=True,
        delay_before_tx=0.005,
        delay_before_rx=0.005,
        parity="N",
        bytesize=8,
        stopbits=1.0,
        timeout=1.0,
        write_timeout=1.0
    )
"""

import serial
from serial.rs485 import RS485Settings


def configure_turbo_serial(port: str, baudrate: int, use_rs485: bool,
                           rts_level_for_tx: bool = False, rts_level_for_rx: bool = True,
                           delay_before_tx: float = 0.005, delay_before_rx: float = 0.005,
                           parity: str = "N", bytesize: int = 8, stopbits: float = 1.0,
                           timeout: float = 1.0, write_timeout: float = 1.0,
                           termination_resistor: bool = False) -> serial.Serial:
    """
    Configures and returns a serial.Serial object for turbo pump communication.

    Args:
        port (str): Serial port (e.g., "COM3" or "/dev/ttyUSB0").
        baudrate (int): Communication baud rate.
        use_rs485 (bool): True to enable RS485 mode.
        rts_level_for_tx (bool): RTS level during transmission (commonly False).
        rts_level_for_rx (bool): RTS level during reception (commonly True).
        delay_before_tx (float): Delay in seconds before transmitting after setting RTS (e.g., 0.005).
        delay_before_rx (float): Delay in seconds after switching to receive mode (e.g., 0.005).
        parity (str): Parity setting ("N", "E", "O", etc.). RS485 usually uses "N".
        bytesize (int): Number of data bits.
        stopbits (float): Number of stop bits.
        timeout (float): Read timeout in seconds.
        write_timeout (float): Write timeout in seconds.
        termination_resistor (bool): If True, indicates that the termination resistor is enabled.
                                      (Note: Actual termination resistor handling is typically hardware-specific.)

    Returns:
        serial.Serial: A configured serial port object.
    """
    ser = serial.Serial(
        port=port,
        baudrate=baudrate,
        bytesize=bytesize,
        parity=parity,
        stopbits=stopbits,
        timeout=timeout,
        write_timeout=write_timeout
    )
    if use_rs485:
        ser.rs485_mode = RS485Settings(
            rts_level_for_tx=rts_level_for_tx,
            rts_level_for_rx=rts_level_for_rx,
            delay_before_tx=delay_before_tx,
            delay_before_rx=delay_before_rx
        )
    # Note: Handling of a termination resistor is typically done externally or via a GPIO.
    return ser

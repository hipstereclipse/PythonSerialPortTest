#!/usr/bin/env python3
"""
device_simulator.py

This module implements the DeviceSimulator class which emulates hardware devices
(gauges or turbos) for testing without physical hardware. It replicates real-world device
behavior by dynamically generating responses and maintaining an internal state so that
write commands affect subsequent read commands.

Features for Gauges:
  - Supports multiple gauge types (e.g., CDG025D, CDG045D, MPG500, PPG550, etc).
  - If the configured gauge_type starts with "CDG", a constant 9-byte continuous output
    frame is produced to mimic a CDG gauge (including checksum calculation).
  - For non-CDG gauges, dynamic values (pressure and temperature) are generated using
    configurable ranges, noise, and delays.
  - Simulated set commands (e.g., "set_pressure", "set_temperature", "data_tx_mode") update
    internal state and return an acknowledgment.
  - A dummy protocol object is attached (via DummyProtocol) so UI components can read
    .protocol._command_defs without error.

Features for Turbos:
  - Simulates basic turbo parameters (speed, motor_on) with support for both read and set commands.
  - When simulating a turbo, no physical port is required (a default dummy port is assumed).

Interface:
  Implements connect(), disconnect(), send_command(), read_continuous(), stop_continuous_reading(),
  set_output_format(), and set_rs_mode()—matching the real communicator’s interface.

Usage Example:
    simulator = DeviceSimulator(device_type="gauge", config={
        "gauge_type": "CDG045D",
        "pressure_range": (0.1, 1000),  # in psi (or your unit)
        "temp_range": (-50, 300),       # in °C
        "noise_level": 0.05,
        "response_delay": 0.1,
        "error_probability": 0.01
    })
    simulator.connect()
    response = simulator.send_command(GaugeCommand(name="pressure", command_type="?"))
    print(response.formatted_data)
"""

import random
import time
import logging
from typing import Callable, Dict, Any, Optional

from serial_communication.models import GaugeCommand, GaugeResponse
from serial_communication.config import GAUGE_PARAMETERS


class DummyProtocol:
    """
    A dummy protocol class for simulation purposes.
    It exposes the _command_defs attribute populated from GAUGE_PARAMETERS for a given gauge type.
    """

    def __init__(self, gauge_type: str = "PPG550"):
        self._command_defs = GAUGE_PARAMETERS.get(gauge_type, {}).get("commands", {})


class DeviceSimulator:
    """
    Simulates hardware devices (gauges or turbos) for testing without physical hardware.

    For gauges:
      - Maintains an internal state (e.g., pressure, temperature) and returns simulated values.
      - If the gauge type (from config) starts with "CDG", returns a fixed 9-byte continuous output frame.
      - Supports simulated set commands that update the state (e.g., "set_pressure", "set_temperature", "data_tx_mode").

    For turbos:
      - Maintains state for speed and motor state.
      - In simulation, no physical port is required.

    This class implements the communicator interface:
      connect(), disconnect(), send_command(), read_continuous(), stop_continuous_reading(),
      set_output_format(), and set_rs_mode().
    """

    def __init__(self, device_type: str = "gauge", config: Optional[Dict[str, Any]] = None,
                 logger: Optional[logging.Logger] = None):
        self.device_type = device_type.lower()
        # Always define rs_mode for compatibility
        self.rs_mode = "RS232"
        if self.device_type == "gauge":
            self.config = config or {
                "gauge_type": "PPG550",  # default gauge type; user may set to "CDG025D", "CDG045D", "MPG500", etc.
                "pressure_range": (0.1, 1000),  # e.g., in psi
                "temp_range": (-50, 300),  # in °C
                "noise_level": 0.05,
                "response_delay": 0.1,
                "error_probability": 0.0
            }
            self.state = {
                "pressure": random.uniform(*self.config["pressure_range"]),
                "temperature": random.uniform(*self.config["temp_range"]),
                "data_tx_mode": "0"
            }
            gauge_type = self.config.get("gauge_type", "PPG550")
            self.protocol = DummyProtocol(gauge_type=gauge_type)
        elif self.device_type == "turbo":
            self.config = config or {
                "speed_range": (1000, 5000),
                "motor_on": False,
                "noise_level": 0.05,
                "response_delay": 0.1,
                "error_probability": 0.0
            }
            self.state = {
                "speed": random.randint(*self.config["speed_range"]),
                "motor_on": self.config.get("motor_on", False)
            }
            self.protocol = None  # For turbos, no protocol definitions are needed.
        else:
            raise ValueError("Unsupported device type. Use 'gauge' or 'turbo'.")
        self.connected = False
        self.logger = logger or logging.getLogger("DeviceSimulator")
        self.logger.setLevel(logging.DEBUG)
        self.output_format = "ASCII"

    def connect(self) -> bool:
        self.logger.debug("Simulated device connecting...")
        # For turbos, if no port is provided, ignore port selection.
        time.sleep(0.1)
        self.connected = True
        self.logger.info("Simulated device connected.")
        return True

    def disconnect(self) -> bool:
        self.logger.debug("Simulated device disconnecting...")
        time.sleep(0.05)
        self.connected = False
        self.logger.info("Simulated device disconnected.")
        return True

    def stop_continuous_reading(self) -> None:
        self.logger.debug("Simulated stop continuous reading.")

    def set_output_format(self, fmt: str) -> None:
        self.output_format = fmt
        self.logger.debug(f"Simulator output format set to: {fmt}")

    def set_rs_mode(self, mode: str) -> None:
        self.rs_mode = mode
        self.logger.debug(f"Simulator RS mode set to: {mode}")

    def send_command(self, command: GaugeCommand) -> GaugeResponse:
        if not self.connected:
            error_msg = "Simulated device not connected."
            self.logger.error(error_msg)
            return GaugeResponse(raw_data=b"", formatted_data="", success=False, error_message=error_msg)

        time.sleep(self.config.get("response_delay", 0.1))
        self.logger.debug(f"Simulated command received: {command.name}")

        # Simulate error response if random chance triggers it.
        if random.random() < self.config.get("error_probability", 0.0):
            error_text = "ERR_DISCONNECTED"
            self.logger.debug(f"Simulated error response: {error_text}")
            return GaugeResponse(raw_data=error_text.encode("utf-8"),
                                 formatted_data=error_text,
                                 success=False,
                                 error_message=error_text)

        # Handle gauge simulation.
        if self.device_type == "gauge":
            gauge_type = self.config.get("gauge_type", "PPG550")
            if gauge_type.startswith("CDG"):
                # Produce a constant 9-byte CDG frame.
                start_byte = 0x07
                page = 0x01
                status = 0x00
                error = 0x00
                # Use current pressure state converted to an integer (simulate fixed measurement).
                measurement = int(self.state.get("pressure", 30000))
                meas_bytes = measurement.to_bytes(2, byteorder="big", signed=True)
                cmd_code = 0x00
                sensor_type = 0x00
                frame = bytearray([start_byte, page, status, error])
                frame.extend(meas_bytes)
                frame.extend([cmd_code, sensor_type])
                checksum = sum(frame[1:8]) & 0xFF
                frame.append(checksum)
                simulated_raw = bytes(frame)
                formatted = " ".join(f"{b:02X}" for b in simulated_raw)
                self.logger.debug(f"Simulated CDG frame: {formatted}")
                return GaugeResponse(raw_data=simulated_raw, formatted_data=formatted, success=True)
            else:
                # For non-CDG gauges, support both read and set commands.
                if command.command_type == "!":
                    if command.name == "data_tx_mode":
                        new_val = command.parameters.get("value", "0")
                        self.state["data_tx_mode"] = new_val
                        response_data = f"DataTxMode set to {new_val}"
                    elif command.name == "set_pressure":
                        try:
                            new_pressure = float(command.parameters.get("value", 0))
                            self.state["pressure"] = new_pressure
                            response_data = f"Pressure set to {new_pressure:.2f} psi"
                        except Exception as e:
                            response_data = f"Error: Invalid pressure value ({e})"
                    elif command.name == "set_temperature":
                        try:
                            new_temp = float(command.parameters.get("value", 0))
                            self.state["temperature"] = new_temp
                            response_data = f"Temperature set to {new_temp:.1f}°C"
                        except Exception as e:
                            response_data = f"Error: Invalid temperature value ({e})"
                    elif command.name == "calibrate":
                        # Simulate calibration delay and acknowledgement.
                        time.sleep(2.0 + random.uniform(-0.1, 0.1))
                        response_data = "Calibration successful"
                    else:
                        response_data = f"{command.name} executed successfully"
                else:
                    if command.name == "pressure":
                        base = random.uniform(*self.config.get("pressure_range", (0.1, 1000)))
                        noise = base * self.config.get("noise_level", 0.05)
                        self.state["pressure"] = base + random.uniform(-noise, noise)
                        response_data = f"{self.state['pressure']:.2f} psi"
                    elif command.name == "temperature":
                        base = random.uniform(*self.config.get("temp_range", (-50, 300)))
                        noise = base * self.config.get("noise_level", 0.05)
                        self.state["temperature"] = base + random.uniform(-noise, noise)
                        response_data = f"{self.state['temperature']:.1f}°C"
                    else:
                        response_data = f"{command.name} executed successfully"
                simulated_raw = response_data.encode("utf-8")
                self.logger.debug(f"Simulated response: {response_data}")
                return GaugeResponse(raw_data=simulated_raw, formatted_data=response_data, success=True)

        elif self.device_type == "turbo":
            # For turbo simulation, ignore port issues.
            if command.command_type == "!":
                if command.name == "set_speed":
                    try:
                        new_speed = int(command.parameters.get("value", 0))
                        low, high = self.config.get("speed_range", (1000, 5000))
                        if new_speed < low or new_speed > high:
                            response_data = f"Error: Speed out of range ({low}-{high} RPM)"
                        else:
                            self.state["speed"] = new_speed
                            response_data = f"Speed set to {new_speed} RPM"
                    except Exception as e:
                        response_data = f"Error: Invalid speed value ({e})"
                elif command.name == "motor_on":
                    if command.command_type == "!":
                        value = command.parameters.get("value")
                        self.state["motor_on"] = (value == "1")
                        response_data = f"Motor set to {'On' if self.state['motor_on'] else 'Off'}"
                    else:
                        response_data = "On" if self.state.get("motor_on", False) else "Off"
                else:
                    response_data = f"{command.name} executed successfully"
            else:
                if command.name == "get_speed":
                    response_data = f"{self.state.get('speed', 0)} RPM"
                else:
                    response_data = f"{command.name} executed successfully"
            simulated_raw = response_data.encode("utf-8")
            self.logger.debug(f"Simulated turbo response: {response_data}")
            return GaugeResponse(raw_data=simulated_raw, formatted_data=response_data, success=True)

        else:
            response_data = f"{command.name} executed successfully"
            simulated_raw = response_data.encode("utf-8")
            self.logger.debug(f"Simulated response: {response_data}")
            return GaugeResponse(raw_data=simulated_raw, formatted_data=response_data, success=True)

    def read_continuous(self, callback: Callable[[GaugeResponse], None], update_interval: float) -> None:
        while self.connected:
            response = self.send_command(GaugeCommand(name="pressure", command_type="?"))
            callback(response)
            time.sleep(update_interval)

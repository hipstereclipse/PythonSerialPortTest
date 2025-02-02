#!/usr/bin/env python3
"""
device_simulator.py

This module implements the DeviceSimulator class which simulates hardware devices
(gauges or turbos) for testing purposes. It dynamically generates realistic responses
and maintains an internal state so that write commands affect subsequent read commands.
It implements the same interface as the real communicator (including connect(),
disconnect(), send_command(), read_continuous(), stop_continuous_reading(), and set_output_format())
so that the GUI can be used without changes when physical hardware is unavailable.

A dummy protocol is attached for gauges so that UI components (e.g., CommandFrame)
can access .protocol._command_defs without error.

Usage Example:
    simulator = DeviceSimulator(device_type="gauge", config={
        "pressure_range": (0.1, 100),
        "temp_range": (20, 80),
        "response_delay": 0.1,
        "noise_level": 0.05,
        "gauge_type": "PPG550"
    })
    simulator.connect()
    response = simulator.send_command(command)
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
    It simply exposes a _command_defs attribute from the configuration for a given gauge type.
    """

    def __init__(self, gauge_type: str = "PPG550"):
        self._command_defs = GAUGE_PARAMETERS.get(gauge_type, {}).get("commands", {})


class DeviceSimulator:
    """
    Simulates hardware devices (gauges or turbos) for testing purposes.

    The simulator maintains an internal state so that write commands (e.g., setting speed)
    persist over subsequent reads. It returns randomized, plausible values based on configured ranges,
    and simulates delays for each response.

    This class implements the same interface as a real communicator:
      - connect(), disconnect(), send_command(), read_continuous(), stop_continuous_reading(), set_output_format()
    For gauge simulation, a dummy protocol is attached (accessible via .protocol).
    """

    def __init__(self, device_type: str = "gauge", config: Optional[Dict[str, Any]] = None,
                 logger: Optional[logging.Logger] = None):
        """
        Initializes the simulator.

        Args:
            device_type (str): "gauge" or "turbo"
            config (dict, optional): Simulation parameters.
                For gauges (default):
                  - pressure_range: (min, max) in mbar
                  - temp_range: (min, max) in °C
                  - noise_level: fractional noise (default 0.05)
                  - response_delay: seconds delay (default 0.1)
                  - gauge_type: e.g., "PPG550" (for dummy protocol lookup)
                For turbos (default):
                  - speed_range: (min, max) in RPM
                  - motor_on: initial state (default False)
                  - noise_level: fractional noise (default 0.05)
                  - response_delay: seconds delay (default 0.1)
            logger (logging.Logger, optional): Logger instance.
        """
        self.device_type = device_type.lower()
        if self.device_type == "gauge":
            self.config = config or {
                "pressure_range": (0.1, 100),
                "temp_range": (20, 80),
                "noise_level": 0.05,
                "response_delay": 0.1,
                "gauge_type": "PPG550"
            }
            self.state = {
                "pressure": random.uniform(*self.config["pressure_range"]),
                "temperature": random.uniform(*self.config["temp_range"])
            }
            # Attach a dummy protocol for command definitions.
            gauge_type = self.config.get("gauge_type", "PPG550")
            self.protocol = DummyProtocol(gauge_type=gauge_type)
        elif self.device_type == "turbo":
            self.config = config or {
                "speed_range": (1000, 5000),
                "motor_on": False,
                "noise_level": 0.05,
                "response_delay": 0.1
            }
            self.state = {
                "speed": random.randint(*self.config["speed_range"]),
                "motor_on": self.config.get("motor_on", False)
            }
            self.protocol = None  # You can add a dummy protocol for turbos if needed.
        else:
            raise ValueError("Unsupported device type. Use 'gauge' or 'turbo'.")
        self.connected = False
        self.logger = logger or logging.getLogger("DeviceSimulator")
        self.logger.setLevel(logging.DEBUG)
        # Store output format; default to "ASCII"
        self.output_format = "ASCII"

    def connect(self) -> bool:
        """
        Simulates establishing a connection.

        Returns:
            bool: True indicating a successful simulated connection.
        """
        self.logger.debug("Simulated device connecting...")
        time.sleep(0.1)  # Simulated delay
        self.connected = True
        self.logger.info("Simulated device connected.")
        return True

    def disconnect(self) -> bool:
        """
        Simulates disconnecting the device.

        Returns:
            bool: True if successfully disconnected.
        """
        self.logger.debug("Simulated device disconnecting...")
        time.sleep(0.05)
        self.connected = False
        self.logger.info("Simulated device disconnected.")
        return True

    def stop_continuous_reading(self) -> None:
        """
        Simulates stopping any continuous reading loops.
        For simulation purposes, this is a no-op.
        """
        self.logger.debug("Simulated stop continuous reading.")

    def set_output_format(self, fmt: str) -> None:
        """
        Sets the output format for simulated responses.
        This is a stub to allow compatibility with code that calls set_output_format().

        Args:
            fmt (str): The desired output format.
        """
        self.output_format = fmt
        self.logger.debug(f"Simulator output format set to: {fmt}")

    def send_command(self, command: GaugeCommand) -> GaugeResponse:
        """
        Simulates processing a command and returns a simulated response.
        Updates internal state for write commands and returns dynamic values for read commands.

        Args:
            command (GaugeCommand): The command to simulate.

        Returns:
            GaugeResponse: A simulated response.
        """
        if not self.connected:
            error_msg = "Simulated device not connected."
            self.logger.error(error_msg)
            return GaugeResponse(raw_data=b"", formatted_data="", success=False, error_message=error_msg)

        # Simulate response delay.
        delay = self.config.get("response_delay", 0.1)
        time.sleep(delay)
        self.logger.debug(f"Simulated command received: {command.name}")

        response_data = ""
        if self.device_type == "gauge":
            if command.name == "pressure":
                base = random.uniform(*self.config.get("pressure_range", (0.1, 100)))
                noise = base * self.config.get("noise_level", 0.05)
                self.state["pressure"] = base + random.uniform(-noise, noise)
                response_data = f"{self.state['pressure']:.2f} mbar"
            elif command.name == "temperature":
                base = random.uniform(*self.config.get("temp_range", (20, 80)))
                noise = base * self.config.get("noise_level", 0.05)
                self.state["temperature"] = base + random.uniform(-noise, noise)
                response_data = f"{self.state['temperature']:.1f}°C"
            else:
                response_data = f"{command.name} executed successfully"
        elif self.device_type == "turbo":
            if command.name == "get_speed":
                response_data = f"{self.state.get('speed', 0)} RPM"
            elif command.name == "set_speed" and command.command_type == "!":
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
            response_data = f"{command.name} executed successfully"

        # Use UTF-8 encoding to support non-ASCII characters (like the degree symbol)
        simulated_raw = response_data.encode("utf-8")
        self.logger.debug(f"Simulated response: {response_data}")
        return GaugeResponse(
            raw_data=simulated_raw,
            formatted_data=response_data,
            success=True
        )

    def read_continuous(self, callback: Callable[[GaugeResponse], None], update_interval: float) -> None:
        """
        Simulates continuous reading by periodically generating responses.

        Args:
            callback (Callable): Function to call with each simulated GaugeResponse.
            update_interval (float): Time in seconds between responses.
        """
        while self.connected:
            simulated_response = self.send_command(GaugeCommand(name="pressure", command_type="?"))
            callback(simulated_response)
            time.sleep(update_interval)

#!/usr/bin/env python3
"""
test_simulated_gauge.py

A simple test script to validate the DeviceSimulator for gauges.
This script creates a simulator for a specified gauge type, connects it,
sends several commands, and prints the responses.
"""

import logging
from serial_communication.device_simulator import DeviceSimulator
from serial_communication.models import GaugeCommand

def main():
    logger = logging.getLogger("TestSimulator")
    logger.setLevel(logging.DEBUG)
    # Create a simulator configuration for a CDG gauge (for example)
    sim_config = {
        "gauge_type": "CDG045D",
        "pressure_range": (0.1, 1000),
        "temp_range": (-50, 300),
        "noise_level": 0.05,
        "response_delay": 0.1,
        "error_probability": 0.0
    }
    simulator = DeviceSimulator(device_type="gauge", config=sim_config, logger=logger)
    simulator.set_output_format("Hex")
    if simulator.connect():
        # Test continuous (CDG) output by sending a "pressure" command.
        cmd_pressure = GaugeCommand(name="pressure", command_type="?")
        response = simulator.send_command(cmd_pressure)
        print("Pressure Response:", response.formatted_data)
        # Test temperature command
        cmd_temp = GaugeCommand(name="temperature", command_type="?")
        response = simulator.send_command(cmd_temp)
        print("Temperature Response:", response.formatted_data)
        # Disconnect simulator
        simulator.disconnect()
    else:
        print("Failed to connect to simulator.")

if __name__ == "__main__":
    main()

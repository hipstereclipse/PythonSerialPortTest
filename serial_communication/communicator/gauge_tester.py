"""
gauge_tester.py
Provides GaugeTester class for testing gauge connections, baud rates, and ENQ.
"""

import time
from typing import Optional

from ..models import GaugeCommand, GaugeResponse
from ..config import GAUGE_PARAMETERS
from .gauge_communicator import GaugeCommunicator
from .intelligent_command_sender import IntelligentCommandSender


class GaugeTester:
    """
    Handles gauge testing functionality including baud rate tests, connection tests, and ENQ checks.
    """

    def __init__(self, communicator: GaugeCommunicator, logger):
        self.communicator = communicator
        self.logger = logger
        self.gauge_type = communicator.gauge_type
        self.params = GAUGE_PARAMETERS[self.gauge_type]
        self.protocol = communicator.protocol
        self.test_commands = self._get_test_commands()

    def _get_test_commands(self) -> dict:
        """Get test commands specific to the gauge type."""
        commands = {}
        if self.gauge_type in ["PCG550", "PSG550", "MAG500", "MPG500"]:
            commands.update({
                "product_name": {"pid": 208, "cmd": 1, "desc": "Read product name"},
                "software_version": {"pid": 218, "cmd": 1, "desc": "Read software version"},
                "serial_number": {"pid": 207, "cmd": 1, "desc": "Read serial number"},
            })
        elif self.gauge_type == "PPG550":
            commands.update({
                "product_name": {"cmd": "PRD", "type": "read"},
                "software_version": {"cmd": "SWV", "type": "read"},
                "serial_number": {"cmd": "SER", "type": "read"},
            })
        elif self.gauge_type == "CDG045D":
            commands.update({
                "software_version": {"cmd": "read", "name": "software_version"},
                "unit": {"cmd": "read", "name": "unit"},
                "gauge_type": {"cmd": "read", "name": "cdg_type"},
            })
        # Add more if needed for other gauges
        return commands

    def test_connection(self) -> bool:
        """Attempt a simple connection test by sending protocol test commands."""
        if not self.communicator.ser or not self.communicator.ser.is_open:
            return False

        try:
            for cmd_bytes in self.communicator.protocol.test_commands():
                formatted_cmd = self.communicator.format_response(cmd_bytes)
                self.logger.debug(f"Testing connection with command: {formatted_cmd}")

                result = IntelligentCommandSender.send_manual_command(
                    self.communicator,
                    cmd_bytes.hex(' '),
                    self.communicator.output_format
                )

                if result["success"]:
                    if "response_formatted" in result:
                        self.logger.debug(f"Test response: {result['response_formatted']}")
                        return True
                    else:
                        self.logger.debug("Test response missing formatted data")
                else:
                    self.logger.debug(f"Test command failed: {result.get('error', 'Unknown error')}")
            return False

        except Exception as e:
            self.logger.error(f"Connection test failed: {str(e)}")
            return False

    def try_all_baud_rates(self, port: str) -> bool:
        """
        Test connecting with multiple baud rates, returning True on success or False if all fail.
        """
        from ..config import BAUD_RATES

        # Start with the gauge's default
        baud_rates = [
            self.params.get("baudrate", 9600),
            57600, 38400, 19200, 9600
        ]
        # Remove duplicates, preserving order
        baud_rates = list(dict.fromkeys(baud_rates))

        self.logger.info("\n=== Testing Baud Rates ===")

        for baud in baud_rates:
            self.logger.info(f"\nTrying baud rate: {baud}")
            try:
                temp_communicator = GaugeCommunicator(
                    port=port,
                    gauge_type=self.gauge_type,
                    logger=self.logger
                )
                temp_communicator.baudrate = baud

                if temp_communicator.connect():
                    if self.test_connection():
                        self.logger.info(f"Successfully connected at {baud} baud!")
                        temp_communicator.disconnect()
                        return True
                    else:
                        self.logger.debug(f"Connection test failed at {baud} baud")
                if temp_communicator.ser and temp_communicator.ser.is_open:
                    temp_communicator.disconnect()

            except Exception as e:
                self.logger.error(f"Failed at {baud} baud: {str(e)}")

            time.sleep(0.5)

        self.logger.info("\nFailed to connect at any baud rate")
        return False

    def send_enq(self) -> bool:
        """
        Send an ENQ character and read the response to verify connectivity.
        """
        if not self.communicator.ser or not self.communicator.ser.is_open:
            self.logger.error("Not connected")
            return False

        try:
            self.communicator.ser.reset_input_buffer()
            self.communicator.ser.reset_output_buffer()

            self.logger.debug("> Sending ENQ (0x05)")

            result = IntelligentCommandSender.send_manual_command(
                self.communicator,
                "05",  # ENQ in hex
                self.communicator.output_format
            )

            if result["success"] and "response_formatted" in result:
                self.logger.debug(f"< ENQ Response: {result['response_formatted']}")
                return True
            else:
                self.logger.debug("< No response to ENQ")
                return False

        except Exception as e:
            self.logger.error(f"ENQ test error: {str(e)}")
            return False

    def get_supported_test_commands(self) -> dict:
        """Return dictionary of supported test commands for the current gauge."""
        return self.test_commands

    def run_all_tests(self) -> dict:
        """
        Run all available tests:
         - Basic connection test
         - ENQ test
         - Command-specific tests
        Returns a dictionary summarizing the results.
        """
        results = {
            "connection": False,
            "enq": False,
            "commands_tested": {}
        }

        if not self.communicator.ser or not self.communicator.ser.is_open:
            return results

        # Mark the basic connection as valid
        results["connection"] = True
        # Try ENQ
        results["enq"] = self.send_enq()

        # Test each command
        for cmd_name, cmd_info in self.test_commands.items():
            try:
                if self.gauge_type in ["PCG550", "PSG550", "MAG500", "MPG500"]:
                    command = GaugeCommand(
                        name=cmd_name,
                        command_type="?",
                        parameters={"pid": cmd_info["pid"], "cmd": cmd_info["cmd"]}
                    )
                elif self.gauge_type == "PPG550":
                    command = GaugeCommand(name=cmd_info["cmd"], command_type="?")
                else:  # e.g., CDG045D
                    command = GaugeCommand(name=cmd_info["name"], command_type=cmd_info["cmd"])

                cmd_bytes = self.protocol.create_command(command)
                result = IntelligentCommandSender.send_manual_command(
                    self.communicator,
                    cmd_bytes.hex(' '),
                    self.communicator.output_format
                )

                results["commands_tested"][cmd_name] = {
                    "success": result['success'],
                    "response": result.get('response_formatted', '')
                }

            except Exception as e:
                results["commands_tested"][cmd_name] = {
                    "success": False,
                    "error": str(e)
                }

        return results

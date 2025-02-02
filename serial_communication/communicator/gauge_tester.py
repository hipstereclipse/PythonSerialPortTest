"""
gauge_tester.py

Provides the GaugeTester class for testing gauge connectivity,
baud rates, and ENQ commands.
"""

import time
from typing import Optional

from serial_communication.models import GaugeCommand, GaugeResponse
from serial_communication.config import GAUGE_PARAMETERS
from serial_communication.communicator.gauge_communicator import GaugeCommunicator
from serial_communication.communicator.intelligent_command_sender import IntelligentCommandSender


class GaugeTester:
    """
    Tests gauge communication by attempting different commands and baud rates.
    """

    def __init__(self, communicator: GaugeCommunicator, logger):
        """
        Initializes the tester.

        Args:
            communicator: An instance of GaugeCommunicator.
            logger: A logger instance.
        """
        self.communicator = communicator
        self.logger = logger
        self.gauge_type = communicator.gauge_type
        self.params = GAUGE_PARAMETERS[self.gauge_type]
        self.protocol = communicator.protocol
        self.test_commands = self._get_test_commands()

    def _get_test_commands(self) -> dict:
        """
        Returns a dictionary of basic test commands to try on the connected gauge.

        Returns:
            A dictionary mapping command names to their definitions.
        """
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
        return commands

    def test_connection(self) -> bool:
        """
        Performs a basic connection test by sending test commands.

        Returns:
            True if a valid response is received, otherwise False.
        """
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
        Cycles through candidate baud rates to find one that works.

        Args:
            port: The serial port to test.

        Returns:
            True if a baud rate is found that passes the connection test, False otherwise.
        """
        from serial_communication.config import BAUD_RATES

        baud_rates = [
            self.params.get("baudrate", 9600),
            57600, 38400, 19200, 9600
        ]
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
        Sends an ENQ (0x05) command to verify if the gauge responds.

        Returns:
            True if a valid response is received, False otherwise.
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
        """
        Returns the dictionary of test commands for the current gauge.

        Returns:
            A dictionary of test commands.
        """
        return self.test_commands

    def run_all_tests(self) -> dict:
        """
        Runs a suite of tests (connection, ENQ, command tests) and returns the results.

        Returns:
            A dictionary summarizing the test outcomes.
        """
        results = {
            "connection": False,
            "enq": False,
            "commands_tested": {}
        }
        if not self.communicator.ser or not self.communicator.ser.is_open:
            return results
        results["connection"] = True
        results["enq"] = self.send_enq()
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
                else:
                    command = GaugeCommand(name=cmd_info.get("name", cmd_name), command_type=cmd_info["cmd"])
                cmd_bytes = self.communicator.protocol.create_command(command)
                result_cmd = IntelligentCommandSender.send_manual_command(
                    self.communicator,
                    cmd_bytes.hex(' '),
                    self.communicator.output_format
                )
                results["commands_tested"][cmd_name] = {
                    "success": result_cmd['success'],
                    "response": result_cmd.get('response_formatted', 'OK')
                }
            except Exception as e:
                results["commands_tested"][cmd_name] = {
                    "success": False,
                    "error": str(e)
                }
        return results

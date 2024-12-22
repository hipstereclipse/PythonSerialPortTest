"""
gauge_tester.py
Provides the GaugeTester class for testing gauge connections, baud rates, and ENQ commands.
This class helps systematically validate communication with a gauge.
"""

import time            # Imports time for sleeps between attempts
from typing import Optional

from ..models import GaugeCommand, GaugeResponse    # Imports standardized data models
from ..config import GAUGE_PARAMETERS              # Imports gauge parameters from config
from .gauge_communicator import GaugeCommunicator  # Imports the main communicator class
from .intelligent_command_sender import IntelligentCommandSender


class GaugeTester:
    """
    Handles gauge testing functionality:
     - Attempting different baud rates
     - Running quick tests to verify connectivity
     - Sending ENQ (enquiry) to see if gauge responds
    """

    def __init__(self, communicator: GaugeCommunicator, logger):
        """
        Initializes the tester with a given communicator and logger.
         - communicator: A GaugeCommunicator instance already created
         - logger: A logging interface for messages
        """
        self.communicator = communicator
        self.logger = logger
        self.gauge_type = communicator.gauge_type
        # Looks up parameters for the chosen gauge
        self.params = GAUGE_PARAMETERS[self.gauge_type]
        # Protocol reference to send/parse commands
        self.protocol = communicator.protocol
        # Prepares a dictionary of short commands for testing
        self.test_commands = self._get_test_commands()

    def _get_test_commands(self) -> dict:
        """
        Returns a dictionary of minimal commands to try on the connected gauge.
        This can vary by gauge type.
        """
        commands = {}
        # A handful of Pfeiffer gauges share some common PIDs for product_name, software_version, etc.
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
        # Additional commands can be appended as needed
        return commands

    def test_connection(self) -> bool:
        """
        Performs a basic connection test by sending the gauge protocol's 'test commands'.
        If the gauge responds properly, returns True.
        """
        if not self.communicator.ser or not self.communicator.ser.is_open:
            # Logs if we are not connected at all
            return False

        try:
            # Grabs the protocol’s test commands
            for cmd_bytes in self.communicator.protocol.test_commands():
                # Translates the command to a readable format
                formatted_cmd = self.communicator.format_response(cmd_bytes)
                # Logs it for debug
                self.logger.debug(f"Testing connection with command: {formatted_cmd}")

                # Uses IntelligentCommandSender to send the bytes
                result = IntelligentCommandSender.send_manual_command(
                    self.communicator,
                    cmd_bytes.hex(' '),
                    self.communicator.output_format
                )

                if result["success"]:
                    # If we have a formatted response, logs it
                    if "response_formatted" in result:
                        self.logger.debug(f"Test response: {result['response_formatted']}")
                        return True
                    else:
                        # If no formatted data was returned, logs a note
                        self.logger.debug("Test response missing formatted data")
                else:
                    self.logger.debug(f"Test command failed: {result.get('error', 'Unknown error')}")
            return False

        except Exception as e:
            self.logger.error(f"Connection test failed: {str(e)}")
            return False

    def try_all_baud_rates(self, port: str) -> bool:
        """
        Cycles through a list of candidate baud rates, trying to connect at each.
        Returns True if any baud rate yields a successful connection test.
        """
        from ..config import BAUD_RATES  # Imports a global list of common baud rates

        # Builds a short list of baud rates to attempt, starting with the gauge’s default
        baud_rates = [
            self.params.get("baudrate", 9600),
            57600, 38400, 19200, 9600
        ]
        # Removes duplicates while preserving order by converting to dict then back to list
        baud_rates = list(dict.fromkeys(baud_rates))

        self.logger.info("\n=== Testing Baud Rates ===")

        # Tries each baud in sequence
        for baud in baud_rates:
            self.logger.info(f"\nTrying baud rate: {baud}")
            try:
                # Creates a temporary communicator for each attempt
                temp_communicator = GaugeCommunicator(
                    port=port,
                    gauge_type=self.gauge_type,
                    logger=self.logger
                )
                temp_communicator.baudrate = baud

                # Connects and runs a quick connection test
                if temp_communicator.connect():
                    # If connected, calls test_connection
                    if self.test_connection():
                        self.logger.info(f"Successfully connected at {baud} baud!")
                        temp_communicator.disconnect()
                        return True
                    else:
                        self.logger.debug(f"Connection test failed at {baud} baud")
                # Closes the port if open
                if temp_communicator.ser and temp_communicator.ser.is_open:
                    temp_communicator.disconnect()

            except Exception as e:
                self.logger.error(f"Failed at {baud} baud: {str(e)}")

            # Waits a brief moment before next attempt
            time.sleep(0.5)

        self.logger.info("\nFailed to connect at any baud rate")
        return False

    def send_enq(self) -> bool:
        """
        Sends an ENQ (ASCII 0x05) to see if the gauge acknowledges.
        Some gauges respond with an ACK, some with version info, or might do nothing.
        Returns True if a positive response is received, else False.
        """
        if not self.communicator.ser or not self.communicator.ser.is_open:
            self.logger.error("Not connected")
            return False

        try:
            # Clears buffers to ensure a fresh read
            self.communicator.ser.reset_input_buffer()
            self.communicator.ser.reset_output_buffer()

            self.logger.debug("> Sending ENQ (0x05)")

            # Sends manual command with "05" as hex
            result = IntelligentCommandSender.send_manual_command(
                self.communicator,
                "05",  # This is 'ENQ' in hex
                self.communicator.output_format
            )

            # If successful and we have a response, logs it
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
        Returns the internal dictionary of test commands for the current gauge.
        The user can iterate over these to manually verify certain commands.
        """
        return self.test_commands

    def run_all_tests(self) -> dict:
        """
        Runs a suite of tests:
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

        # If not connected, no tests can run
        if not self.communicator.ser or not self.communicator.ser.is_open:
            return results

        # If we are here, we consider the basic connection valid
        results["connection"] = True

        # Attempts an ENQ test
        results["enq"] = self.send_enq()

        # For each known test command, attempts a read
        for cmd_name, cmd_info in self.test_commands.items():
            try:
                # Constructs a GaugeCommand differently for ASCII or binary protocols
                if self.gauge_type in ["PCG550", "PSG550", "MAG500", "MPG500"]:
                    command = GaugeCommand(
                        name=cmd_name,
                        command_type="?",
                        parameters={"pid": cmd_info["pid"], "cmd": cmd_info["cmd"]}
                    )
                elif self.gauge_type == "PPG550":
                    command = GaugeCommand(name=cmd_info["cmd"], command_type="?")
                else:
                    # e.g., CDG045D or others
                    command = GaugeCommand(name=cmd_info.get("name", cmd_name), command_type=cmd_info["cmd"])

                # Creates raw command bytes via the protocol
                cmd_bytes = self.protocol.create_command(command)
                # Sends them using IntelligentCommandSender
                result = IntelligentCommandSender.send_manual_command(
                    self.communicator,
                    cmd_bytes.hex(' '),
                    self.communicator.output_format
                )

                # Stashes the success or error in the results dict
                results["commands_tested"][cmd_name] = {
                    "success": result['success'],
                    "response": result.get('response_formatted', '')
                }

            except Exception as e:
                # If something fails, logs and records an error
                results["commands_tested"][cmd_name] = {
                    "success": False,
                    "error": str(e)
                }

        return results

"""
ppg_protocol.py
Implements the protocol logic for PPG550/PPG570 MEMS Pirani & Piezo gauges.
These typically use ASCII-based commands that start with '@XXX' and end with a backslash.
"""

from typing import Optional, List

# Imports the base abstract class
from serial_communication.gauges.protocols.gauge_protocol import GaugeProtocol
from serial_communication.models import GaugeCommand, GaugeResponse


class PPGProtocol(GaugeProtocol):
    """
    Manages ASCII-based commands for PPG550/PPG570.
    Addresses can range if using RS485; if RS232, address=254 is common.
    """

    def __init__(self, address: int = 254, gauge_type: str = "PPG550", logger: Optional[object] = None):
        """
        Stores the gauge_type (e.g., "PPG550" or "PPG570").
        Also indicates if the gauge has an atmospheric sensor (PPG570 does).
        """
        self.gauge_type = gauge_type
        # Some PPG variants can read atmospheric pressure, so we note if has_atm is True
        self.has_atm = (gauge_type == "PPG570")
        super().__init__(address, logger)
        self.logger.debug(f"Initialized {self.gauge_type} protocol handler with ATM sensor: {self.has_atm}")

    def _initialize_commands(self):
        """
        Defines standard commands for PPG:
         - 'PR3' => read combined pressure
         - 'FV' => firmware version
         - etc.
        """
        self._command_defs = {
            "pressure": {
                "cmd": "PR3",
                "type": "read",
                "desc": "Read combined pressure measurement"
            },
            "temperature": {
                "cmd": "T",
                "type": "read",
                "desc": "Read temperature"
            },
            "software_version": {
                "cmd": "FV",
                "type": "read",
                "desc": "Read firmware version"
            },
            "serial_number": {
                "cmd": "SN",
                "type": "read",
                "desc": "Read serial number"
            },
            "unit": {
                "cmd": "U",
                "type": "read/write",
                "desc": "Get/set pressure unit"
            },
            "zero_adjust": {
                "cmd": "VAC",
                "type": "write",
                "desc": "Perform Pirani zero adjustment"
            },
            "piezo_adjust": {
                "cmd": "FS",
                "type": "write",
                "desc": "Perform Piezo full scale adjustment"
            }
        }

        # If it's PPG570, we add ATM commands
        if self.has_atm:
            self._command_defs.update({
                "atm_pressure": {
                    "cmd": "PR4",
                    "type": "read",
                    "desc": "Read atmospheric pressure"
                },
                "differential_pressure": {
                    "cmd": "PR5",
                    "type": "read",
                    "desc": "Read differential pressure"
                },
                "atm_zero": {
                    "cmd": "ATZ",
                    "type": "write",
                    "desc": "Perform atmospheric sensor zero adjustment"
                },
                "atm_adjust": {
                    "cmd": "ATD",
                    "type": "write",
                    "desc": "Perform atmospheric sensor adjustment"
                }
            })

    def create_command(self, command: GaugeCommand) -> bytes:
        """
        Builds an ASCII command string, e.g. "@254PR3?\"
        or "@254U!mbar\" if user sets units.
        """
        cmd_info = self._command_defs.get(command.name)
        if not cmd_info:
            raise ValueError(f"Unknown command: {command.name}")

        # If RS485, we format the address as e.g. 003 => 3
        addr = f"{self.address:03d}" if self.rs485_mode else "254"
        # Command type: '?' for read, '!' for write
        cmd_type = "!" if command.command_type in ["!", "write"] else "?"
        # Builds the base string
        cmd_str = f"@{addr}{cmd_info['cmd']}{cmd_type}"

        # If user set a parameter, e.g. "@254U!mbar\"
        if cmd_type == "!" and command.parameters:
            value = command.parameters.get('value')
            if value is not None:
                cmd_str += str(value)

        # Ends with a backslash
        cmd_str += "\\"
        self.logger.debug(f"Created PPG command: {cmd_str}")
        return cmd_str.encode('ascii')

    def parse_response(self, response: bytes) -> GaugeResponse:
        """
        Decodes ASCII, looks for @ACK or @NAK, returns a structured GaugeResponse.
        """
        try:
            if not response:
                return GaugeResponse(
                    raw_data=b"",
                    formatted_data="",
                    success=False,
                    error_message="No response received"
                )

            resp_str = response.decode('ascii', errors='replace').strip()
            self.logger.debug(f"Parsing response: {resp_str}")

            if resp_str.startswith("@NAK"):
                error_msg = resp_str[4:] if len(resp_str) > 4 else "Unknown error"
                return GaugeResponse(
                    raw_data=response,
                    formatted_data=error_msg,
                    success=False,
                    error_message=error_msg
                )

            if resp_str.startswith("@ACK"):
                data = resp_str[4:].strip()
                return GaugeResponse(
                    raw_data=response,
                    formatted_data=data,
                    success=True
                )

            return GaugeResponse(
                raw_data=response,
                formatted_data=resp_str,
                success=False,
                error_message="Invalid response format"
            )

        except Exception as e:
            self.logger.error(f"Response parse error: {str(e)}")
            return GaugeResponse(
                raw_data=response if response else b"",
                formatted_data="",
                success=False,
                error_message=f"Parse error: {str(e)}"
            )

    def test_commands(self) -> List[bytes]:
        """
        Provides a small set of ASCII commands that test basic functionality:
         - Query software version
         - Query pressure
         - If PPG570, query ATM pressure as well
        """
        commands = [
            self.create_command(GaugeCommand(name="software_version", command_type="?")),
            self.create_command(GaugeCommand(name="pressure", command_type="?"))
        ]
        if self.has_atm:
            commands.append(self.create_command(GaugeCommand(name="atm_pressure", command_type="?")))
        return commands

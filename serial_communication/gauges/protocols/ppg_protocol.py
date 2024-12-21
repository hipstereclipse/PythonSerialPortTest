"""
Implements the protocol logic for PPG550 and PPG570 MEMS Pirani & Piezo gauges.
"""

from typing import Optional, List

from serial_communication.gauges.protocols.gauge_protocol import GaugeProtocol
from serial_communication.models import GaugeCommand, GaugeResponse


class PPGProtocol(GaugeProtocol):
    """
    Manages ASCII-based commands for PPG550/PPG570 gauges.
    """

    def __init__(self, address: int = 254, gauge_type: str = "PPG550", logger: Optional[object] = None):
        self.gauge_type = gauge_type
        self.has_atm = (gauge_type == "PPG570")
        super().__init__(address, logger)
        self.logger.debug(f"Initialized {self.gauge_type} protocol handler with ATM sensor: {self.has_atm}")

    def _initialize_commands(self):
        """
        Adds user interface button for commands that are common to both PPG550 and PPG570.
        Also adds additional commands if this is a PPG570.
        """
        self._command_defs = {
            "pressure": {
                "cmd": "PR3",
                "type": "read",
                "desc": "Read combined pressure measurement"
            },
            "pirani_pressure": {
                "cmd": "PR1",
                "type": "read",
                "desc": "Read Pirani pressure"
            },
            "piezo_pressure": {
                "cmd": "PR2",
                "type": "read",
                "desc": "Read Piezo pressure"
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
            },
        }

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
        Builds ASCII command string for PPG gauges based on the command definitions.
        """
        cmd_info = self._command_defs.get(command.name)
        if not cmd_info:
            raise ValueError(f"Unknown command: {command.name}")

        addr = f"{self.address:03d}" if self.rs485_mode else "254"
        cmd_type = "!" if command.command_type in ["!", "write"] else "?"
        cmd_str = f"@{addr}{cmd_info['cmd']}{cmd_type}"

        if cmd_type == "!" and command.parameters:
            value = command.parameters.get('value')
            if value is not None:
                cmd_str += str(value)

        cmd_str += "\\"
        self.logger.debug(f"Created PPG command: {cmd_str}")
        return cmd_str.encode('ascii')

    def parse_response(self, response: bytes) -> GaugeResponse:
        """
        Decodes ASCII response, checks for ACK/NAK, and returns a structured GaugeResponse.
        """
        try:
            if not response:
                return GaugeResponse(
                    raw_data=b"",
                    formatted_data="",
                    success=False,
                    error_message="No response received"
                )

            resp_str = response.decode('ascii').strip()
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
        Returns a small set of test commands that query firmware version and pressure.
        """
        commands = [
            self.create_command(GaugeCommand(name="software_version", command_type="?")),
            self.create_command(GaugeCommand(name="pressure", command_type="?"))
        ]
        if self.has_atm:
            commands.append(self.create_command(GaugeCommand(name="atm_pressure", command_type="?")))
        return commands

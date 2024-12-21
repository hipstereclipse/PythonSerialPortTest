"""
intelligent_command_sender.py
Contains the IntelligentCommandSender class for parsing and converting manual commands.
"""

import time
from typing import Dict, Any
from ..config import OUTPUT_FORMATS  # Adjust import as needed


class IntelligentCommandSender:
    """
    Handles detection of user input format (hex, decimal, binary, etc.) and
    sends a manual command through the communicator's serial interface.
    """

    @staticmethod
    def detect_format(input_string: str) -> tuple[str, str]:
        """
        Detect the format of the input string and normalize it.
        Returns: (format_type, normalized_string)
        """
        input_string = input_string.strip()

        # Binary format (e.g. "1010 0011")
        if all(c in '01 ' for c in input_string):
            return "binary", input_string.replace(" ", "")

        # Hex with '0x'
        if input_string.lower().startswith('0x') or ' 0x' in input_string.lower():
            return "hex_prefixed", input_string.lower().replace("0x", "").replace(" ", "")

        # Hex with '\x'
        if input_string.startswith('\\x') or '\\x' in input_string:
            return "hex_escaped", input_string.replace("\\x", "").replace(" ", "")

        # Space-separated decimal (e.g. "3 0 2")
        if all(part.isdigit() for part in input_string.split()):
            return "decimal", input_string

        # Comma-separated decimal (e.g. "3,0,2")
        if ',' in input_string and all(part.strip().isdigit() for part in input_string.split(',')):
            return "decimal_csv", input_string

        # Standard hex (e.g. "03 00 02")
        if all(c in '0123456789ABCDEFabcdef ' for c in input_string):
            return "hex", input_string.replace(" ", "")

        # If not any of the above, treat as ASCII
        return "ascii", input_string

    @staticmethod
    def convert_to_bytes(format_type: str, input_string: str) -> bytes:
        """
        Convert the normalized string to bytes based on the detected format.
        """
        try:
            if format_type == "binary":
                while len(input_string) % 8 != 0:
                    input_string += '0'
                return bytes(int(input_string[i:i + 8], 2) for i in range(0, len(input_string), 8))

            elif format_type in ["hex", "hex_prefixed", "hex_escaped"]:
                return bytes.fromhex(input_string)

            elif format_type in ["decimal", "decimal_csv"]:
                if ',' in input_string:
                    numbers = [int(x.strip()) for x in input_string.split(',')]
                else:
                    numbers = [int(x) for x in input_string.split()]
                return bytes(numbers)

            elif format_type == "ascii":
                return input_string.encode('ascii')

            else:
                raise ValueError(f"Unsupported format: {format_type}")

        except Exception as e:
            raise ValueError(f"Conversion error: {str(e)}")

    @staticmethod
    def format_output_suggestion(raw_response: bytes) -> str:
        """
        Suggest the best output format based on the response content.
        """
        if not raw_response:
            return "Hex"  # Default if no response

        try:
            decoded = raw_response.decode('ascii')
            if all(32 <= ord(c) <= 126 or c in '\r\n' for c in decoded):
                return "ASCII"
        except:
            pass

        if any(b > 127 for b in raw_response):
            return "Hex"

        if all(b < 100 for b in raw_response):
            return "Decimal"

        return "Hex"

    @staticmethod
    def send_manual_command(communicator, input_string: str, force_format: str = None) -> dict:
        """
        Send manual command and format according to the specified or suggested format.
        """
        try:
            input_format, normalized = IntelligentCommandSender.detect_format(input_string)
            command_bytes = IntelligentCommandSender.convert_to_bytes(input_format, normalized)

            result = {
                "input_format_detected": input_format,
                "success": False,
                "error": None,
                "response_formatted": None,
                "response_raw": None,
                "rs_mode": communicator.rs_mode
            }

            if communicator.ser and communicator.ser.is_open:
                communicator.ser.reset_input_buffer()
                communicator.ser.reset_output_buffer()

                # Handle RS485 mode
                if communicator.rs_mode == "RS485":
                    if hasattr(communicator.ser, 'rs485_mode'):
                        communicator.ser.rs485_mode = communicator.rs485_config
                    communicator.ser.setRTS(communicator.rts_level_for_tx)
                    time.sleep(communicator.rts_delay_before_tx)

                communicator.ser.write(command_bytes)
                communicator.ser.flush()

                if communicator.rs_mode == "RS485":
                    communicator.ser.setRTS(communicator.rts_level_for_rx)
                    time.sleep(communicator.rts_delay_before_rx)

                time.sleep(communicator.rts_delay)
                response = communicator.read_response()

                if response:
                    suggested_format = force_format or communicator.output_format
                    communicator.set_output_format(suggested_format)

                    result.update({
                        "success": True,
                        "response_raw": response.hex(),
                        "response_formatted": communicator.format_response(response)
                    })
                else:
                    result["error"] = "No response received"
            else:
                result["error"] = "Port not open"

            return result

        except Exception as e:
            communicator.logger.error(f"Manual command failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "response_formatted": None,
                "response_raw": None
            }

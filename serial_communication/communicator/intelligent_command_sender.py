"""
intelligent_command_sender.py
Contains the IntelligentCommandSender class for parsing user-supplied strings
and sending them as manual commands in the correct format (hex, decimal, ascii, etc.).
"""

import time             # Used for small delays if needed
from typing import Dict, Any

# Imports a global list of potential output formats if needed
from ..config import OUTPUT_FORMATS


class IntelligentCommandSender:
    """
    Handles detection of a user’s input string format (hex, decimal, binary, etc.)
    and automatically converts it into bytes to write on the serial port.
    """

    @staticmethod
    def detect_format(input_string: str) -> tuple[str, str]:
        """
        Determines the format of the user input command (binary, hex, decimal, ascii).
        Returns a tuple: (format_type, normalized_string).
        """
        # Strips whitespace
        input_string = input_string.strip()

        # Checks if it might be binary (only '0' or '1' with optional spaces)
        if all(c in '01 ' for c in input_string):
            return "binary", input_string.replace(" ", "")

        # Checks for '0x' hex prefix
        if input_string.lower().startswith('0x') or ' 0x' in input_string.lower():
            return "hex_prefixed", input_string.lower().replace("0x", "").replace(" ", "")

        # Checks for '\x' style escaped hex
        if '\\x' in input_string:
            return "hex_escaped", input_string.replace("\\x", "").replace(" ", "")

        # Checks for space-separated decimals
        if all(part.isdigit() for part in input_string.split()):
            return "decimal", input_string

        # Checks for comma-separated decimals
        if ',' in input_string and all(part.strip().isdigit() for part in input_string.split(',')):
            return "decimal_csv", input_string

        # If all else fails, tries to interpret as plain hex (no prefix) if it’s valid
        if all(c in '0123456789ABCDEFabcdef ' for c in input_string):
            return "hex", input_string.replace(" ", "")

        # Otherwise, treat as ASCII
        return "ascii", input_string

    @staticmethod
    def convert_to_bytes(format_type: str, input_string: str) -> bytes:
        """
        Converts the normalized string to actual bytes based on the detected format.
        """
        try:
            if format_type == "binary":
                # Ensures we have multiples of 8
                while len(input_string) % 8 != 0:
                    input_string += '0'
                # Groups bits into bytes
                return bytes(int(input_string[i:i + 8], 2) for i in range(0, len(input_string), 8))

            elif format_type in ["hex", "hex_prefixed", "hex_escaped"]:
                # Interprets the string as hex
                return bytes.fromhex(input_string)

            elif format_type in ["decimal", "decimal_csv"]:
                # Splits on commas or spaces
                if ',' in input_string:
                    numbers = [int(x.strip()) for x in input_string.split(',')]
                else:
                    numbers = [int(x) for x in input_string.split()]
                # Packs them as bytes
                return bytes(numbers)

            elif format_type == "ascii":
                # Directly encodes as ASCII
                return input_string.encode('ascii')

            else:
                raise ValueError(f"Unsupported format: {format_type}")

        except Exception as e:
            # If conversion fails, raises a ValueError
            raise ValueError(f"Conversion error: {str(e)}")

    @staticmethod
    def format_output_suggestion(raw_response: bytes) -> str:
        """
        Suggests the best output format based on what the response looks like.
        For example, if the bytes decode cleanly as ASCII, it suggests "ASCII".
        """
        if not raw_response:
            return "Hex"  # Default if empty

        try:
            decoded = raw_response.decode('ascii')
            # Checks if all chars are printable ASCII
            if all(32 <= ord(c) <= 126 or c in '\r\n' for c in decoded):
                return "ASCII"
        except:
            pass

        # If we have non-ascii or high-bit bytes, suggests Hex
        if any(b > 127 for b in raw_response):
            return "Hex"

        # If all bytes are small, decimal might be okay
        if all(b < 100 for b in raw_response):
            return "Decimal"

        return "Hex"

    @staticmethod
    def send_manual_command(communicator, input_string: str, force_format: str = None) -> dict:
        """
        Interprets the user command string (detecting format automatically),
        sends it via the communicator’s serial port, and returns the raw response + formatted response.

        Args:
         - communicator: The GaugeCommunicator instance
         - input_string: The user-typed command (e.g. "05", "0x0300", or "Hello")
         - force_format: If provided, forces the output format to a specific choice
        Returns:
         - A dictionary with success/error, raw/hex response, and possibly formatted text
        """
        try:
            # Detects the format
            input_format, normalized = IntelligentCommandSender.detect_format(input_string)
            # Converts to bytes
            command_bytes = IntelligentCommandSender.convert_to_bytes(input_format, normalized)

            result = {
                "input_format_detected": input_format,
                "success": False,
                "error": None,
                "response_formatted": None,
                "response_raw": None,
                "rs_mode": communicator.rs_mode
            }

            # Checks if port is open
            if communicator.ser and communicator.ser.is_open:
                # Clears input/output buffers
                communicator.ser.reset_input_buffer()
                communicator.ser.reset_output_buffer()

                # If we are in RS485, set RTS accordingly
                if communicator.rs_mode == "RS485":
                    if hasattr(communicator.ser, 'rs485_mode'):
                        communicator.ser.rs485_mode = communicator.rs485_config
                    communicator.ser.setRTS(communicator.rts_level_for_tx)
                    time.sleep(communicator.rts_delay_before_tx)

                # Writes the command
                communicator.ser.write(command_bytes)
                communicator.ser.flush()

                # Switches to RX mode quickly if RS485
                if communicator.rs_mode == "RS485":
                    communicator.ser.setRTS(communicator.rts_level_for_rx)
                    time.sleep(communicator.rts_delay_before_rx)

                # Optional small delay
                time.sleep(communicator.rts_delay)
                # Reads the response
                response = communicator.read_response()

                if response:
                    # Chooses a final format to display (either forced or communicator’s format)
                    suggested_format = force_format or communicator.output_format
                    communicator.set_output_format(suggested_format)

                    # Fills in the result dictionary
                    result.update({
                        "success": True,
                        "response_raw": response.hex(),
                        "response_formatted": communicator.format_response(response)
                    })
                else:
                    # If no data came back
                    result["error"] = "No response received"
            else:
                # If port not open
                result["error"] = "Port not open"

            return result

        except Exception as e:
            # Logs error details in communicator
            communicator.logger.error(f"Manual command failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "response_formatted": None,
                "response_raw": None
            }

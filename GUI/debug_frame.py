"""
DebugFrame: Provides debugging tools and test functionality for gauge communication.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable


class DebugFrame(ttk.LabelFrame):
    """
    Frame for debugging options and testing gauge communication.
    Uses the same output format as the main interface for consistency.
    """

    def __init__(
        self,
        parent,
        baud_callback: Callable,
        enq_callback: Callable,
        settings_callback: Callable,
        output_format: tk.StringVar
    ):
        """
        Initializes the DebugFrame.
        parent: The parent widget or window.
        baud_callback: A function that tries all baud rates.
        enq_callback: A function that sends an ENQ character.
        settings_callback: A function that shows port settings.
        output_format: A StringVar indicating the current output format.
        """
        super().__init__(parent, text="Debug")
        self.output_format = output_format
        self.parent = parent  # Reference to the main application

        # Creates a small sub-frame to hold the debug buttons
        controls_frame = ttk.Frame(self)
        controls_frame.pack(fill=tk.X, padx=5, pady=5)

        # Button to try all baud rates
        self.baud_button = ttk.Button(
            controls_frame,
            text="Try All Baud Rates",
            command=lambda: self._wrap_debug_callback(baud_callback)
        )
        self.baud_button.pack(side=tk.LEFT, padx=5)

        # Button to send an ENQ
        self.enq_button = ttk.Button(
            controls_frame,
            text="Send ENQ",
            command=lambda: self._wrap_debug_callback(enq_callback)
        )
        self.enq_button.pack(side=tk.LEFT, padx=5)

        # Button to show port settings
        self.settings_button = ttk.Button(
            controls_frame,
            text="Show Settings",
            command=settings_callback
        )
        self.settings_button.pack(side=tk.LEFT, padx=5)

        # A list of buttons that should remain active even if disconnected
        self.non_connection_buttons = [self.settings_button]

    def _wrap_debug_callback(self, callback: Callable):
        """
        Calls the provided debug function and then processes the output
        in the output frame to ensure it matches the current output format.
        """
        try:
            # Runs the actual callback
            result = callback()
            # If the parent has an output_frame, we re-format the entire log
            if hasattr(self.parent, 'output_frame'):
                debug_text = self.parent.output_frame.output_text.get("1.0", tk.END)
                formatted = self._format_debug_messages(debug_text)
                # If the text changed, refresh the entire log
                if formatted != debug_text:
                    self.parent.output_frame.clear()
                    self.parent.output_frame.append_log(formatted)
            return result
        except Exception as e:
            # Logs an error if callback fails
            if hasattr(self.parent, 'output_frame'):
                self.parent.output_frame.append_log(f"Debug error: {str(e)}")
            return None

    def _format_debug_messages(self, text: str) -> str:
        """
        Iterates over each line of the debug log,
        and re-formats lines that look like protocol messages.
        """
        lines = []
        for line in text.split('\n'):
            if "command:" in line.lower() or "response:" in line.lower():
                formatted = self._format_protocol_message(line)
                lines.append(formatted)
            else:
                lines.append(line)
        return '\n'.join(lines)

    def _format_protocol_message(self, message: str) -> str:
        """
        Converts message byte strings into the selected output format (Hex, ASCII, etc.).
        """
        try:
            prefix, data = message.split(':', 1)
            data = data.strip()

            # Attempts to interpret data as bytes
            if data.startswith("b'") or data.startswith('b\"'):
                data_bytes = eval(data)  # risky, but for demonstration
            elif all(c in '0123456789ABCDEFabcdef ' for c in data):
                data_bytes = bytes.fromhex(data.replace(' ', ''))
            else:
                return message

            current_format = self.output_format.get()
            if current_format == "Hex":
                formatted_data = ' '.join(f'{b:02X}' for b in data_bytes)
            elif current_format == "ASCII":
                formatted_data = data_bytes.decode('ascii', errors='replace')
            elif current_format == "Decimal":
                formatted_data = ' '.join(str(b) for b in data_bytes)
            elif current_format == "Binary":
                formatted_data = ' '.join(f'{b:08b}' for b in data_bytes)
            elif current_format == "UTF-8":
                formatted_data = data_bytes.decode('utf-8', errors='replace')
            else:
                # By default, keep as string representation of bytes
                formatted_data = str(data_bytes)

            # Additional logic for ASCII/UTF-8 if needed
            if current_format in ["ASCII", "UTF-8"] and len(formatted_data) >= 10:
                # Example of artificially parsing ASCII data
                addr = formatted_data[0:3]
                cmd_type = "Write" if formatted_data[3:5] == "10" else "Read"
                param = formatted_data[5:8]
                data_section = formatted_data[8:] if len(formatted_data) > 8 else ""
                formatted_data = f"Addr={addr} {cmd_type} Param={param} Data={data_section}"

            return f"{prefix}: {formatted_data}"
        except Exception:
            return message

    def set_enabled(self, enabled: bool):
        """
        Enables or disables most debug buttons when connected/disconnected,
        except for some that are always allowed.
        """
        state = "normal" if enabled else "disabled"
        # For each child of this frame
        for widget in self.winfo_children():
            for child in widget.winfo_children():
                # Only disable if not in the non_connection_buttons list
                if child not in self.non_connection_buttons:
                    child.config(state=state)

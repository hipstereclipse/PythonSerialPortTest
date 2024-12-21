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

    def __init__(self, parent, baud_callback: Callable, enq_callback: Callable, settings_callback: Callable,
                 output_format: tk.StringVar):
        super().__init__(parent, text="Debug")
        self.output_format = output_format
        self.parent = parent

        controls_frame = ttk.Frame(self)
        controls_frame.pack(fill=tk.X, padx=5, pady=5)

        self.baud_button = ttk.Button(
            controls_frame,
            text="Try All Baud Rates",
            command=lambda: self._wrap_debug_callback(baud_callback)
        )
        self.baud_button.pack(side=tk.LEFT, padx=5)

        self.enq_button = ttk.Button(
            controls_frame,
            text="Send ENQ",
            command=lambda: self._wrap_debug_callback(enq_callback)
        )
        self.enq_button.pack(side=tk.LEFT, padx=5)

        self.settings_button = ttk.Button(
            controls_frame,
            text="Show Settings",
            command=settings_callback
        )
        self.settings_button.pack(side=tk.LEFT, padx=5)

        self.non_connection_buttons = [self.settings_button]

    def _wrap_debug_callback(self, callback: Callable):
        """Runs debug callbacks and updates the output frame if needed."""
        try:
            result = callback()
            if hasattr(self.parent, 'output_frame'):
                debug_text = self.parent.output_frame.output_text.get("1.0", tk.END)
                formatted = self._format_debug_messages(debug_text)
                if formatted != debug_text:
                    self.parent.output_frame.clear()
                    self.parent.output_frame.append_log(formatted)
            return result
        except Exception as e:
            if hasattr(self.parent, 'output_frame'):
                self.parent.output_frame.append_log(f"Debug error: {str(e)}")
            return None

    def _format_debug_messages(self, text: str) -> str:
        """Format protocol messages in the log according to the selected output format."""
        lines = []
        for line in text.split('\n'):
            if "command:" in line.lower() or "response:" in line.lower():
                formatted = self._format_protocol_message(line)
                lines.append(formatted)
            else:
                lines.append(line)
        return '\n'.join(lines)

    def _format_protocol_message(self, message: str) -> str:
        """Format a protocol message for debug output."""
        try:
            prefix, data = message.split(':', 1)
            data = data.strip()
            if data.startswith("b'") or data.startswith('b\"'):
                data_bytes = eval(data)
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
                formatted_data = str(data_bytes)

            # Simple ASCII/UTF-8 interpretation
            if current_format in ["ASCII", "UTF-8"] and len(formatted_data) >= 10:
                addr = formatted_data[0:3]
                cmd_type = "Write" if formatted_data[3:5] == "10" else "Read"
                param = formatted_data[5:8]
                data_section = formatted_data[8:] if len(formatted_data) > 8 else ""
                formatted_data = f"Addr={addr} {cmd_type} Param={param} Data={data_section}"

            return f"{prefix}: {formatted_data}"
        except Exception:
            return message

    def set_enabled(self, enabled: bool):
        """Enable or disable debug buttons based on connection state."""
        state = "normal" if enabled else "disabled"
        for widget in self.winfo_children():
            for child in widget.winfo_children():
                if child not in self.non_connection_buttons:
                    child.config(state=state)

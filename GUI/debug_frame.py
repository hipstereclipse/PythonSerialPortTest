"""
GUI/debug_frame.py

Provides a DebugFrame class with buttons to try all baud rates, send ENQ, show port settings,
and a checkbox to toggle debug message visibility.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable


class DebugFrame(ttk.LabelFrame):
    """
    Frame for debugging features.
    """

    def __init__(self, parent: tk.Widget, baud_callback: Callable, enq_callback: Callable,
                 settings_callback: Callable, output_format: tk.StringVar) -> None:
        """
        Initialize the DebugFrame.

        Args:
            parent: The parent Tkinter widget.
            baud_callback: Callback to attempt all baud rates.
            enq_callback: Callback to send ENQ.
            settings_callback: Callback to show port settings.
            output_format: StringVar for output format selection.
        """
        super().__init__(parent, text="Debug")
        self.output_format = output_format
        self.parent = parent

        controls_frame = ttk.Frame(self)
        controls_frame.pack(fill=tk.X, padx=5, pady=5)

        self.baud_button = ttk.Button(controls_frame, text="Try All Baud Rates",
                                        command=lambda: self._wrap_debug_callback(baud_callback))
        self.baud_button.pack(side=tk.LEFT, padx=5)

        self.enq_button = ttk.Button(controls_frame, text="Send ENQ",
                                       command=lambda: self._wrap_debug_callback(enq_callback))
        self.enq_button.pack(side=tk.LEFT, padx=5)

        self.settings_button = ttk.Button(controls_frame, text="Show Settings", command=settings_callback)
        self.settings_button.pack(side=tk.LEFT, padx=5)

        self.show_debug_var = tk.BooleanVar(value=True)
        self.debug_checkbox = ttk.Checkbutton(controls_frame, text="Show Debug",
                                                variable=self.show_debug_var,
                                                command=self._on_debug_toggle)
        self.debug_checkbox.pack(side=tk.LEFT, padx=5)

        # Controls that remain enabled regardless of connection
        self.non_connection_buttons = [self.settings_button]

    def _wrap_debug_callback(self, callback: Callable) -> None:
        """
        Wraps a debug callback to reformat output log if necessary.
        """
        try:
            result = callback()
            if hasattr(self.parent, "output_frame"):
                current_text = self.parent.output_frame.output_text.get("1.0", tk.END)
                formatted = self._format_debug_messages(current_text)
                if formatted != current_text:
                    self.parent.output_frame.clear()
                    self.parent.output_frame.append_log(formatted)
            return result
        except Exception as e:
            if hasattr(self.parent, "output_frame"):
                self.parent.output_frame.append_log(f"Debug error: {str(e)}")
            return None

    def _format_debug_messages(self, text: str) -> str:
        """
        Formats lines containing 'command:' or 'response:' according to the selected output format.
        """
        lines = []
        for line in text.splitlines():
            if "command:" in line.lower() or "response:" in line.lower():
                lines.append(self._format_protocol_message(line))
            else:
                lines.append(line)
        return "\n".join(lines)

    def _format_protocol_message(self, message: str) -> str:
        """
        Attempts to format a protocol message from raw bytes.
        """
        try:
            prefix, data = message.split(":", 1)
            data = data.strip()
            if data.startswith("b'") or data.startswith('b"'):
                data_bytes = eval(data)
            elif all(c in "0123456789ABCDEFabcdef " for c in data):
                data_bytes = bytes.fromhex(data.replace(" ", ""))
            else:
                return message

            fmt = self.output_format.get()
            if fmt == "Hex":
                formatted_data = " ".join(f"{b:02X}" for b in data_bytes)
            elif fmt == "ASCII":
                formatted_data = data_bytes.decode("ascii", errors="replace")
            elif fmt == "Decimal":
                formatted_data = " ".join(str(b) for b in data_bytes)
            elif fmt == "Binary":
                formatted_data = " ".join(f"{b:08b}" for b in data_bytes)
            elif fmt == "UTF-8":
                formatted_data = data_bytes.decode("utf-8", errors="replace")
            else:
                formatted_data = str(data_bytes)
            return f"{prefix}: {formatted_data}"
        except Exception:
            return message

    def _on_debug_toggle(self) -> None:
        """
        Invoked when the 'Show Debug' checkbox is toggled.
        Notifies the parent about the new debug visibility state.
        """
        if hasattr(self.parent, "set_show_debug"):
            self.parent.set_show_debug(self.show_debug_var.get())

    def set_enabled(self, enabled: bool) -> None:
        """
        Enables or disables the debug frame widgets (except those that remain active always).
        """
        state = "normal" if enabled else "disabled"
        for widget in self.winfo_children():
            for child in widget.winfo_children():
                if child not in self.non_connection_buttons:
                    child.config(state=state)

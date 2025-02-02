#!/usr/bin/env python3
"""
debug_frame.py

Provides debugging controls including testing baud rates, sending ENQ, showing settings,
and toggling debug output. This version also includes controls to enable Simulator Mode and
configure simulation options.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable

class DebugFrame(ttk.LabelFrame):
    """
    Debug frame with various controls for testing and debugging.
    Now includes a "Simulator Mode" toggle and "Simulation Options" button.
    """

    def __init__(self, parent, baud_callback: Callable, enq_callback: Callable,
                 settings_callback: Callable, output_format: tk.StringVar,
                 simulator_callback: Callable[[bool], None],
                 simulation_options_callback: Callable[[], None]):
        """
        Initializes the DebugFrame.

        Args:
            parent: Parent widget.
            baud_callback: Function to test baud rates.
            enq_callback: Function to send ENQ.
            settings_callback: Function to show port settings.
            output_format: StringVar for output format.
            simulator_callback: Function to enable/disable simulator mode.
            simulation_options_callback: Function to open simulation options panel.
        """
        super().__init__(parent, text="Debug")
        self.output_format = output_format
        self.parent = parent

        # Create a frame for debug controls.
        controls_frame = ttk.Frame(self)
        controls_frame.pack(fill=tk.X, padx=5, pady=5)

        # Existing debug buttons.
        self.baud_button = ttk.Button(controls_frame, text="Try All Baud Rates",
                                        command=lambda: self._wrap_debug_callback(baud_callback))
        self.baud_button.pack(side=tk.LEFT, padx=5)
        self.enq_button = ttk.Button(controls_frame, text="Send ENQ",
                                       command=lambda: self._wrap_debug_callback(enq_callback))
        self.enq_button.pack(side=tk.LEFT, padx=5)
        self.settings_button = ttk.Button(controls_frame, text="Show Settings",
                                          command=settings_callback)
        self.settings_button.pack(side=tk.LEFT, padx=5)

        # New: Simulator Mode toggle.
        self.simulator_mode = tk.BooleanVar(value=False)
        self.simulator_checkbox = ttk.Checkbutton(controls_frame, text="Simulator Mode",
                                                  variable=self.simulator_mode,
                                                  command=lambda: simulator_callback(self.simulator_mode.get()))
        self.simulator_checkbox.pack(side=tk.LEFT, padx=5)

        # New: Simulation Options button.
        self.simulation_options_button = ttk.Button(controls_frame, text="Simulation Options",
                                                    command=simulation_options_callback)
        self.simulation_options_button.pack(side=tk.LEFT, padx=5)

        # Existing debug checkbox.
        self.show_debug_var = tk.BooleanVar(value=True)
        self.debug_checkbox = ttk.Checkbutton(controls_frame, text="Show Debug",
                                               variable=self.show_debug_var,
                                               command=self._on_debug_toggle)
        self.debug_checkbox.pack(side=tk.LEFT, padx=5)

        # Some controls remain active regardless of connection state.
        self.non_connection_buttons = [self.settings_button]

    def _wrap_debug_callback(self, callback: Callable):
        """
        Calls a debug callback and reformats output if necessary.
        """
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
        """
        Formats debug messages in the output.
        """
        lines = []
        for line in text.split('\n'):
            if "command:" in line.lower() or "response:" in line.lower():
                lines.append(self._format_protocol_message(line))
            else:
                lines.append(line)
        return '\n'.join(lines)

    def _format_protocol_message(self, message: str) -> str:
        """
        Formats a protocol message.
        """
        try:
            prefix, data = message.split(':', 1)
            data = data.strip()
            fmt = self.output_format.get()
            if fmt == "Hex":
                formatted_data = ' '.join(f'{ord(c):02X}' for c in data)
            elif fmt == "ASCII":
                formatted_data = data
            elif fmt == "Decimal":
                formatted_data = ' '.join(str(ord(c)) for c in data)
            elif fmt == "Binary":
                formatted_data = ' '.join(f'{ord(c):08b}' for c in data)
            elif fmt == "UTF-8":
                formatted_data = data.encode('utf-8').decode('utf-8', errors='replace')
            else:
                formatted_data = data
            return f"{prefix}: {formatted_data}"
        except Exception:
            return message

    def _on_debug_toggle(self):
        """
        Toggles debug output.
        """
        if hasattr(self.parent, 'set_show_debug'):
            self.parent.set_show_debug(self.show_debug_var.get())

    def set_enabled(self, enabled: bool):
        """
        Enables or disables debug features based on connection state.
        """
        state = "normal" if enabled else "disabled"
        for widget in self.winfo_children():
            for child in widget.winfo_children():
                if child not in self.non_connection_buttons:
                    child.config(state=state)

"""
GUI/command_frame.py

This module defines the CommandFrame class that provides both manual and quick command interfaces
for gauge communication.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

# Import models and communication components
from serial_communication.models import GaugeCommand, GaugeResponse
from serial_communication.communicator.intelligent_command_sender import IntelligentCommandSender
from serial_communication.config import GAUGE_PARAMETERS


class CommandFrame(ttk.LabelFrame):
    """
    Frame for handling gauge commands (both manual and quick commands).
    """

    def __init__(self, parent: tk.Widget, gauge_var: tk.StringVar, command_callback: Callable) -> None:
        """
        Initialize the CommandFrame.

        Args:
            parent: The parent Tkinter widget.
            gauge_var: StringVar that holds the currently selected gauge type.
            command_callback: Function called after sending a command.
        """
        super().__init__(parent, text="Commands")
        self.gauge_var = gauge_var
        self.command_callback = command_callback
        self.communicator: Optional[object] = None  # To be set externally

        # Internal Tkinter variable objects
        self.cmd_var = tk.StringVar()
        self.cmd_type = tk.StringVar(value="?")
        self.param_var = tk.StringVar()
        self.desc_var = tk.StringVar()

        self._create_widgets()

        # Trace variable changes
        self.gauge_var.trace("w", self._update_commands)
        self.cmd_var.trace("w", self._update_command_info)
        self.cmd_type.trace("w", self._update_parameter_state)

    def _create_widgets(self) -> None:
        """
        Creates and packs all widgets for manual and quick commands.
        """
        # Manual Command Section
        manual_frame = ttk.LabelFrame(self, text="Manual Command")
        manual_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(manual_frame, text="Command:").pack(side=tk.LEFT, padx=5)
        self.manual_cmd_entry = ttk.Entry(manual_frame, width=50)
        self.manual_cmd_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        self.manual_send_button = ttk.Button(manual_frame, text="Send", command=self.send_manual_command)
        self.manual_send_button.pack(side=tk.LEFT, padx=5)

        # Quick Commands Section
        quick_frame = ttk.LabelFrame(self, text="Quick Commands")
        quick_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(quick_frame, text="Command:").pack(side=tk.LEFT, padx=5)
        self.cmd_combo = ttk.Combobox(quick_frame, textvariable=self.cmd_var, state="readonly", width=30)
        self.cmd_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        radio_frame = ttk.Frame(quick_frame)
        radio_frame.pack(side=tk.LEFT, padx=5)
        self.query_radio = ttk.Radiobutton(radio_frame, text="Query (?)", variable=self.cmd_type, value="?")
        self.set_radio = ttk.Radiobutton(radio_frame, text="Set (!)", variable=self.cmd_type, value="!")
        self.query_radio.pack(side=tk.LEFT, padx=5)
        self.set_radio.pack(side=tk.LEFT, padx=5)

        # Parameter Frame (for set commands)
        param_frame = ttk.Frame(self)
        param_frame.pack(fill=tk.X, padx=5, pady=5)
        self.param_label = ttk.Label(param_frame, text="Parameter:")
        self.param_label.pack(side=tk.LEFT, padx=5)

        self.param_entry = ttk.Entry(param_frame, textvariable=self.param_var, width=30)
        self.param_combo = ttk.Combobox(param_frame, textvariable=self.param_var, state="readonly", width=30)
        self.quick_send_button = ttk.Button(param_frame, text="Send", command=self.send_quick_command)
        self.quick_send_button.pack(side=tk.RIGHT, padx=5)

        # Description Label
        self.desc_label = ttk.Label(self, textvariable=self.desc_var, wraplength=500)
        self.desc_label.pack(fill=tk.X, padx=5, pady=5)

    def _update_commands(self, *args) -> None:
        """
        Update the quick command combobox based on the selected gauge.
        For generic gauge types (e.g. 'CDGxxxD') attempts detection if possible.
        """
        gauge_type = self.gauge_var.get()

        if self.communicator:
            if gauge_type == "CDGxxxD":
                detected = self.communicator.detect_gauge()
                if detected:
                    self.gauge_var.set(detected)
                    gauge_type = detected
                else:
                    self.desc_var.set("Error: Could not detect gauge type.")
                    self.cmd_combo["values"] = []
                    return

        params = GAUGE_PARAMETERS.get(gauge_type, {})
        commands = params.get("commands", {})
        cmd_list = [f"{name} - {info['desc']}" for name, info in commands.items()]
        self.cmd_combo["values"] = cmd_list
        if cmd_list:
            self.cmd_combo.set(cmd_list[0])
            self._update_command_info()

    def _update_command_info(self, *args) -> None:
        """
        Updates the description label with details about the currently selected command.
        Also enables/disables the set radio based on the command’s write ability.
        """
        selected = self.cmd_var.get()
        if selected and self.communicator:
            cmd_name = selected.split(" - ")[0]
            cmd_info = self.communicator.protocol._command_defs.get(cmd_name, {})
            self.desc_var.set(cmd_info.get("desc", "No description available"))
            if cmd_info.get("write", False):
                self.query_radio.configure(state="normal")
                self.set_radio.configure(state="normal")
            else:
                self.cmd_type.set("?")
                self.query_radio.configure(state="normal")
                self.set_radio.configure(state="disabled")
            self._update_parameter_state()

    def _update_parameter_state(self, *args) -> None:
        """
        Shows or hides the parameter entry/combo based on the command type.
        If set (!) is chosen and parameters are expected, the parameter widget is displayed.
        """
        if not self.communicator or not self.cmd_var.get():
            return

        cmd_name = self.cmd_var.get().split(" - ")[0]
        cmd_info = self.communicator.protocol._command_defs.get(cmd_name, {})

        self.param_entry.pack_forget()
        self.param_combo.pack_forget()

        if self.cmd_type.get() == "!":
            self.param_label.configure(state="normal")
            if "options" in cmd_info:
                options = [f"{val} - {desc}" for val, desc in zip(cmd_info["options"], cmd_info.get("option_desc", []))]
                self.param_combo["values"] = options
                if options:
                    self.param_combo.set(options[0])
                self.param_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
                self.param_combo.configure(state="readonly")
            else:
                self.param_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
                self.param_entry.configure(state="normal")
                if "min" in cmd_info and "max" in cmd_info:
                    self.desc_var.set(f"{cmd_info['desc']} (Range: {cmd_info['min']}-{cmd_info['max']} {cmd_info.get('unit','')})")
        else:
            self.param_label.configure(state="disabled")
            self.param_var.set("")

    def send_manual_command(self) -> None:
        """
        Reads the manual command from the entry, sends it through the IntelligentCommandSender,
        and clears the entry. The response is passed to the callback.
        """
        if not self.communicator:
            return
        cmd_str = self.manual_cmd_entry.get().strip()
        if cmd_str:
            result = IntelligentCommandSender.send_manual_command(self.communicator, cmd_str)
            self.manual_cmd_entry.delete(0, tk.END)
            if self.command_callback:
                response = GaugeResponse(
                    raw_data=bytes.fromhex(result.get("response_raw", "")) if result.get("response_raw") else b"",
                    formatted_data=result.get("response_formatted", ""),
                    success=result.get("success", False),
                    error_message=result.get("error")
                )
                self.command_callback(cmd_str, response=response)

    def send_quick_command(self) -> None:
        """
        Builds a GaugeCommand from the quick command selections and sends it.
        Passes the response to the callback.
        """
        if not self.communicator:
            return

        selected = self.cmd_var.get()
        if selected:
            cmd_name = selected.split(" - ")[0]
            param_value = self.param_var.get().strip()
            if " - " in param_value:
                param_value = param_value.split(" - ")[0]

            command = GaugeCommand(
                name=cmd_name,
                command_type=self.cmd_type.get(),
                parameters={"value": param_value} if self.cmd_type.get() == "!" else None
            )
            response = self.communicator.send_command(command)
            if self.command_callback:
                self.command_callback(cmd_name, response=response)

    def set_enabled(self, enabled: bool) -> None:
        """
        Enables or disables all widgets in the frame.
        Called when the connection state changes.
        """
        state = "normal" if enabled else "disabled"
        widgets = [
            self.manual_cmd_entry, self.manual_send_button, self.cmd_combo,
            self.query_radio, self.set_radio, self.param_entry, self.quick_send_button
        ]
        for widget in widgets:
            widget.configure(state=state)
        if enabled:
            self._update_command_info()

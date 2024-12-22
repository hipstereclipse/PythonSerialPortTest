"""
CommandFrame: Handles gauge commands - both quick commands and detailed command construction.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable

# Imports an intelligent command sender to handle manual strings
from serial_communication.communicator.intelligent_command_sender import IntelligentCommandSender
from serial_communication.config import GAUGE_PARAMETERS
from serial_communication.models import GaugeResponse, GaugeCommand


class CommandFrame(ttk.LabelFrame):
    """
    Frame for handling gauge commands - both quick commands and detailed command construction.
    """

    def __init__(self, parent, gauge_var: tk.StringVar, command_callback: Callable):
        """
        Initializes the CommandFrame.
        parent: The parent widget.
        gauge_var: StringVar holding the currently selected gauge type.
        command_callback: A function to be called after sending a command.
        """
        super().__init__(parent, text="Commands")

        # Stores references to external variables and methods
        self.gauge_var = gauge_var
        self.command_callback = command_callback
        # Holds the reference to the main communicator, set by main_app
        self.communicator = None

        # Internal state variables
        self.cmd_var = tk.StringVar()
        self.cmd_type = tk.StringVar(value="?")
        self.param_var = tk.StringVar()
        self.desc_var = tk.StringVar()

        # Builds the GUI elements
        self._create_widgets()

        # When gauge_var changes, update the list of available commands
        self.gauge_var.trace('w', self._update_commands)
        # When cmd_var changes, update the command’s description
        self.cmd_var.trace('w', self._update_command_info)
        # When the user switches between ? (query) and ! (set), show/hide parameter entry
        self.cmd_type.trace('w', self._update_parameter_state)

    def _create_widgets(self):
        """
        Creates the manual command controls and the quick commands controls:
         - A text field for manual command input
         - Buttons to send manual commands
         - A combobox of known commands
         - Radio buttons to switch between query (!) and read (?)
         - Parameter entry controls
        """
        # Manual Command Section
        manual_frame = ttk.LabelFrame(self, text="Manual Command")
        manual_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(manual_frame, text="Command:").pack(side=tk.LEFT, padx=5)
        self.manual_cmd_entry = ttk.Entry(manual_frame, width=50)
        self.manual_cmd_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        self.manual_send_button = ttk.Button(
            manual_frame,
            text="Send",
            command=self.send_manual_command
        )
        self.manual_send_button.pack(side=tk.LEFT, padx=5)

        # Quick Commands Section
        quick_frame = ttk.LabelFrame(self, text="Quick Commands")
        quick_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(quick_frame, text="Command:").pack(side=tk.LEFT, padx=5)
        self.cmd_combo = ttk.Combobox(
            quick_frame,
            textvariable=self.cmd_var,
            state="readonly",
            width=30
        )
        self.cmd_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        radio_frame = ttk.Frame(quick_frame)
        radio_frame.pack(side=tk.LEFT, padx=5)

        self.query_radio = ttk.Radiobutton(
            radio_frame,
            text="Query (?)",
            variable=self.cmd_type,
            value="?"
        )
        self.set_radio = ttk.Radiobutton(
            radio_frame,
            text="Set (!)",
            variable=self.cmd_type,
            value="!"
        )
        self.query_radio.pack(side=tk.LEFT, padx=5)
        self.set_radio.pack(side=tk.LEFT, padx=5)

        # Parameter frame (for set commands)
        param_frame = ttk.Frame(self)
        param_frame.pack(fill=tk.X, padx=5, pady=5)

        self.param_label = ttk.Label(param_frame, text="Parameter:")
        self.param_label.pack(side=tk.LEFT, padx=5)

        # Two different widgets for parameter entry:
        # 1) A text entry
        self.param_entry = ttk.Entry(param_frame, textvariable=self.param_var, width=30)
        # 2) A combo (read-only) for enumerated options, shown only if command has options
        self.param_combo = ttk.Combobox(param_frame, textvariable=self.param_var, state="readonly", width=30)

        # Button to send the selected quick command
        self.quick_send_button = ttk.Button(param_frame, text="Send", command=self.send_quick_command)
        self.quick_send_button.pack(side=tk.RIGHT, padx=5)

        # Label to display command or parameter descriptions
        self.desc_label = ttk.Label(self, textvariable=self.desc_var, wraplength=500)
        self.desc_label.pack(fill=tk.X, padx=5, pady=5)

    def _update_commands(self, *args):
        """
        Updates the combo box with commands for the currently selected gauge type.
        If the gauge is a generic CDGxxxD, attempts to detect exact type if possible.
        """
        gauge_type = self.gauge_var.get()

        # If we have a communicator, we can attempt detection for CDGxxxD
        if self.communicator:
            if gauge_type == "CDGxxxD":
                detected_type = self.communicator.detect_gauge()
                if detected_type:
                    self.gauge_var.set(detected_type)
                    gauge_type = detected_type
                else:
                    self.desc_var.set("Error: Could not detect gauge type.")
                    self.cmd_combo['values'] = []
                    return

        # Looks up known commands for that gauge from GAUGE_PARAMETERS
        if gauge_type in GAUGE_PARAMETERS:
            commands = GAUGE_PARAMETERS[gauge_type].get("commands", {})
            # Builds a list with "name - description"
            cmd_list = [f"{name} - {cmd_info['desc']}" for name, cmd_info in commands.items()]
            # Assigns them to the combobox
            self.cmd_combo['values'] = cmd_list
            if cmd_list:
                self.cmd_combo.set(cmd_list[0])
                self._update_command_info()

    def _update_command_info(self, *args):
        """
        Updates the description label to match the selected command,
        and disables the "set" radio if the command is read-only.
        """
        selected = self.cmd_var.get()
        if selected and self.communicator:
            # Extracts the command’s short name (everything before " - ")
            cmd_name = selected.split(" - ")[0]
            # Looks it up in the communicator’s protocol definitions
            cmd_info = self.communicator.protocol._command_defs.get(cmd_name, {})

            self.desc_var.set(cmd_info.get("desc", "No description available"))

            # If the command is writable, enables both radio buttons
            if cmd_info.get("write", False):
                self.query_radio.configure(state="normal")
                self.set_radio.configure(state="normal")
            else:
                # If read-only, sets radio to "?"
                self.cmd_type.set("?")
                self.query_radio.configure(state="normal")
                self.set_radio.configure(state="disabled")

            self._update_parameter_state()

    def send_manual_command(self):
        """
        Reads the text from the manual command entry,
        sends it via the IntelligentCommandSender,
        and clears the entry.
        """
        if not self.communicator:
            return

        cmd = self.manual_cmd_entry.get().strip()
        if cmd:
            result = IntelligentCommandSender.send_manual_command(self.communicator, cmd)
            self.manual_cmd_entry.delete(0, tk.END)

            if self.command_callback:
                # Builds a GaugeResponse to pass back
                response = GaugeResponse(
                    raw_data=bytes.fromhex(result.get('response_raw', '')) if result.get('response_raw') else b'',
                    formatted_data=result.get('response_formatted', ''),
                    success=result.get('success', False),
                    error_message=result.get('error', None)
                )
                self.command_callback(cmd, response=response)

    def _update_parameter_state(self, *args):
        """
        Shows parameter entry/combobox only if user chooses a 'set' command
        and if the underlying command definition has options or numeric parameters.
        """
        if not self.communicator or not self.cmd_var.get():
            return

        cmd_name = self.cmd_var.get().split(" - ")[0]
        cmd_info = self.communicator.protocol._command_defs.get(cmd_name, {})

        # Hides both parameter widgets first
        self.param_entry.pack_forget()
        self.param_combo.pack_forget()

        # If the user chose to set (!), shows either a combo for enumerated options or an entry
        if self.cmd_type.get() == "!":
            self.param_label.configure(state="normal")
            if "options" in cmd_info:
                # For enumerated options
                options = [f"{val} - {desc}" for val, desc in zip(cmd_info["options"], cmd_info["option_desc"])]
                self.param_combo['values'] = options
                self.param_combo.set(options[0] if options else "")
                self.param_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
                self.param_combo.configure(state="readonly")
            else:
                # For numeric/string entry
                self.param_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
                self.param_entry.configure(state="normal")
                # If there's a min/max range, show it in the desc label
                if "min" in cmd_info and "max" in cmd_info:
                    self.desc_var.set(
                        f"{cmd_info['desc']} (Range: {cmd_info['min']}-{cmd_info['max']} {cmd_info.get('unit', '')})"
                    )
        else:
            # Disables parameter input if it’s a read command
            self.param_label.configure(state="disabled")
            self.param_var.set("")

    def send_quick_command(self):
        """
        Builds a GaugeCommand object from the user’s selection (cmd_var, cmd_type, param_var)
        and sends it via the communicator.
        """
        if not self.communicator:
            return

        selected = self.cmd_var.get()
        if selected:
            cmd_name = selected.split(" - ")[0]
            param_value = self.param_var.get()

            # If the user selects something like '3 - On/Off', split off the numeric portion
            if " - " in param_value:
                param_value = param_value.split(" - ")[0]

            # Builds a GaugeCommand with parameters (if user wants to set something)
            command = GaugeCommand(
                name=cmd_name,
                command_type=self.cmd_type.get(),
                parameters={"value": param_value} if self.cmd_type.get() == "!" else None
            )

            response = self.communicator.send_command(command)
            if self.command_callback:
                self.command_callback(cmd_name, response=response)

    def set_enabled(self, enabled: bool):
        """
        Enables or disables all relevant widgets in this frame.
        called by main_app when connecting/disconnecting.
        """
        state = "normal" if enabled else "disabled"
        widgets = [
            self.manual_cmd_entry,
            self.manual_send_button,
            self.cmd_combo,
            self.query_radio,
            self.set_radio,
            self.param_entry,
            self.quick_send_button
        ]
        for widget in widgets:
            widget.configure(state=state)

        # If re-enabled, refresh info
        if enabled:
            self._update_command_info()

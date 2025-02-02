"""
GUI/serial_settings_frame.py

Defines the SerialSettingsFrame class which lets the user configure serial settings
and send manual commands.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable


class SerialSettingsFrame(ttk.LabelFrame):
    """
    Frame for RS232/RS485 serial settings and manual command entry.
    """

    def __init__(self, parent: tk.Widget, settings_callback: Callable, command_callback: Callable) -> None:
        """
        Initialize SerialSettingsFrame.

        Args:
            parent: Parent widget.
            settings_callback: Function called when settings change.
            command_callback: Function called for sending manual commands.
        """
        super().__init__(parent, text="Serial Settings & Manual Command")
        self.settings_callback = settings_callback
        self.command_callback = command_callback
        self.parent_app = None  # To be set via set_parent

        self.baud_var = tk.StringVar(value="9600")
        self.bytesize_var = tk.StringVar(value="8")
        self.parity_var = tk.StringVar(value="N")
        self.stopbits_var = tk.StringVar(value="1")
        self.rs485_mode = tk.BooleanVar(value=False)
        self.rs485_addr = tk.StringVar(value="254")

        self.cmd_history: list[str] = []
        self.history_index = -1

        self._create_widgets()

    def _create_widgets(self) -> None:
        """
        Creates the widgets for serial settings and manual command entry.
        """
        settings_frame = ttk.Frame(self)
        settings_frame.pack(fill=tk.X, padx=5, pady=5)

        left_frame = ttk.Frame(settings_frame)
        left_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(left_frame, text="Baud:").pack(side=tk.LEFT, padx=2)
        baud_menu = ttk.Combobox(left_frame, textvariable=self.baud_var,
                                  values=["1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"], width=7)
        baud_menu.pack(side=tk.LEFT, padx=2)
        ttk.Label(left_frame, text="Bits:").pack(side=tk.LEFT, padx=2)
        bytesize_menu = ttk.Combobox(left_frame, textvariable=self.bytesize_var, values=["5", "6", "7", "8"], width=2)
        bytesize_menu.pack(side=tk.LEFT, padx=2)

        center_frame = ttk.Frame(settings_frame)
        center_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(center_frame, text="Parity:").pack(side=tk.LEFT, padx=2)
        parity_menu = ttk.Combobox(center_frame, textvariable=self.parity_var, values=["N", "E", "O", "M", "S"], width=2)
        parity_menu.pack(side=tk.LEFT, padx=2)
        ttk.Label(center_frame, text="Stop:").pack(side=tk.LEFT, padx=2)
        stopbits_menu = ttk.Combobox(center_frame, textvariable=self.stopbits_var, values=["1", "1.5", "2"], width=3)
        stopbits_menu.pack(side=tk.LEFT, padx=2)

        right_frame = ttk.Frame(settings_frame)
        right_frame.pack(side=tk.LEFT, padx=5)
        rs485_frame = ttk.Frame(right_frame)
        rs485_frame.pack(side=tk.LEFT, padx=2)
        self.rs485_check = ttk.Checkbutton(rs485_frame, text="RS485", variable=self.rs485_mode,
                                           command=self._on_rs485_change)
        self.rs485_check.pack(side=tk.LEFT, padx=2)
        ttk.Label(rs485_frame, text="Addr:").pack(side=tk.LEFT, padx=2)
        self.rs485_addr_entry = ttk.Entry(rs485_frame, textvariable=self.rs485_addr, width=4)
        self.rs485_addr_entry.pack(side=tk.LEFT, padx=2)
        self._update_rs485_address_state()

        ttk.Button(right_frame, text="Apply", command=self.apply_settings, width=8).pack(side=tk.LEFT, padx=5)

    def _update_rs485_address_state(self) -> None:
        """
        Enables or disables the RS485 address entry based on rs485_mode.
        """
        state = "normal" if self.rs485_mode.get() else "disabled"
        self.rs485_addr_entry.configure(state=state)

    def _on_rs485_change(self) -> None:
        """
        Called when the RS485 checkbox is toggled.
        """
        self._update_rs485_address_state()
        settings = self.get_current_settings()
        self.settings_callback(settings)

    def get_current_settings(self) -> dict:
        """
        Returns the current serial settings as a dictionary.
        """
        return {
            'baudrate': int(self.baud_var.get()),
            'bytesize': int(self.bytesize_var.get()),
            'parity': self.parity_var.get(),
            'stopbits': float(self.stopbits_var.get()),
            'rs485_mode': self.rs485_mode.get(),
            'rs485_address': int(self.rs485_addr.get())
        }

    def apply_settings(self) -> None:
        """
        Called when the Apply button is pressed.
        Gets current settings and sends them via the callback.
        Also logs the applied settings.
        """
        settings = self.get_current_settings()
        self.settings_callback(settings)
        settings_msg = (
            f"\nSerial settings applied:\n"
            f"Baud Rate: {settings['baudrate']}\n"
            f"Data Bits: {settings['bytesize']}\n"
            f"Parity: {settings['parity']}\n"
            f"Stop Bits: {settings['stopbits']}\n"
        )
        if settings['rs485_mode']:
            settings_msg += f"RS485 Mode: Enabled\nRS485 Address: {settings['rs485_address']}\n"
        else:
            settings_msg += "RS485 Mode: Disabled\n"
        if self.parent_app:
            self.parent_app.log_message(settings_msg)

    def set_parent(self, parent_app: object) -> None:
        """
        Sets a reference to the parent application.
        """
        self.parent_app = parent_app

    def set_rs485_mode(self, enabled: bool, address: int = 254) -> None:
        """
        Externally sets the RS485 mode and address.
        """
        self.rs485_mode.set(enabled)
        self.rs485_addr.set(str(address))
        self._update_rs485_address_state()
        self._on_rs485_change()

    def send_command(self, event=None) -> None:
        """
        Sends the manual command entered by the user.
        """
        cmd = self.manual_cmd_entry.get().strip()
        if cmd:
            self.command_callback(cmd)
            self.manual_cmd_entry.delete(0, tk.END)
            if not self.cmd_history or self.cmd_history[-1] != cmd:
                self.cmd_history.append(cmd)
            self.history_index = len(self.cmd_history)

    def history_up(self, event) -> None:
        """
        Recalls the previous command from history.
        """
        if self.cmd_history and self.history_index > 0:
            self.history_index -= 1
            self.manual_cmd_entry.delete(0, tk.END)
            self.manual_cmd_entry.insert(0, self.cmd_history[self.history_index])

    def history_down(self, event) -> None:
        """
        Recalls the next command from history.
        """
        if self.history_index < len(self.cmd_history) - 1:
            self.history_index += 1
            self.manual_cmd_entry.delete(0, tk.END)
            self.manual_cmd_entry.insert(0, self.cmd_history[self.history_index])

    def set_enabled(self, enabled: bool) -> None:
        """
        Enables or disables all widgets in the frame.
        """
        state = "normal" if enabled else "disabled"
        for widget in self.winfo_children():
            for child in widget.winfo_children():
                child.configure(state=state)

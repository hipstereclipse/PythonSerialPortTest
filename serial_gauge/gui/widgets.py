from datetime import *
import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, Any
from ..config import GAUGE_PARAMETERS, OUTPUT_FORMATS
from serial_gauge.protocols import *

class CommandFrame(ttk.LabelFrame):
    """Frame for command selection and execution"""

    def __init__(self, parent, gauge_var, command_callback):
        super().__init__(parent, text="Commands")
        self.gauge_var = gauge_var
        self.command_callback = command_callback

        # Create instance variables
        self.cmd_var = tk.StringVar()
        self.cmd_type = tk.StringVar(value="?")
        self.param_var = tk.StringVar()
        self.desc_var = tk.StringVar()
        self.quick_cmd_var = tk.StringVar()

        # Quick commands dictionary
        self.quick_commands = {
            "PCG550": {
                "Read Pressure": {"cmd": "pressure", "type": "?"},
                "Read Temperature": {"cmd": "temperature", "type": "?"},
                "Read Serial Number": {"cmd": "serial_number", "type": "?"},
                "Read Product Name": {"cmd": "product_name", "type": "?"}
            },
            "PPG550": {
                "Read Combined Pressure": {"cmd": "PR3", "type": "?"},
                "Read Pirani Pressure": {"cmd": "PR1", "type": "?"},
                "Read Piezo Pressure": {"cmd": "PR2", "type": "?"},
                "Read Temperature": {"cmd": "T", "type": "?"},
                "Read Serial Number": {"cmd": "SN", "type": "?"},
                "Get Units": {"cmd": "U", "type": "?"}
            }
        }

        self.create_widgets()
        self.gauge_var.trace('w', self.update_commands)
        self.cmd_var.trace('w', self.update_command_info)
        self.gauge_var.trace('w', self.update_quick_commands)

        self.set_enabled(False)

    def on_format_change(self, *args):
        """Handle format change"""
        self.append_log(f"Output format changed to: {self.output_format.get()}")

    def append_log(self, message: str):
        """Add message to log with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.output_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.output_text.see(tk.END)

    def create_widgets(self):
        # Quick Command Frame
        quick_frame = ttk.Frame(self)
        quick_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(quick_frame, text="Quick Commands:").pack(side=tk.LEFT, padx=5)
        self.quick_combo = ttk.Combobox(
            quick_frame,
            textvariable=self.quick_cmd_var,
            state="readonly",
            width=30
        )
        self.quick_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        self.quick_send_button = ttk.Button(
            quick_frame,
            text="Send",
            command=self.send_quick_command  # Note the underscore
        )
        self.quick_send_button.pack(side=tk.LEFT, padx=5)

        # Separator
        ttk.Separator(self, orient="horizontal").pack(fill=tk.X, padx=5, pady=5)

        # Regular Command Frame
        cmd_frame = ttk.Frame(self)
        cmd_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(cmd_frame, text="Command:").pack(side=tk.LEFT, padx=5)
        self.cmd_combo = ttk.Combobox(
            cmd_frame,
            textvariable=self.cmd_var,
            state="readonly",
            width=30
        )
        self.cmd_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        self.query_radio = ttk.Radiobutton(
            cmd_frame,
            text="Query (?)",
            variable=self.cmd_type,
            value="?"
        )
        self.set_radio = ttk.Radiobutton(
            cmd_frame,
            text="Set (!)",
            variable=self.cmd_type,
            value="!"
        )
        self.query_radio.pack(side=tk.LEFT, padx=5)
        self.set_radio.pack(side=tk.LEFT, padx=5)

        # Parameter frame
        param_frame = ttk.Frame(self)
        param_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(param_frame, text="Parameter:").pack(side=tk.LEFT, padx=5)
        self.param_entry = ttk.Entry(
            param_frame,
            textvariable=self.param_var,
            width=30
        )
        self.param_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        self.send_button = ttk.Button(
            param_frame,
            text="Send",
            command=lambda: self.send_quick_command()  # Note the underscore
        )
        self.send_button.pack(side=tk.LEFT, padx=5)

        # Description label
        self.desc_label = ttk.Label(
            self,
            textvariable=self.desc_var,
            wraplength=500
        )
        self.desc_label.pack(fill=tk.X, padx=5, pady=5)

    def update_commands(self, *args):
        """Update available commands when gauge type changes"""
        try:
            gauge_type = self.gauge_var.get()
            if gauge_type and gauge_type in GAUGE_PARAMETERS:
                commands = GAUGE_PARAMETERS[gauge_type]["commands"]
                self.cmd_combo["values"] = list(commands.keys())
                if commands:
                    self.cmd_combo.set(list(commands.keys())[0])
        except Exception as e:
            print(f"Error updating commands: {str(e)}")

    def update_quick_commands(self, *args):
        """Update quick commands when gauge type changes"""
        try:
            gauge_type = self.gauge_var.get()
            if gauge_type in self.quick_commands:
                commands = self.quick_commands[gauge_type]
                self.quick_combo["values"] = list(commands.keys())
                if commands:
                    self.quick_combo.set(list(commands.keys())[0])
        except Exception as e:
            print(f"Error updating quick commands: {str(e)}")

    def send_quick_command(self):
        """Send the selected quick command"""
        try:
            gauge_type = self.gauge_var.get()
            quick_cmd_name = self.quick_cmd_var.get()

            if gauge_type and quick_cmd_name:
                cmd_info = self.quick_commands[gauge_type][quick_cmd_name]
                self.command_callback(
                    cmd_info["cmd"],
                    cmd_info["type"],
                    cmd_info.get("parameters")
                )
        except Exception as e:
            print(f"Error sending quick command: {str(e)}")

    def apply_settings(self):
        """Apply serial settings"""
        settings = {
            'baudrate': int(self.baud_var.get()),
            'bytesize': int(self.bytesize_var.get()),
            'parity': self.parity_var.get(),
            'stopbits': float(self.stopbits_var.get())
        }
        self.settings_callback(settings)

    def update_command_info(self, *args):
        """Update command information when selection changes"""
        try:
            gauge_type = self.gauge_var.get()
            cmd_name = self.cmd_var.get()

            if gauge_type and cmd_name and gauge_type in GAUGE_PARAMETERS:
                cmd_info = GAUGE_PARAMETERS[gauge_type]["commands"].get(cmd_name, {})

                # Update description
                self.desc_var.set(cmd_info.get("desc", ""))

                # Update parameter field based on command type
                cmd_type = cmd_info.get("type", "")
                if cmd_type == "read":
                    self.param_entry.config(state="disabled")
                    self.cmd_type.set("?")
                    self.set_radio.config(state="disabled")
                    self.query_radio.config(state="normal")
                elif cmd_type == "write":
                    self.param_entry.config(state="normal")
                    self.cmd_type.set("!")
                    self.set_radio.config(state="normal")
                    self.query_radio.config(state="disabled")
                else:  # both
                    self.param_entry.config(state="normal")
                    self.set_radio.config(state="normal")
                    self.query_radio.config(state="normal")
        except Exception as e:
            print(f"Error updating command info: {str(e)}")

    def send_command(self, event):
        """Send manual command"""
        cmd = self.cmd_entry.get().strip()
        if cmd:
            # Add to history if not duplicate of last command
            if not self.cmd_history or cmd != self.cmd_history[-1]:
                self.cmd_history.append(cmd)
            self.history_index = len(self.cmd_history)
            # Send command
            self.command_callback(cmd)
            # Clear entry
            self.cmd_entry.delete(0, tk.END)
        return 'break'  # Prevent default handling

    def history_up(self, event):
        """Navigate command history upward"""
        if self.cmd_history and self.history_index > 0:
            self.history_index -= 1
            self.cmd_entry.delete(0, tk.END)
            self.cmd_entry.insert(0, self.cmd_history[self.history_index])
        return 'break'

    def history_down(self, event):
        """Navigate command history downward"""
        if self.history_index < len(self.cmd_history) - 1:
            self.history_index += 1
            self.cmd_entry.delete(0, tk.END)
            self.cmd_entry.insert(0, self.cmd_history[self.history_index])
        else:
            self.history_index = len(self.cmd_history)
            self.cmd_entry.delete(0, tk.END)
        return 'break'

    def set_enabled(self, enabled: bool):
        """Enable/disable the command interface"""
        state = "normal" if enabled else "disabled"
        readonly_state = "readonly" if enabled else "disabled"

        # Update quick command controls
        self.quick_combo.config(state=readonly_state)
        self.quick_send_button.config(state=state)

        # Update regular command controls
        self.cmd_combo.config(state=readonly_state)
        self.query_radio.config(state=state)
        self.set_radio.config(state=state)
        self.param_entry.config(state=state)
        self.send_button.config(state=state)


class SerialSettingsFrame(ttk.LabelFrame):
    """Frame for RS232 settings and manual command entry"""

    def __init__(self, parent: tk.Widget, settings_callback: Callable, command_callback: Callable):
        super().__init__(parent, text="Serial Settings & Manual Command")
        self.settings_callback = settings_callback
        self.command_callback = command_callback

        # Create variables for settings
        self.baud_var = tk.StringVar(value="9600")
        self.bytesize_var = tk.StringVar(value="8")
        self.parity_var = tk.StringVar(value="N")
        self.stopbits_var = tk.StringVar(value="1")

        self.create_widgets()

    def create_widgets(self):
        # Settings Frame
        settings_frame = ttk.Frame(self)
        settings_frame.pack(fill=tk.X, padx=5, pady=5)

        # Baud Rate
        ttk.Label(settings_frame, text="Baud Rate:").pack(side=tk.LEFT, padx=5)
        baud_menu = ttk.Combobox(
            settings_frame,
            textvariable=self.baud_var,
            values=["1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"],
            width=8
        )
        baud_menu.pack(side=tk.LEFT, padx=5)

        # Byte Size
        ttk.Label(settings_frame, text="Byte Size:").pack(side=tk.LEFT, padx=5)
        bytesize_menu = ttk.Combobox(
            settings_frame,
            textvariable=self.bytesize_var,
            values=["5", "6", "7", "8"],
            width=3
        )
        bytesize_menu.pack(side=tk.LEFT, padx=5)

        # Parity
        ttk.Label(settings_frame, text="Parity:").pack(side=tk.LEFT, padx=5)
        parity_menu = ttk.Combobox(
            settings_frame,
            textvariable=self.parity_var,
            values=["N", "E", "O", "M", "S"],
            width=3
        )
        parity_menu.pack(side=tk.LEFT, padx=5)

        # Stop Bits
        ttk.Label(settings_frame, text="Stop Bits:").pack(side=tk.LEFT, padx=5)
        stopbits_menu = ttk.Combobox(
            settings_frame,
            textvariable=self.stopbits_var,
            values=["1", "1.5", "2"],
            width=3
        )
        stopbits_menu.pack(side=tk.LEFT, padx=5)

        # Apply Settings Button
        ttk.Button(
            settings_frame,
            text="Apply Settings",
            command=self.apply_settings
        ).pack(side=tk.LEFT, padx=20)

        # Manual Command Frame
        cmd_frame = ttk.Frame(self)
        cmd_frame.pack(fill=tk.X, padx=5, pady=5)

        # Command Entry
        ttk.Label(cmd_frame, text="Manual Command:").pack(side=tk.LEFT, padx=5)
        self.cmd_entry = ttk.Entry(cmd_frame, width=50)
        self.cmd_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # Add command history
        self.cmd_history = []
        self.history_index = -1
        self.cmd_entry.bind('<Return>', self.send_command)
        self.cmd_entry.bind('<Up>', self.history_up)
        self.cmd_entry.bind('<Down>', self.history_down)

        # Send Button
        ttk.Button(
            cmd_frame,
            text="Send",
            command=lambda: self.send_command(None)
        ).pack(side=tk.LEFT, padx=5)

    def apply_settings(self):
        """Apply serial settings"""
        settings = {
            'baudrate': int(self.baud_var.get()),
            'bytesize': int(self.bytesize_var.get()),
            'parity': self.parity_var.get(),
            'stopbits': float(self.stopbits_var.get())
        }
        self.settings_callback(settings)

    def send_command(self, event):
        """Send manual command"""
        cmd = self.cmd_entry.get().strip()
        if cmd:
            # Add to history if not duplicate of last command
            if not self.cmd_history or cmd != self.cmd_history[-1]:
                self.cmd_history.append(cmd)
            self.history_index = len(self.cmd_history)
            # Send command
            self.command_callback(cmd)
            # Clear entry
            self.cmd_entry.delete(0, tk.END)
        return 'break'  # Prevent default handling

    def history_up(self, event):
        """Navigate command history upward"""
        if self.cmd_history and self.history_index > 0:
            self.history_index -= 1
            self.cmd_entry.delete(0, tk.END)
            self.cmd_entry.insert(0, self.cmd_history[self.history_index])
        return 'break'

    def history_down(self, event):
        """Navigate command history downward"""
        if self.history_index < len(self.cmd_history) - 1:
            self.history_index += 1
            self.cmd_entry.delete(0, tk.END)
            self.cmd_entry.insert(0, self.cmd_history[self.history_index])
        else:
            self.history_index = len(self.cmd_history)
            self.cmd_entry.delete(0, tk.END)
        return 'break'


class DebugFrame(ttk.LabelFrame):
    """Frame for debugging options"""
    def __init__(self, parent, baud_callback, enq_callback, settings_callback):
        super().__init__(parent, text="Debug")

        # Create debug controls frame
        controls_frame = ttk.Frame(self)
        controls_frame.pack(fill=tk.X, padx=5, pady=5)

        # Baud rate test button
        self.baud_button = ttk.Button(
            controls_frame,
            text="Try All Baud Rates",
            command=baud_callback
        )
        self.baud_button.pack(side=tk.LEFT, padx=5)

        # ENQ test button
        self.enq_button = ttk.Button(
            controls_frame,
            text="Send ENQ",
            command=enq_callback
        )
        self.enq_button.pack(side=tk.LEFT, padx=5)

        # Port settings button
        self.settings_button = ttk.Button(
            controls_frame,
            text="Show Settings",
            command=settings_callback
        )
        self.settings_button.pack(side=tk.LEFT, padx=5)

        # These buttons don't need to be disabled
        self.non_connection_buttons = [self.settings_button]

    def set_enabled(self, enabled: bool):
        """Enable/disable debug buttons that require connection"""
        state = "normal" if enabled else "disabled"

        # Only disable buttons that require connection
        for widget in self.winfo_children():
            for child in widget.winfo_children():
                if child not in self.non_connection_buttons:
                    child.config(state=state)


class OutputFrame(ttk.LabelFrame):
    """Frame for command output and logging"""

    def __init__(self, parent, output_format):
        super().__init__(parent, text="Output")
        self.output_format = output_format

        # Output format selection
        format_frame = ttk.Frame(self)
        format_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(format_frame, text="Format:").pack(side=tk.LEFT, padx=5)
        ttk.OptionMenu(
            format_frame,
            self.output_format,
            "ASCII",
            *OUTPUT_FORMATS
        ).pack(side=tk.LEFT, padx=5)

        # Output text area
        self.output_text = tk.Text(self, height=20, width=80)
        self.output_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Scrollbar
        scrollbar = ttk.Scrollbar(self.output_text)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.output_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.output_text.yview)

    def append_log(self, message: str):
        """Add message to log"""
        self.output_text.insert(tk.END, message + "\n")
        self.output_text.see(tk.END)
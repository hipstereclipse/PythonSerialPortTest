"""
OutputFrame: Displays logs and gauge responses with optional format selection.
"""

import tkinter as tk
from tkinter import ttk

# Imports the global list of known output formats
from serial_communication.config import OUTPUT_FORMATS


class OutputFrame(ttk.LabelFrame):
    """
    Frame for displaying command outputs and response logs.
    Provides a text area for logs and an option to select output formats.
    """

    def __init__(self, parent, output_format: tk.StringVar):
        """
        Initializes the OutputFrame.
        parent: The parent widget (usually the main window).
        output_format: A StringVar that tracks the current output format.
        """
        super().__init__(parent, text="Output")
        self.output_format = output_format

        # Creates a sub-frame for the format dropdown
        format_frame = ttk.Frame(self)
        format_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(format_frame, text="Format:").pack(side=tk.LEFT, padx=5)
        # Creates an OptionMenu to let the user pick an output format
        ttk.OptionMenu(
            format_frame,
            self.output_format,
            "ASCII",
            *OUTPUT_FORMATS
        ).pack(side=tk.LEFT, padx=5)

        # Creates a text widget to display logs
        self.output_text = tk.Text(self, height=20, width=80, wrap=tk.WORD)
        self.output_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Adds a scrollbar to the text widget
        scrollbar = ttk.Scrollbar(self.output_text, orient="vertical", command=self.output_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.output_text.config(yscrollcommand=scrollbar.set)

    def append_log(self, message: str):
        """
        Appends a message to the log text box and scrolls to the end.
        """
        self.output_text.insert(tk.END, message + "\n")
        self.output_text.see(tk.END)

    def clear(self):
        """
        Clears all content from the log text box.
        """
        self.output_text.delete(1.0, tk.END)

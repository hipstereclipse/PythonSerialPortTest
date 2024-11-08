# Import necessary modules
import tkinter as tk
from serial_gauge.gui.gui import GaugeApplication
import sys
import os

# Add the project root directory to Python path for module imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def main():
    """
    Main entry point of the application.
    Creates the root window and initializes the gauge application.
    """
    root = tk.Tk()  # Create the root window
    app = GaugeApplication(root)  # Initialize the application with the root window
    root.protocol("WM_DELETE_WINDOW", app.on_closing)  # Handle window close event
    root.mainloop()  # Start the main event loop

if __name__ == "__main__":
    main()
import tkinter as tk
import os
import time
import serial
import binascii
import keyboard

default_PN = "Enter PN"
default_SN = "Enter SN"

# Define the dictionary with framing parameters for each gauge
gauge_parameters = {
    "PPG550": {"baudrate": 9600, "bytesize": 8, "parity": serial.PARITY_NONE, "stopbits": serial.STOPBITS_ONE},
    "PSG550": {"baudrate": 9600, "bytesize": 8, "parity": serial.PARITY_NONE, "stopbits": serial.STOPBITS_ONE},
    "PCG550": {"baudrate": 57600, "bytesize": 8, "parity": serial.PARITY_NONE, "stopbits": serial.STOPBITS_ONE},
}

# Function to set the serial parameters based on the selected gauge
def update_serial_parameters(*args):
    gauge = gauge_selection.get()
    parameters = gauge_parameters.get(gauge, {})
    if parameters:
        ser.baudrate = parameters["baudrate"]
        ser.bytesize = parameters["bytesize"]
        ser.parity = parameters["parity"]
        ser.stopbits = parameters["stopbits"]
        log_console_data(f"Serial settings updated for {gauge}: {parameters}")

# Function to log data to the file
def log_data(data):
    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{current_time}] {data}"
    with open(f"{part_number}_{serial_number}_log.txt", "a") as log_file:
        log_file.write(log_entry + "\n")
        log_file.flush()  # Flush the buffer to ensure immediate write to the file
    log_console_data(log_entry)  # Log the data to the console_area

def log_console_data(data):
    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{current_time}] {data}"
    console_area.insert(tk.END, log_entry + "\n")
    console_area.see(tk.END)

# Check if the log file exists
def check_log_file():
    log_file_path = f"{part_number}_{serial_number}_log.txt"
    if not os.path.isfile(log_file_path):
        # Generate a new log file
        with open(log_file_path, "w") as log_file:
            log_file.write("Serial Log\n")
            log_file.write(time.ctime() + "\n")
            log_file.write("-" * 20 + "\n")

# Define initial values for part_number and serial_number
part_number = ""
serial_number = ""

ser = serial.Serial(port="COM5", baudrate=57600, bytesize=8, timeout=5, stopbits=serial.STOPBITS_ONE)

def send_command(command):
    # Send the command to the gauge with a delay for processing
    ser.write(command.encode('ascii'))
    log_data(f"Sent command: {command}")

    # Delay to allow for device response
    time.sleep(0.5)  # Adjust delay as needed

    # Collect the complete response
    response = ser.read_until(b'\n')  # Read until newline or specify a larger read buffer if needed
    log_response(response)


# Enhanced log_response function to handle multiple response formats
def log_response(response):
    current_format = selected_format.get()

    if current_format == "Hex":
        response_text = ' '.join(f'{byte:02x}' for byte in response)
    elif current_format == "Binary":
        response_text = ' '.join(f'{bin(byte)[2:].zfill(8)}' for byte in response)
    elif current_format == "ASCII":
        try:
            response_text = response.decode('ascii', errors='replace')
        except UnicodeDecodeError:
            response_text = ''.join(f'{byte:02x}' for byte in response)
    elif current_format == "UTF-8":
        try:
            response_text = response.decode('utf-8', errors='replace')
        except UnicodeDecodeError:
            response_text = ''.join(f'{byte:02x}' for byte in response)
    elif current_format == "Decimal":
        response_text = ' '.join(str(byte) for byte in response)
    elif current_format == "Raw Bytes":
        response_text = str(response)

    log_console_data(f"Received response ({current_format}): {response_text}")


def display_response(response):
    # Convert the response to hex format
    response_text = ' '.join(f'{byte:02x}' for byte in response)

    output_area.configure(state=tk.NORMAL)
    output_area.insert(tk.END, f"Response (Hex): {response_text}\n")
    output_area.configure(state=tk.DISABLED)
    log_data(f"Received response (Hex): {response_text}")
def query_serial_number():
    command = "@254SN?\\"  # The command for querying serial number
    output_area.insert(tk.END, f"> {command}\n")
    output_area.insert(tk.END, "Command processed!\n\n")
    output_area.see(tk.END)  # Scroll to the bottom
    log_data(f"Command entered: {command}")
    send_command(command)  # Send the command to the gauge

def query_part_number():
    command = "@254PN?\\"  # The command for querying part number
    output_area.insert(tk.END, f"> {command}\n")
    output_area.insert(tk.END, "Command processed!\n\n")
    output_area.see(tk.END)  # Scroll to the bottom
    log_data(f"Command entered: {command}")
    send_command(command)  # Send the command to the gauge

def set_address():
    address = address_entry.get().strip()
    if address.isdigit():
        send_command(f"@254ADR!{address}\\")
        address_entry.delete(0, tk.END)

# Function to handle the Enter button click event
# Function to handle the Enter button click event
def handle_command(event=None):
    # Retrieve the text from the input area
    command = input_area.get("1.0", tk.END).strip()

    # If there's a command, send it to the gauge
    if command:
        # Display the command in output_area
        output_area.insert(tk.END, f"> {command}\n")
        output_area.insert(tk.END, "Command processed!\n\n")
        output_area.see(tk.END)  # Scroll to bottom of output area
        log_data(f"Command entered: {command}")  # Log command

        # Send the command to the gauge and handle response in the console
        send_command(command)

    # Clear the input area after sending the command
    input_area.delete("1.0", tk.END)

# Function to send a query and display the response
def query_name():
    console_area.insert(tk.END, f"Gauge Manufacturer Queried {time.strftime('%Y-%m-%d')} {time.strftime('%H:%M:%S')}\n")

    # ASCII command to query the gauge
    command = "@243P?MP\\"

    # Send the ASCII command as bytes
    ser.write(command.encode('ascii'))
    log_data("Query command sent.")
    output_area.insert(tk.END, "Query command sent.\n")

    # Read Response message frame
    response_frame = ser.read(8)  # Adjust the read size based on the expected response length
    log_data("Read Response received.")

    # After obtaining the response frame
    output_area.configure(state=tk.NORMAL)
    output_area.delete("1.0", tk.END)
    log_data("Response:")
    output_area.insert(tk.END, response_frame.decode() + "\n")  # Convert bytes to string
    log_data(response_frame.decode())  # Log the response
    output_area.configure(state=tk.DISABLED)
    change_output_format(output_format.get(), response_frame)

# Function to handle the output format change

def change_output_format(selection, response_frame=None):
    if response_frame is None:
        # No response to process yet, just updating format selection
        log_console_data(f"Output format set to: {selection}")
        return

    # Process the response based on the selected format if response_frame is provided
    if selection == "Hex":
        formatted_response = ' '.join(f'{byte:02x}' for byte in response_frame)
    elif selection == "Binary":
        formatted_response = ' '.join(f'{bin(byte)[2:].zfill(8)}' for byte in response_frame)
    elif selection == "ASCII":
        formatted_response = response_frame.decode('ascii', errors='replace')
    elif selection == "UTF-8":
        try:
            formatted_response = response_frame.decode('utf-8', errors='replace')
        except UnicodeDecodeError:
            formatted_response = ' '.join(f'{byte:02x}' for byte in response_frame)
    elif selection == "Decimal":
        formatted_response = ' '.join(str(byte) for byte in response_frame)
    elif selection == "Raw Bytes":
        formatted_response = str(response_frame)

    log_console_data(f"Formatted response ({selection}): {formatted_response}")


def change_console_format(selection, response_frame=None):
    console_area.configure(state=tk.NORMAL)
    console_area.delete("1.0", tk.END)

    if response_frame:
        if selection == "Hex":
            for byte in response_frame:
                console_area.insert(tk.END, hex(byte) + "\n")
        elif selection == "Binary":
            binary_representation = ' '.join(f'{bin(byte)[2:].zfill(8)}' for byte in response_frame)
            console_area.insert(tk.END, binary_representation + "\n")
        elif selection == "ASCII":
            console_area.insert(tk.END, response_frame.decode('ascii', errors='replace') + "\n")
        elif selection == "UTF-8":
            try:
                console_area.insert(tk.END, response_frame.decode('utf-8', errors='replace') + "\n")
            except UnicodeDecodeError:
                hex_representation = ' '.join(f'{byte:02x}' for byte in response_frame)
                console_area.insert(tk.END, hex_representation + "\n")
        elif selection == "Decimal":
            decimal_representation = ' '.join(str(byte) for byte in response_frame)
            console_area.insert(tk.END, decimal_representation + "\n")
        elif selection == "Raw Bytes":
            console_area.insert(tk.END, str(response_frame) + "\n")

    console_area.configure(state=tk.DISABLED)

# Function to display the log on the output_area
def display_log():
    global part_number, serial_number
    output_area.configure(state=tk.NORMAL)
    output_area.delete("1.0", tk.END)

    log_file_path = f"{part_number}_{serial_number}_log.txt"
    if not os.path.isfile(log_file_path):
        output_area.insert(tk.END, f"Log file '{log_file_path}' does not exist.\n")
        return

    with open(log_file_path, "r") as log_file:
        log_contents = log_file.read()

    # Add part number, serial number, log date, and log time to the log file contents
    part_number = gauge_PN.get()
    serial_number = gauge_SN.get()
    log_header = f"Part Number: {part_number}\nSerial Number: {serial_number}\nLog Date: {time.strftime('%Y-%m-%d')}\nLog Time: {time.strftime('%H:%M:%S')}\n"
    log_contents = log_header + log_contents

    output_area.insert(tk.END, log_contents)
    output_area.configure(state=tk.DISABLED)
    console_area.insert(tk.END, f"Log Displayed {time.strftime('%Y-%m-%d')} {time.strftime('%H:%M:%S')}\n")

# Function to scroll to the top of the output_area
def scroll_to_top():
    output_area.yview_moveto(0)

# Function to scroll to the bottom of the output_area
def scroll_to_bottom():
    output_area.yview_moveto(1)

# Function to handle the serial number entry
def handle_serial_number_entry(event=None):
    global serial_number
    serial_number = gauge_SN.get()
    check_log_file()

# Function to handle the part number entry
def handle_part_number_entry(event=None):
    global part_number
    part_number = gauge_PN.get()

# Function to save the log file
def save_log_file():
    global part_number, serial_number
    part_number = gauge_PN.get()
    serial_number = gauge_SN.get()

    if part_number == "" or serial_number == "":
        output_area.insert(tk.END, "Please enter the part number and serial number.\n")
        return

    log_file_path = f"{part_number}_{serial_number}_log.txt"
    if not os.path.exists(log_file_path):
        output_area.insert(tk.END, f"Log file '{log_file_path}' does not exist.\n")
        return

    with open(log_file_path, "r") as log_file:
        log_contents = log_file.read()

    save_file_path = f"{part_number}_{serial_number}_log.txt"
    with open(save_file_path, "w") as save_file:
        save_file.write(log_contents)
    log_data("Log file saved.")

    # Add a message to the output area
    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
    message = f"Log of Part Number: {part_number}, Serial Number: {serial_number}, saved at {current_time}\n"
    output_area.insert(tk.END, message)

# Function to load a log file
def load_log_file():
    part_number = gauge_PN.get()
    serial_number = gauge_SN.get()
    log_file_path = f"{part_number}_{serial_number}_log.txt"
    if os.path.isfile(log_file_path):
        with open(log_file_path, "r") as log_file:
            log_contents = log_file.read()
        output_area.configure(state=tk.NORMAL)
        output_area.delete("1.0", tk.END)
        output_area.insert(tk.END, log_contents)
        output_area.configure(state=tk.DISABLED)
        log_data("Log file loaded.")
    else:
        log_data("Log file not found.")
        output_area.configure(state=tk.NORMAL)
        output_area.delete("1.0", tk.END)
        output_area.insert(tk.END, "No log file found.\n")
        output_area.configure(state=tk.DISABLED)

window = tk.Tk()
window.geometry("660x755")
window.title("David's Gauge Communicator / Logger")
# Make the window non-resizable
window.resizable(False, False)
# Create a frame for the Gauge label and dropdown to keep them side by side
gauge_frame = tk.Frame(window)
gauge_frame.grid(row=0, column=0, sticky=tk.W, padx=10, pady=10)

# Create and add Gauge label within the frame
gN_label = tk.Label(gauge_frame, text="Gauge:", font=('Arial', 12))
gN_label.pack(side=tk.LEFT)

# Add dropdown menu for gauge selection next to the label
gauge_selection = tk.StringVar()
gauge_selection.set("Select Gauge")  # Default value

gauge_menu = tk.OptionMenu(gauge_frame, gauge_selection, *gauge_parameters.keys())
gauge_menu.pack(side=tk.LEFT, padx=(5, 0))  # Small padding between label and dropdown

# Bind selection change to update_serial_parameters function
gauge_selection.trace("w", update_serial_parameters)

# Create a frame for the Gauge Address entry and Set Address button in row 0
address_frame = tk.Frame(window)
address_frame.grid(row=0, column=1, pady=10, sticky=tk.W)

# Add Gauge Address label, entry, and Set Address button to the address_frame
gN_label = tk.Label(address_frame, text="Device Address:", font=('Arial', 12))
gN_label.pack(side=tk.LEFT)

address_entry = tk.Entry(address_frame)
address_entry.pack(side=tk.LEFT, padx=(5, 5))

set_address_button = tk.Button(address_frame, text="Set Address", command=set_address)
set_address_button.pack(side=tk.LEFT)

# Create a frame for Gauge Part Number (PN) and Serial Number (SN) entries in row 1
gauge_frame = tk.Frame(window)
gauge_frame.grid(row=1, column=0, pady=10, sticky=tk.W)

# Add Gauge PN and Gauge SN entries to gauge_frame
gauge_PN = tk.Entry(gauge_frame)
gauge_PN.insert(0, default_PN)
gauge_PN.pack(side=tk.LEFT, padx=(5, 5))  # Small padding between PN and SN

gauge_SN = tk.Entry(gauge_frame)
gauge_SN.insert(0, default_SN)
gauge_SN.pack(side=tk.LEFT)

# Create a frame for Query buttons in row 2, column 0
query_frame = tk.Frame(window)
query_frame.grid(row=2, column=0, pady=10, sticky=tk.W)

# Add Query Part Number and Query Serial Number buttons to the query_frame
query_part_button = tk.Button(query_frame, text="Query Part Number", command=query_part_number)
query_part_button.pack(side=tk.LEFT, padx=(5, 5))  # Add small space between buttons

query_serial_button = tk.Button(query_frame, text="Query Serial Number", command=query_serial_number)
query_serial_button.pack(side=tk.LEFT)
# Create a frame for Load, Save, and Display Log buttons in row 2, column 1
save_load_frame = tk.Frame(window)
save_load_frame.grid(row=2, column=1, pady=10, sticky=tk.W)

# Add Load, Save, and Display Log buttons to the save_load_frame
load_button = tk.Button(save_load_frame, text="Load", command=load_log_file)
load_button.pack(side=tk.LEFT, padx=(0, 5))  # Add small space between buttons

save_button = tk.Button(save_load_frame, text="Save", command=save_log_file)
save_button.pack(side=tk.LEFT, padx=(0, 5))  # Add small space between buttons

display_log_button = tk.Button(save_load_frame, text="Display Log", command=display_log)
display_log_button.pack(side=tk.LEFT)

# Create a label (text) for output area
output_label = tk.Label(window, text="Output", font=('Arial', 18))
output_label.grid(row=3, column=0, columnspan=2)

# Create a Text widget for the output area
output_area = tk.Text(window, height=15, width=70)
output_area.grid(row=4, column=0, columnspan=2, padx=10)

# Create a scrollbar for the output area
scrollbar = tk.Scrollbar(window)

# Configure the output area to use the scrollbar
output_area.configure(yscrollcommand=scrollbar.set)
scrollbar.configure(command=output_area.yview)
scrollbar.grid(row=4, column=2, sticky=tk.N+tk.S)

# Create a button widget for the Scroll to Top button with a callback to the scroll_to_top function
scroll_top_button = tk.Button(window, text="Scroll to Top", command=scroll_to_top)
scroll_top_button.grid(row=5, column=0, pady=10)

# Create a button widget for the Scroll to Bottom button with a callback to the scroll_to_bottom function
scroll_bottom_button = tk.Button(window, text="Scroll to Bottom", command=scroll_to_bottom)
scroll_bottom_button.grid(row=5, column=1, pady=10)

# Create a label (text) for input area
input_label = tk.Label(window, text="Input", font=('Arial', 18))
input_label.grid(row=6, column=0, columnspan=2)

# Create a Text widget for the input area
input_area = tk.Text(window, height=1, width=50)
input_area.grid(row=7, column=0, columnspan=2, padx=10)

# Create a button widget for the Enter button with a callback to the handle_command function
enter_button = tk.Button(window, text="Enter", command=handle_command)
enter_button.grid(row=7, column=1, sticky=tk.E, padx=10)

# Create a frame for the output format selection and label in row 8, column 0
output_format_frame = tk.Frame(window)
output_format_frame.grid(row=8, column=0, sticky=tk.W)

# Add Output Format label and drop-down menu to the output_format_frame
output_format_label = tk.Label(output_format_frame, text="Expected Response Format:", font=('Arial', 12))
output_format_label.pack(side=tk.LEFT, padx=(0, 5))

# Set the width of the OptionMenu to the length of the longest option to prevent shifting
output_formats = ["Hex", "Binary", "ASCII", "UTF-8", "Decimal", "Raw Bytes"]
selected_format = tk.StringVar()
selected_format.set(output_formats[2])  # Default to ASCII

# Adjust width to match the longest option, ensuring the menu is wide enough
output_format_menu = tk.OptionMenu(output_format_frame, selected_format, *output_formats, command=change_output_format)
output_format_menu.config(width=max(len(option) for option in output_formats))  # Set fixed width based on longest text
output_format_menu.pack(side=tk.LEFT)

# Create a label (text) for console area
console_label = tk.Label(window, text="Console", font=('Arial', 18))
console_label.grid(row=9, column=0, columnspan=2)

# Create a Text widget for the console area
console_area = tk.Text(window, height=10, width=70)
console_area.grid(row=10, column=0, columnspan=2, padx=10)

# Create a scrollbar for the output area
console_scrollbar = tk.Scrollbar(window)

# Configure the output area to use the scrollbar
console_area.configure(yscrollcommand=console_scrollbar.set)
console_scrollbar.configure(command=console_area.yview)
console_scrollbar.grid(row=10, column=2, sticky=tk.N+tk.S)

# Create a variable to hold the selected output format
output_format = tk.StringVar()

# Bind the Enter key to the handle_command function
window.bind("<Return>", handle_command)

# Bind the Return key to the handle_serial_number_entry function
gauge_SN.bind("<Return>", handle_serial_number_entry)

# Bind the Return key to the handle_part_number_entry function
gauge_PN.bind("<Return>", handle_part_number_entry)

# Run the Tkinter event loop
window.mainloop()
# Close the serial port
ser.close()
import serial
import tkinter as tk
import time

# Adjust this port if necessary (check with `dmesg | grep tty`)
SERIAL_PORT = '/dev/ttyACM0'
BAUD_RATE = 115200

# Connect to Arduino
try:
    arduino = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)  # Wait for Arduino to reset
    print("Connected to Arduino")
except:
    print("Error: Could not connect to Arduino")
    exit()

# Function to send command and print response
def send(cmd):
    arduino.write((cmd + '\n').encode())
    time.sleep(0.1)
    while arduino.in_waiting:
        print("Arduino:", arduino.readline().decode().strip())

# Handle key press events
def key(event):
    key = event.keysym
    if key == 'Up':
        send("F:150")      # Forward
    elif key == 'Down':
        send("B:150")      # Backward
    elif key == 'Left':
        send("L:0")        # Turn left in place
    elif key == 'Right':
        send("R:0")        # Turn right in place
    elif key == 'space':
        send("X")          # Stop
    elif key == 's':
        send("S")          # Send sensor data

# Build GUI window
root = tk.Tk()
root.title("Robot Controller")

instructions = (
    "⬆️ Up Arrow = Forward\n"
    "⬇️ Down Arrow = Backward\n"
    "⬅️ Left Arrow = Turn Left\n"
    "➡️ Right Arrow = Turn Right\n"
    "Space = Stop\n"
    "S = Sensor Data\n\n"
    "Click this window and use keyboard"
)

label = tk.Label(root, text=instructions, font=('Helvetica', 14), justify="left", padx=20, pady=20)
label.pack()

root.bind('<KeyPress>', key)
root.mainloop()

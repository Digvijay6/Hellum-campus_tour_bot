import serial
import time

# def send_command_to_arduino(command, port='/dev/ttyACM0', baudrate=9600, timeout=2):
def send_command_to_arduino(command, port='COM5', baudrate=9600, timeout=2):
    # Open serial connection
    with serial.Serial(port, baudrate, timeout=timeout) as ser:
        time.sleep(2)  # Wait for Arduino to reset and get ready
        ser.write(command.encode())  # Send the command as bytes
        print(f"Sent to Arduino: {command}")
        
        # Optionally, read response
        response = ser.readline().decode(errors='ignore').strip()
        print(f"Arduino says: {response}")
        return response


# Example usage
if __name__ == "__main__":
    # Example: Send the string "LED_ON" to Arduino
    response = send_command_to_arduino("F")
    if response:
        print(f"Arduino responded: {response}")
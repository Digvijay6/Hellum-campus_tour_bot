import serial
import pynmea2
import time

def read_gps():
    try:
        # Open the serial port to communicate with GPS
        gps_serial = serial.Serial('/dev/ttyS0', baudrate=9600, timeout=1)
        print("✅ Serial port opened. Waiting for GPS data...\n")
        
        got_signal = False
        got_fix = False

        while True:
            line = gps_serial.readline().decode('ascii', errors='replace').strip()

            if not line:
                continue

            # Log when NMEA sentences start arriving
            if not got_signal and line.startswith('$'):
                got_signal = True
                print("📡 GPS module detected. Receiving NMEA sentences.")

            # Check for fix using GGA (Global Positioning System Fix Data)
            if line.startswith('$GPGGA'):
                try:
                    msg = pynmea2.parse(line)
                    fix_quality = int(msg.gps_qual)

                    if fix_quality > 0:
                        if not got_fix:
                            got_fix = True
                            print(f"✅ GPS Fix Acquired! Satellites: {msg.num_sats}")
                        print(f"🌍 Latitude: {msg.latitude}, Longitude: {msg.longitude}")
                    else:
                        print("❌ No GPS fix yet. Waiting for satellite lock...")

                except pynmea2.ParseError:
                    print("⚠️ Parse error in GGA sentence.")
                    continue

            elif line.startswith('$GPRMC'):
                try:
                    msg = pynmea2.parse(line)
                    if msg.status == 'A':
                        print(f"✔️  Valid RMC data - Lat: {msg.latitude}, Lon: {msg.longitude}")
                    else:
                        print("🚫 RMC data invalid or no fix.")
                except pynmea2.ParseError:
                    print("⚠️ Parse error in RMC sentence.")
                    continue

            time.sleep(1)

    except serial.SerialException as e:
        print(f"❌ Serial error: {e}")
    except KeyboardInterrupt:
        print("\n🛑 GPS reading stopped by user.")
    finally:
        if 'gps_serial' in locals() and gps_serial.is_open:
            gps_serial.close()
            print("🔌 Serial port closed.")

if __name__ == '__main__':
    read_gps()

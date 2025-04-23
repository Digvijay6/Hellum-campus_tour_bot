import requests
import math
import time
import serial
import json
import os
import logging
from typing import Tuple, List, Dict, Union, Optional
import polyline
from dataclasses import dataclass
import threading

def navigate(destination: str):

    print(f"[Function Call] Navigating to {destination}...")
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger("RobotNavigation")

    # Constants
    WAYPOINT_RADIUS = 2.0  # meters
    GPS_UPDATE_INTERVAL = 0.5  # seconds
    OBSTACLE_DISTANCE_THRESHOLD = 30  # cm, for ultrasonic sensors
    MAX_SPEED = 100  # maximum motor speed (0-255)
    MIN_SPEED = 50  # minimum motor speed
    CONFIG_FILE = "robot_config.json"
    HEADING_SOURCE = "magnetometer"  # Options: "gps", "magnetometer"
    GPS_AVERAGING_SAMPLES = 5  # Number of GPS readings to average for better accuracy
    MAX_GPS_AGE = 5.0  # Maximum age of GPS data in seconds before considering it stale

    @dataclass
    class RobotState:
        """Store current state of the robot"""
        lat: float = 0.0
        lon: float = 0.0
        heading: float = 0.0  # degrees, 0 = North, 90 = East
        speed: float = 0.0
        magnetometer_heading: Optional[float] = None
        gps_heading: Optional[float] = None
        obstacles: Dict[str, float] = None
        destination_reached: bool = False
        last_gps_update: float = 0.0
        navigation_active: bool = False
        current_waypoint_index: int = 0
        total_waypoints: int = 0
        distance_to_waypoint: float = 0.0
        bearing_to_waypoint: float = 0.0
        remaining_distance: float = 0.0

        def __post_init__(self):
            if self.obstacles is None:
                self.obstacles = {"front": 100, "left": 100, "right": 100}

    class GPSModule:
        """Handles GPS data acquisition and processing"""

        def __init__(self, port="/dev/ttyS0", baud=9600):
            self.port = port
            self.baud = baud
            self.serial_connected = False
            self.gps_data = []  # Store recent GPS readings for averaging
            self._connect()

        def _connect(self):
            """Connect to GPS module"""
            try:
                self.ser = serial.Serial(self.port, self.baud, timeout=1)
                self.serial_connected = True
                logger.info(f"Connected to GPS on {self.port}")
            except Exception as e:
                logger.error(f"Failed to connect to GPS: {e}")
                self.serial_connected = False

        def read_gps(self) -> Tuple[float, float]:
            """Read GPS data from serial and return lat, lon"""
            if not self.serial_connected:
                try:
                    self._connect()
                except Exception as e:
                    logger.error(f"Failed to reconnect to GPS: {e}")
                    logger.error("GPS reconnection failed")
                    return None, None

            try:
                # This is a simplified implementation
                # In a real implementation, you would parse NMEA sentences
                line = self.ser.readline().decode('ascii', errors='replace').strip()

                # Parse NMEA data (simplified)
                if line.startswith('$GPRMC') or line.startswith('$GNRMC'):
                    parts = line.split(',')
                    if len(parts) >= 7 and parts[2] == 'A':  # Valid fix
                        lat = float(parts[3][:2]) + float(parts[3][2:]) / 60
                        if parts[4] == 'S':
                            lat = -lat
                        lon = float(parts[5][:3]) + float(parts[5][3:]) / 60
                        if parts[6] == 'W':
                            lon = -lon
                        return lat, lon

                return None, None
            except Exception as e:
                logger.error(f"GPS read error: {e}")
                return None, None

        def get_averaged_position(self) -> Tuple[float, float]:
            """Get averaged GPS position from multiple readings for improved accuracy"""
            valid_readings = []

            # Collect several readings
            for _ in range(GPS_AVERAGING_SAMPLES):
                lat, lon = self.read_gps()
                if lat is not None and lon is not None:
                    valid_readings.append((lat, lon))
                time.sleep(0.2)  # Short delay between readings

            if not valid_readings:
                return None, None

            # Average the readings
            avg_lat = sum(r[0] for r in valid_readings) / len(valid_readings)
            avg_lon = sum(r[1] for r in valid_readings) / len(valid_readings)

            return avg_lat, avg_lon

        def calculate_heading_from_positions(self, prev_pos, current_pos) -> Optional[float]:
            """Calculate heading based on two GPS positions"""
            if not prev_pos or not current_pos:
                return None

            bearing = calculate_bearing(prev_pos[0], prev_pos[1], current_pos[0], current_pos[1])
            return bearing

    class SensorModule:
        """Handles various sensors for obstacle detection and orientation"""

        def __init__(self, arduino_port="/dev/ttyACM0", baud=115200):
            self.port = arduino_port
            self.baud = baud
            self.serial_connected = False
            self._connect()

        def _connect(self):
            """Connect to Arduino handling sensors"""
            try:
                self.ser = serial.Serial(self.port, self.baud, timeout=1)
                self.serial_connected = True
                logger.info(f"Connected to Arduino on {self.port}")
                time.sleep(2)  # Allow Arduino to reset after serial connection
            except Exception as e:
                logger.error(f"Failed to connect to Arduino: {e}")
                self.serial_connected = False

        def read_sensors(self) -> Dict:
            """Read all sensor data from Arduino"""
            if not self.serial_connected:
                try:
                    self._connect()
                except Exception as e:
                    logger.error(f"Failed to reconnect to Arduino: {e}")
                    logger.error("Arduino reconnection failed")
                    return {"error": "Connection failed"}

            try:
                # Clear any pending data
                self.ser.reset_input_buffer()

                # Request sensor readings
                self.ser.write(b'S\n')  # Send sensor read command

                # Wait a moment for Arduino to process and respond
                time.sleep(0.1)

                # Read the response
                response = self.ser.readline().decode('utf-8', errors='replace').strip()

                # Parse JSON response from Arduino
                data = json.loads(response)
                return data
            except Exception as e:
                logger.error(f"Sensor read error: {e}")
                return {"error": str(e)}

        def get_magnetometer_heading(self) -> Optional[float]:
            """Get heading from magnetometer in degrees (0-359.9)"""
            try:
                data = self.read_sensors()
                if "magnetometer" in data:
                    return float(data["magnetometer"])
                return None
            except Exception as e:
                logger.error(f"Magnetometer read error: {e}")
                return None

        def get_obstacle_distances(self) -> Dict[str, float]:
            """Get obstacle distances from ultrasonic sensors"""
            try:
                data = self.read_sensors()
                if "ultrasonic" in data:
                    return data["ultrasonic"]
                return {"front": 100, "left": 100, "right": 100}
            except Exception as e:
                logger.error(f"Obstacle distance read error: {e}")
                return {"front": 100, "left": 100, "right": 100}

    class MotionController:
        """Controls the robot's movement by sending commands to motors"""

        def __init__(self, arduino_port="/dev/ttyACM0", baud=115200):
            self.port = arduino_port
            self.baud = baud
            self.arduino = None
            self.connected = False
            self._connect()

        def _connect(self):
            """Connect to Arduino motor controller"""
            try:
                self.arduino = serial.Serial(self.port, self.baud, timeout=1)
                self.connected = True
                logger.info(f"Connected to motor controller on {self.port}")
                time.sleep(2)  # Allow Arduino to reset after serial connection
            except Exception as e:
                logger.error(f"Failed to connect to motor controller: {e}")
                self.connected = False

        def send_command(self, cmd: str, value: Optional[int] = None):
            """Send command to Arduino

            Commands:
            F - Forward (value = speed 0-255)
            B - Backward (value = speed 0-255)
            L - Left turn (value = turn radius, 0 = spin in place)
            R - Right turn (value = turn radius, 0 = spin in place)
            X - Stop
            """
            if not self.connected:
                try:
                    self._connect()
                except Exception as e:
                    logger.error(f"Failed to reconnect to motor controller: {e}")
                    logger.error("Motor controller reconnection failed")
                    return

            try:
                command = f"{cmd}"
                if value is not None:
                    command += f":{value}"
                command += "\n"

                self.arduino.write(command.encode())
                response = self.arduino.readline().decode('utf-8').strip()
                logger.debug(f"Motor command sent: {command.strip()}, Response: {response}")
            except Exception as e:
                logger.error(f"Failed to send motor command: {e}")

        def move_forward(self, speed=MAX_SPEED):
            """Move forward at specified speed"""
            self.send_command('F', speed)

        def move_backward(self, speed=MAX_SPEED):
            """Move backward at specified speed"""
            self.send_command('B', speed)

        def turn_left(self, radius=0):
            """Turn left with specified radius (0 = spin in place)"""
            self.send_command('L', radius)

        def turn_right(self, radius=0):
            """Turn right with specified radius (0 = spin in place)"""
            self.send_command('R', radius)

        def stop(self):
            """Stop all movement"""
            self.send_command('X')

    class NavigationSystem:
        """Main navigation system that integrates waypoints, sensors, and motion control"""

        def __init__(self, api_key, config_file=CONFIG_FILE):
            self.api_key = api_key
            self.config_file = config_file
            self.state = RobotState()

            # Initialize modules
            self.load_config()
            self.gps = GPSModule(port=self.config.get("gps_port", "/dev/ttyS0"))
            self.sensors = SensorModule(arduino_port=self.config.get("arduino_port", "/dev/ttyACM0"))
            self.motors = MotionController(arduino_port=self.config.get("arduino_port", "/dev/ttyACM0"))

            # Navigation data
            self.waypoints = []
            self.previous_position = None

            # Start background threads
            self.running = True
            self.gps_thread = threading.Thread(target=self._gps_update_loop)
            self.sensor_thread = threading.Thread(target=self._sensor_update_loop)
            self.gps_thread.daemon = True
            self.sensor_thread.daemon = True
            self.gps_thread.start()
            self.sensor_thread.start()

        def load_config(self):
            """Load robot configuration from file"""
            try:
                if os.path.exists(self.config_file):
                    with open(self.config_file, 'r') as f:
                        self.config = json.load(f)
                else:
                    # Default configuration
                    self.config = {
                        "gps_port": "/dev/ttyS0",
                        "arduino_port": "/dev/ttyACM0",
                        "waypoint_radius": WAYPOINT_RADIUS,
                        "obstacle_threshold": OBSTACLE_DISTANCE_THRESHOLD,
                        "heading_source": HEADING_SOURCE,
                        "max_speed": MAX_SPEED,
                        "min_speed": MIN_SPEED
                    }
                    with open(self.config_file, 'w') as f:
                        json.dump(self.config, f, indent=4)
            except Exception as e:
                logger.error(f"Error loading config: {e}")
                # Set default configuration
                self.config = {
                    "gps_port": "/dev/ttyS0",
                    "arduino_port": "/dev/ttyACM0",
                    "waypoint_radius": WAYPOINT_RADIUS,
                    "obstacle_threshold": OBSTACLE_DISTANCE_THRESHOLD,
                    "heading_source": HEADING_SOURCE,
                    "max_speed": MAX_SPEED,
                    "min_speed": MIN_SPEED
                }

        def _gps_update_loop(self):
            """Background thread to continuously update GPS position"""
            while self.running:
                try:
                    lat, lon = self.gps.get_averaged_position()
                    if lat is not None and lon is not None:
                        # Store previous position for heading calculation
                        self.previous_position = (self.state.lat, self.state.lon)

                        # Update current position
                        self.state.lat = lat
                        self.state.lon = lon
                        self.state.last_gps_update = time.time()

                        # Calculate GPS-based heading if we have previous position
                        if self.previous_position and self.previous_position != (lat, lon):
                            self.state.gps_heading = self.gps.calculate_heading_from_positions(
                                self.previous_position, (lat, lon)
                            )

                        # Update distance to current waypoint if navigating
                        if self.state.navigation_active and self.waypoints:
                            current_wp = self.waypoints[self.state.current_waypoint_index]
                            self.state.distance_to_waypoint = haversine_distance(
                                self.state.lat, self.state.lon,
                                current_wp[0], current_wp[1]
                            )
                            self.state.bearing_to_waypoint = calculate_bearing(
                                self.state.lat, self.state.lon,
                                current_wp[0], current_wp[1]
                            )

                            # Calculate total remaining distance
                            remaining = 0
                            for i in range(self.state.current_waypoint_index, len(self.waypoints) - 1):
                                wp1 = self.waypoints[i]
                                wp2 = self.waypoints[i + 1]
                                remaining += haversine_distance(wp1[0], wp1[1], wp2[0], wp2[1])
                            self.state.remaining_distance = remaining

                            logger.debug(
                                f"GPS Update: {lat}, {lon}, Dist to WP: {self.state.distance_to_waypoint:.2f}m")
                except Exception as e:
                    logger.error(f"Error in GPS update loop: {e}")

                time.sleep(GPS_UPDATE_INTERVAL)

        def _sensor_update_loop(self):
            """Background thread to continuously update sensor readings"""
            while self.running:
                try:
                    # Update magnetometer heading
                    heading = self.sensors.get_magnetometer_heading()
                    if heading is not None:
                        self.state.magnetometer_heading = heading

                    # Update obstacle sensors
                    obstacles = self.sensors.get_obstacle_distances()
                    if obstacles:
                        self.state.obstacles = obstacles

                    # Set the heading based on configuration
                    if self.config["heading_source"] == "magnetometer" and self.state.magnetometer_heading is not None:
                        self.state.heading = self.state.magnetometer_heading
                    elif self.config["heading_source"] == "gps" and self.state.gps_heading is not None:
                        self.state.heading = self.state.gps_heading

                    logger.debug(f"Sensor Update: Heading: {self.state.heading}, Obstacles: {self.state.obstacles}")
                except Exception as e:
                    logger.error(f"Error in sensor update loop: {e}")

                time.sleep(0.2)  # Update sensors more frequently than GPS

        def geocode_address(self, address: str) -> Union[Tuple[float, float], None]:
            """Convert an address to coordinates using Google Geocoding API."""
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {
                "address": address,
                "key": self.api_key
            }

            try:
                response = requests.get(url, params=params)
                data = response.json()

                if data["status"] != "OK":
                    logger.error(f"Geocoding error: {data['status']}")
                    return None

                location = data["results"][0]["geometry"]["location"]
                return (location["lat"], location["lng"])

            except Exception as e:
                logger.error(f"Failed to geocode address: {e}")
                return None

        def get_waypoints(self, start_location: Tuple[float, float],
                          end_location: Union[str, Tuple[float, float]]) -> List[Tuple[float, float]]:
            """Get fine-grained waypoints using Google Directions API with polyline decoding."""

            # Geocode if end_location is an address
            if isinstance(end_location, str):
                geocoded_end = self.geocode_address(end_location)
                if not geocoded_end:
                    logger.error("Failed to geocode destination address")
                    return []
                end_location = geocoded_end
                logger.info(f"Geocoded destination to coordinates: {geocoded_end}")

            url = "https://maps.googleapis.com/maps/api/directions/json"
            params = {
                "origin": f"{start_location[0]},{start_location[1]}",
                "destination": f"{end_location[0]},{end_location[1]}",
                "mode": "walking",
                "key": self.api_key
            }

            try:
                response = requests.get(url, params=params)
                data = response.json()

                if data["status"] != "OK":
                    logger.error(f"Error getting directions: {data['status']}")
                    return []

                # Decode polyline from each step for detailed path
                waypoints = []
                for leg in data["routes"][0]["legs"]:
                    for step in leg["steps"]:
                        step_polyline = step["polyline"]["points"]
                        points = polyline.decode(step_polyline)
                        waypoints.extend(points)

                # Filter waypoints to reduce redundancy while preserving critical points
                filtered_waypoints = self._optimize_waypoints(waypoints)

                return filtered_waypoints

            except Exception as e:
                logger.error(f"Failed to get route: {e}")
                return []

        def _optimize_waypoints(self, waypoints: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
            """Optimize waypoints by removing redundant points while preserving path shape"""
            if len(waypoints) <= 2:
                return waypoints

            # Always keep first and last waypoints
            optimized = [waypoints[0]]

            # Douglas-Peucker algorithm for path simplification
            # This reduces the number of points while maintaining the path shape
            epsilon = 0.00001  # Adjust based on desired detail level

            def point_line_distance(point, line_start, line_end):
                if line_start == line_end:
                    return haversine_distance(point[0], point[1], line_start[0], line_start[1])

                # Calculate perpendicular distance from point to line
                # using the formula: d = |cross_product| / |line_vector|
                line_vector = (line_end[0] - line_start[0], line_end[1] - line_start[1])
                point_vector = (point[0] - line_start[0], point[1] - line_start[1])

                # Cross product magnitude
                cross = abs(line_vector[0] * point_vector[1] - line_vector[1] * point_vector[0])

                # Line length
                line_length = math.sqrt(line_vector[0] ** 2 + line_vector[1] ** 2)

                if line_length == 0:
                    return 0

                # Distance
                return cross / line_length

            def simplify_recursive(points, start_idx, end_idx):
                # Find point with maximum distance
                max_dist = 0
                max_idx = start_idx

                for i in range(start_idx + 1, end_idx):
                    dist = point_line_distance(points[i], points[start_idx], points[end_idx])
                    if dist > max_dist:
                        max_dist = dist
                        max_idx = i

                # If max distance is greater than epsilon, recursively simplify
                if max_dist > epsilon:
                    # Recursive call
                    simplify_recursive(points, start_idx, max_idx)
                    optimized.append(points[max_idx])
                    simplify_recursive(points, max_idx, end_idx)

            # Run recursive simplification
            simplify_recursive(waypoints, 0, len(waypoints) - 1)

            # Add last point
            optimized.append(waypoints[-1])

            # Sort optimized points to maintain original order
            optimized_indices = [waypoints.index(p) for p in optimized]
            optimized_indices.sort()
            sorted_optimized = [waypoints[i] for i in optimized_indices]

            logger.info(f"Optimized waypoints from {len(waypoints)} to {len(sorted_optimized)} points")
            return sorted_optimized

        def _adjust_speed_for_turn(self, angle_diff: float) -> int:
            """Calculate appropriate speed based on sharpness of turn"""
            # Normalize angle difference to -180 to 180
            angle_diff = (angle_diff + 180) % 360 - 180
            abs_diff = abs(angle_diff)

            # Reduce speed for sharper turns
            if abs_diff > 90:
                return self.config["min_speed"]
            elif abs_diff > 45:
                return int(self.config["min_speed"] + (self.config["max_speed"] - self.config["min_speed"]) * 0.3)
            elif abs_diff > 20:
                return int(self.config["min_speed"] + (self.config["max_speed"] - self.config["min_speed"]) * 0.7)
            else:
                return self.config["max_speed"]

        def _handle_obstacles(self) -> bool:
            """Check for obstacles and take avoidance action if needed
            Returns True if obstacle handling required stopping normal navigation
            """
            threshold = self.config["obstacle_threshold"]

            # Check front obstacle
            if self.state.obstacles["front"] < threshold:
                logger.warning(f"Obstacle detected ahead at {self.state.obstacles['front']}cm")
                self.motors.stop()

                # Check left and right for clearance
                if self.state.obstacles["left"] > self.state.obstacles["right"]:
                    logger.info("Turning left to avoid obstacle")
                    self.motors.turn_left()
                    time.sleep(0.5)
                else:
                    logger.info("Turning right to avoid obstacle")
                    self.motors.turn_right()
                    time.sleep(0.5)

                self.motors.stop()
                return True

            # Adjust for side obstacles
            elif self.state.obstacles["left"] < threshold:
                logger.info(f"Obstacle close on left at {self.state.obstacles['left']}cm")
                self.motors.turn_right(radius=50)  # Gentle right turn
                time.sleep(0.2)
                self.motors.move_forward()
                return True

            elif self.state.obstacles["right"] < threshold:
                logger.info(f"Obstacle close on right at {self.state.obstacles['right']}cm")
                self.motors.turn_left(radius=50)  # Gentle left turn
                time.sleep(0.2)
                self.motors.move_forward()
                return True

            return False

        def navigate_to_waypoint(self, waypoint: Tuple[float, float]) -> bool:
            """Navigate to a specific waypoint
            Returns True when waypoint is reached
            """
            # Calculate distance and bearing to waypoint
            distance = haversine_distance(
                self.state.lat, self.state.lon,
                waypoint[0], waypoint[1]
            )
            target_bearing = calculate_bearing(
                self.state.lat, self.state.lon,
                waypoint[0], waypoint[1]
            )

            logger.info(
                f"Navigating to waypoint: {waypoint}, Distance: {distance:.2f}m, Bearing: {target_bearing:.1f}°")

            # Keep navigating until we reach the waypoint
            while distance > self.config["waypoint_radius"]:
                # Check if GPS data is stale
                if time.time() - self.state.last_gps_update > MAX_GPS_AGE:
                    logger.warning("GPS data is stale, stopping navigation")
                    self.motors.stop()
                    time.sleep(1)
                    continue

                # Check for obstacles
                if self._handle_obstacles():
                    time.sleep(0.5)  # Short delay after obstacle handling
                    continue

                # Calculate angle difference between current heading and target bearing
                angle_diff = (target_bearing - self.state.heading + 360) % 360
                if angle_diff > 180:
                    angle_diff -= 360

                logger.debug(
                    f"Current heading: {self.state.heading:.1f}°, Target: {target_bearing:.1f}°, Diff: {angle_diff:.1f}°")

                # Adjust direction based on angle difference
                if abs(angle_diff) > 20:
                    # Need to turn significantly
                    self.motors.stop()

                    if angle_diff > 0:
                        logger.debug("Turning right")
                        self.motors.turn_right()
                    else:
                        logger.debug("Turning left")
                        self.motors.turn_left()

                    # Wait for turn to have an effect
                    time.sleep(0.3)
                    self.motors.stop()
                    time.sleep(0.2)  # Short pause to stabilize heading reading

                elif abs(angle_diff) > 5:
                    # Minor direction adjustment while moving
                    speed = self._adjust_speed_for_turn(angle_diff)

                    if angle_diff > 0:
                        logger.debug(f"Moving forward with right adjustment, speed: {speed}")
                        self.motors.turn_right(radius=100)  # Gentle right turn
                    else:
                        logger.debug(f"Moving forward with left adjustment, speed: {speed}")
                        self.motors.turn_left(radius=100)  # Gentle left turn

                    time.sleep(0.2)
                    self.motors.move_forward(speed)

                else:
                    # Heading is good, move forward
                    speed = self._adjust_speed_for_turn(angle_diff)
                    logger.debug(f"Moving forward, speed: {speed}")
                    self.motors.move_forward(speed)

                # Update distance to waypoint
                distance = haversine_distance(
                    self.state.lat, self.state.lon,
                    waypoint[0], waypoint[1]
                )
                target_bearing = calculate_bearing(
                    self.state.lat, self.state.lon,
                    waypoint[0], waypoint[1]
                )

                # Small delay to prevent tight loop
                time.sleep(0.2)

            # We've reached the waypoint
            logger.info(f"Reached waypoint {waypoint}")
            self.motors.stop()
            return True

        def navigate_route(self, destination: Union[str, Tuple[float, float]]) -> bool:
            """Navigate to a destination using waypoints from Google Maps API"""
            # Get current position
            current_location = (self.state.lat, self.state.lon)

            # Check if we have a valid GPS position
            if current_location[0] == 0 and current_location[1] == 0:
                logger.error("Cannot start navigation: invalid GPS position")
                return False

            # Fetch waypoints
            logger.info(f"Planning route from {current_location} to {destination}")
            self.waypoints = self.get_waypoints(current_location, destination)

            if not self.waypoints:
                logger.error("Failed to get waypoints for route")
                return False

            logger.info(f"Route planned with {len(self.waypoints)} waypoints")

            # Begin navigation
            self.state.navigation_active = True
            self.state.current_waypoint_index = 0
            self.state.total_waypoints = len(self.waypoints)

            try:
                for i, waypoint in enumerate(self.waypoints):
                    logger.info(f"Navigating to waypoint {i + 1}/{len(self.waypoints)}")
                    self.state.current_waypoint_index = i

                    # Navigate to this waypoint
                    success = self.navigate_to_waypoint(waypoint)
                    if not success:
                        logger.warning(f"Failed to reach waypoint {i + 1}")
                        # Continue to next waypoint anyway

                logger.info("Destination reached!")
                self.state.destination_reached = True
                self.state.navigation_active = False
                return True

            except KeyboardInterrupt:
                logger.info("Navigation interrupted")
                self.motors.stop()
                self.state.navigation_active = False
                return False

            except Exception as e:
                logger.error(f"Navigation error: {e}")
                self.motors.stop()
                self.state.navigation_active = False
                return False

        def shutdown(self):
            """Cleanly shut down all system components"""
            logger.info("Shutting down navigation system")
            self.running = False
            self.motors.stop()

            # Wait for threads to terminate
            self.gps_thread.join(timeout=1)
            self.sensor_thread.join(timeout=1)

            logger.info("Navigation system shutdown complete")

    # Utility functions
    def haversine_distance(lat1, lon1, lat2, lon2):
        """Returns distance in meters between two lat/lon pairs"""
        R = 6371000  # Earth radius in meters
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def calculate_bearing(lat1, lon1, lat2, lon2):
        """Calculate angle in degrees between two lat/lon points (0° = North, 90° = East)"""
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_lambda = math.radians(lon2 - lon1)

        y = math.sin(delta_lambda) * math.cos(phi2)
        x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)

        bearing = math.degrees(math.atan2(y, x))
        return (bearing + 360) % 360

    class CampusTourRobot:
        """Main class for the Campus Tour Robot with voice interface and tour guide features"""

        def __init__(self, api_key, audio_enabled=True):
            self.api_key = api_key
            self.audio_enabled = audio_enabled
            self.navigation = NavigationSystem(api_key)
            self.campus_landmarks = {}
            self.current_tour = []
            self.tour_index = 0
            self.load_landmarks()

        def load_landmarks(self):
            """Load campus landmark information from file"""
            try:
                if os.path.exists("campus_landmarks.json"):
                    with open("campus_landmarks.json", 'r') as f:
                        self.campus_landmarks = json.load(f)
                    logger.info(f"Loaded {len(self.campus_landmarks)} campus landmarks")
                else:
                    logger.warning("No campus landmarks file found. Creating empty file.")
                    self.campus_landmarks = {}
                    with open("campus_landmarks.json", 'w') as f:
                        json.dump(self.campus_landmarks, f, indent=4)
            except Exception as e:
                logger.error(f"Failed to load landmarks: {e}")
                self.campus_landmarks = {}

        def add_landmark(self, name, lat, lon, description):
            """Add a new campus landmark"""
            self.campus_landmarks[name] = {
                "coordinates": (lat, lon),
                "description": description
            }
            try:
                with open("campus_landmarks.json", 'w') as f:
                    json.dump(self.campus_landmarks, f, indent=4)
                logger.info(f"Added landmark: {name}")
            except Exception as e:
                logger.error(f"Failed to save landmark: {e}")

        def text_to_speech(self, text):
            """Convert text to speech if audio is enabled"""
            if not self.audio_enabled:
                return

            try:
                # This is a placeholder for actual TTS implementation
                # You could use pyttsx3, gTTS, or other TTS libraries
                logger.info(f"TTS: {text}")
                os.system(f'echo "{text}" | festival --tts')
            except Exception as e:
                logger.error(f"TTS error: {e}")

        def announce_arrival(self, landmark_name):
            """Announce arrival at a landmark and provide information"""
            if landmark_name in self.campus_landmarks:
                landmark = self.campus_landmarks[landmark_name]
                announcement = f"We have arrived at {landmark_name}. {landmark['description']}"
                print(announcement)
                self.text_to_speech(announcement)
            else:
                announcement = f"We have arrived at {landmark_name}."
                print(announcement)
                self.text_to_speech(announcement)

        def create_tour(self, landmark_names):
            """Create a tour visiting multiple landmarks in sequence"""
            self.current_tour = []

            for name in landmark_names:
                if name in self.campus_landmarks:
                    self.current_tour.append({
                        "name": name,
                        "coordinates": self.campus_landmarks[name]["coordinates"]
                    })
                else:
                    logger.warning(f"Landmark not found: {name}")

            logger.info(f"Created tour with {len(self.current_tour)} landmarks")
            return len(self.current_tour) > 0

        def start_tour(self):
            """Start a campus tour visiting multiple landmarks"""
            if not self.current_tour:
                logger.error("No tour defined")
                self.text_to_speech("No tour has been defined yet.")
                return False

            self.tour_index = 0
            announcement = f"Starting campus tour with {len(self.current_tour)} stops."
            print(announcement)
            self.text_to_speech(announcement)

            try:
                while self.tour_index < len(self.current_tour):
                    current_stop = self.current_tour[self.tour_index]

                    # Announce next destination
                    announcement = f"Next, we will visit {current_stop['name']}."
                    print(announcement)
                    self.text_to_speech(announcement)

                    # Navigate to the landmark
                    success = self.navigation.navigate_route(current_stop["coordinates"])

                    if success:
                        # Announce arrival
                        self.announce_arrival(current_stop["name"])

                        # Wait at the landmark for a bit
                        time.sleep(5)

                        self.tour_index += 1
                    else:
                        announcement = "I'm having trouble reaching this location. Let's try the next stop."
                        print(announcement)
                        self.text_to_speech(announcement)
                        self.tour_index += 1

                # Tour complete
                announcement = "The campus tour is now complete. Thank you for joining!"
                print(announcement)
                self.text_to_speech(announcement)
                return True

            except KeyboardInterrupt:
                announcement = "Tour interrupted."
                print(announcement)
                self.text_to_speech(announcement)
                return False

            except Exception as e:
                logger.error(f"Tour error: {e}")
                announcement = "I've encountered a problem with the tour. Let's stop here."
                print(announcement)
                self.text_to_speech(announcement)
                return False

        def navigate_to_landmark(self, landmark_name):
            """Navigate to a specific landmark by name"""
            if landmark_name in self.campus_landmarks:
                coordinates = self.campus_landmarks[landmark_name]["coordinates"]

                announcement = f"Navigating to {landmark_name}."
                print(announcement)
                self.text_to_speech(announcement)

                success = self.navigation.navigate_route(coordinates)

                if success:
                    self.announce_arrival(landmark_name)
                    return True
                else:
                    announcement = "I'm having trouble reaching this location."
                    print(announcement)
                    self.text_to_speech(announcement)
                    return False
            else:
                announcement = f"I don't have information about {landmark_name}."
                print(announcement)
                self.text_to_speech(announcement)
                return False

        def navigate_to_coordinates(self, lat, lon, name=None):
            """Navigate to specific coordinates"""
            destination_name = name if name else f"coordinates ({lat:.6f}, {lon:.6f})"

            announcement = f"Navigating to {destination_name}."
            print(announcement)
            self.text_to_speech(announcement)

            success = self.navigation.navigate_route((lat, lon))

            if success:
                announcement = f"We have arrived at {destination_name}."
                print(announcement)
                self.text_to_speech(announcement)
                return True
            else:
                announcement = "I'm having trouble reaching this location."
                print(announcement)
                self.text_to_speech(announcement)
                return False

        def navigate_to_address(self, address):
            """Navigate to an address using geocoding"""
            announcement = f"Finding location for {address}."
            print(announcement)
            self.text_to_speech(announcement)

            # Geocode the address
            coordinates = self.navigation.geocode_address(address)

            if not coordinates:
                announcement = f"I couldn't find the location for {address}."
                print(announcement)
                self.text_to_speech(announcement)
                return False

            # Navigate to the coordinates
            return self.navigate_to_coordinates(coordinates[0], coordinates[1], address)

        def get_current_location(self):
            """Get the current GPS location of the robot"""
            lat = self.navigation.state.lat
            lon = self.navigation.state.lon

            # Check if position is valid
            if lat == 0 and lon == 0:
                logger.warning("Invalid GPS position")
                return None

            return (lat, lon)

        def shutdown(self):
            """Shutdown the robot system"""
            announcement = "Shutting down tour guide system."
            print(announcement)
            self.text_to_speech(announcement)
            self.navigation.shutdown()

    # Main function to run the tour robot
    def main():
        # Get Google Maps API key (replace with your actual key)
        api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "YOUR_API_KEY_HERE")

        if not api_key:
            logger.warning("Using placeholder API key. Set the GOOGLE_MAPS_API_KEY environment variable.")

        # Create the campus tour robot
        robot = CampusTourRobot(api_key)

        try:
            # Interactive mode or predefined destination
            print("Campus Tour Robot Navigation System")
            print("==================================")

            while True:
                print("\nOptions:")
                print("1. Navigate to campus landmark")
                print("2. Navigate to coordinates")
                print("3. Navigate to address")
                print("4. Start campus tour")
                print("5. Add new landmark")
                print("6. Show current location")
                print("7. Exit")

                choice = input("\nEnter your choice (1-7): ")

                if choice == '1':
                    # Show available landmarks
                    print("\nAvailable landmarks:")
                    for i, name in enumerate(robot.campus_landmarks.keys()):
                        print(f"{i + 1}. {name}")

                    if not robot.campus_landmarks:
                        print("No landmarks defined yet.")
                        continue

                    landmark_index = int(input("\nEnter landmark number: ")) - 1
                    landmark_names = list(robot.campus_landmarks.keys())

                    if 0 <= landmark_index < len(landmark_names):
                        robot.navigate_to_landmark(landmark_names[landmark_index])
                    else:
                        print("Invalid selection.")

                elif choice == '2':
                    try:
                        lat = float(input("Enter latitude: "))
                        lon = float(input("Enter longitude: "))
                        name = input("Enter location name (optional): ")
                        robot.navigate_to_coordinates(lat, lon, name if name else None)
                    except ValueError:
                        print("Invalid coordinates. Please enter valid numbers.")

                elif choice == '3':
                    address = input("Enter address: ")
                    robot.navigate_to_address(address)

                elif choice == '4':
                    print("\nAvailable landmarks:")
                    for i, name in enumerate(robot.campus_landmarks.keys()):
                        print(f"{i + 1}. {name}")

                    if not robot.campus_landmarks:
                        print("No landmarks defined yet.")
                        continue

                    selections = input("\nEnter landmark numbers separated by commas: ")
                    try:
                        indices = [int(i.strip()) - 1 for i in selections.split(',')]
                        landmark_names = list(robot.campus_landmarks.keys())
                        tour_stops = [landmark_names[i] for i in indices if 0 <= i < len(landmark_names)]

                        if tour_stops:
                            robot.create_tour(tour_stops)
                            robot.start_tour()
                        else:
                            print("No valid landmarks selected.")
                    except ValueError:
                        print("Invalid input. Please enter numbers separated by commas.")

                elif choice == '5':
                    name = input("Enter landmark name: ")
                    description = input("Enter landmark description: ")

                    # Get coordinates (either directly or current location)
                    coord_choice = input("Use current location (C) or enter coordinates (E)? ").upper()

                    if coord_choice == 'C':
                        current_loc = robot.get_current_location()
                        if current_loc:
                            lat, lon = current_loc
                            robot.add_landmark(name, lat, lon, description)
                            print(f"Added landmark '{name}' at current location ({lat}, {lon})")
                        else:
                            print("Couldn't get current location. Try again or enter coordinates manually.")
                    else:
                        try:
                            lat = float(input("Enter latitude: "))
                            lon = float(input("Enter longitude: "))
                            robot.add_landmark(name, lat, lon, description)
                            print(f"Added landmark '{name}' at ({lat}, {lon})")
                        except ValueError:
                            print("Invalid coordinates. Landmark not added.")

                elif choice == '6':
                    current_loc = robot.get_current_location()
                    if current_loc:
                        print(f"Current location: {current_loc[0]}, {current_loc[1]}")
                    else:
                        print("Couldn't get current location.")

                elif choice == '7':
                    print("Shutting down...")
                    robot.shutdown()
                    break

                else:
                    print("Invalid choice. Please try again.")



        except KeyboardInterrupt:
            print("\nExiting...")
            robot.shutdown()
        except Exception as e:
            logger.error(f"Error in main program: {e}")
            robot.shutdown()

    if __name__ == "__main__":
        main()

    return f"you have arrived at {destination}."
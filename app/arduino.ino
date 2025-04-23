#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_HMC5883_U.h>  // For magnetometer
#include <NewPing.h>             // For ultrasonic sensors

// Motor pins
#define LEFT_MOTOR_FWD 5
#define LEFT_MOTOR_BWD 6
#define RIGHT_MOTOR_FWD 9
#define RIGHT_MOTOR_BWD 10

// Ultrasonic sensor pins
#define TRIG_PIN_FRONT 2
#define ECHO_PIN_FRONT 3
#define TRIG_PIN_LEFT 4
#define ECHO_PIN_LEFT 7
#define TRIG_PIN_RIGHT 8
#define ECHO_PIN_RIGHT 12

#define MAX_DISTANCE 300  // Maximum distance for ultrasonic sensors (cm)

// Create ultrasonic sensor objects
NewPing sonarFront(TRIG_PIN_FRONT, ECHO_PIN_FRONT, MAX_DISTANCE);
NewPing sonarLeft(TRIG_PIN_LEFT, ECHO_PIN_LEFT, MAX_DISTANCE);
NewPing sonarRight(TRIG_PIN_RIGHT, ECHO_PIN_RIGHT, MAX_DISTANCE);

// Create magnetometer sensor object
Adafruit_HMC5883_Unified mag = Adafruit_HMC5883_Unified(12345);
bool magAvailable = false;

// Motor control variables
int leftSpeed = 0;
int rightSpeed = 0;

void setup() {
  // Initialize serial communication
  Serial.begin(115200);

  // Initialize motor pins
  pinMode(LEFT_MOTOR_FWD, OUTPUT);
  pinMode(LEFT_MOTOR_BWD, OUTPUT);
  pinMode(RIGHT_MOTOR_FWD, OUTPUT);
  pinMode(RIGHT_MOTOR_BWD, OUTPUT);

  // Initialize magnetometer
  magAvailable = mag.begin();
  if (!magAvailable) {
    Serial.println("Could not find a valid HMC5883 sensor!");
  }

  Serial.println("Robot controller initialized");
}

void loop() {
  // Check if there's a command from Raspberry Pi
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    processCommand(command);
  }
}

void processCommand(String command) {
  if (command.startsWith("S")) {
    sendSensorData();  // Sensor readings
  }
  else if (command.startsWith("F")) {
    int speed = 100;
    if (command.indexOf(':') != -1) {
      speed = command.substring(command.indexOf(':') + 1).toInt();
    }
    moveForward(speed);
    Serial.println("Moving forward");
  }
  else if (command.startsWith("B")) {
    int speed = 100;
    if (command.indexOf(':') != -1) {
      speed = command.substring(command.indexOf(':') + 1).toInt();
    }
    moveBackward(speed);
    Serial.println("Moving backward");
  }
  else if (command.startsWith("L")) {
    int radius = 0;
    if (command.indexOf(':') != -1) {
      radius = command.substring(command.indexOf(':') + 1).toInt();
    }
    turnLeft(radius);
    Serial.println("Turning left");
  }
  else if (command.startsWith("R")) {
    int radius = 0;
    if (command.indexOf(':') != -1) {
      radius = command.substring(command.indexOf(':') + 1).toInt();
    }
    turnRight(radius);
    Serial.println("Turning right");
  }
  else if (command.startsWith("X")) {
    stopMotors();
    Serial.println("Stopped");
  }
}

void sendSensorData() {
  StaticJsonDocument<256> doc;

  // Read ultrasonic sensors
  int frontDistance = sonarFront.ping_cm();
  int leftDistance = sonarLeft.ping_cm();
  int rightDistance = sonarRight.ping_cm();

  if (frontDistance == 0) frontDistance = MAX_DISTANCE;
  if (leftDistance == 0) leftDistance = MAX_DISTANCE;
  if (rightDistance == 0) rightDistance = MAX_DISTANCE;

  // Create ultrasonic JSON
  JsonObject ultrasonic = doc.createNestedObject("ultrasonic");
  ultrasonic["front"] = frontDistance;
  ultrasonic["left"] = leftDistance;
  ultrasonic["right"] = rightDistance;

  // Magnetometer data
  if (magAvailable) {
    sensors_event_t event;
    mag.getEvent(&event);

    float heading = atan2(event.magnetic.y, event.magnetic.x);
    float declination = 0.23;
    heading += declination;

    if (heading < 0) heading += 2 * PI;
    if (heading > 2 * PI) heading -= 2 * PI;

    float headingDegrees = heading * 180 / PI;
    doc["magnetometer"] = headingDegrees;
  } else {
    doc["magnetometer"] = -1.0;
  }

  serializeJson(doc, Serial);
  Serial.println();
}

void moveForward(int speed) {
  analogWrite(LEFT_MOTOR_FWD, speed);
  analogWrite(LEFT_MOTOR_BWD, 0);
  analogWrite(RIGHT_MOTOR_FWD, speed);
  analogWrite(RIGHT_MOTOR_BWD, 0);
}

void moveBackward(int speed) {
  analogWrite(LEFT_MOTOR_FWD, 0);
  analogWrite(LEFT_MOTOR_BWD, speed);
  analogWrite(RIGHT_MOTOR_FWD, 0);
  analogWrite(RIGHT_MOTOR_BWD, speed);
}

void turnLeft(int radius) {
  if (radius == 0) {
    analogWrite(LEFT_MOTOR_FWD, 0);
    analogWrite(LEFT_MOTOR_BWD, 100);
    analogWrite(RIGHT_MOTOR_FWD, 100);
    analogWrite(RIGHT_MOTOR_BWD, 0);
  } else {
    int innerWheelSpeed = 50;
    int outerWheelSpeed = 100;
    analogWrite(LEFT_MOTOR_FWD, innerWheelSpeed);
    analogWrite(LEFT_MOTOR_BWD, 0);
    analogWrite(RIGHT_MOTOR_FWD, outerWheelSpeed);
    analogWrite(RIGHT_MOTOR_BWD, 0);
  }
}

void turnRight(int radius) {
  if (radius == 0) {
    analogWrite(LEFT_MOTOR_FWD, 100);
    analogWrite(LEFT_MOTOR_BWD, 0);
    analogWrite(RIGHT_MOTOR_FWD, 0);
    analogWrite(RIGHT_MOTOR_BWD, 100);
  } else {
    int innerWheelSpeed = 50;
    int outerWheelSpeed = 100;
    analogWrite(LEFT_MOTOR_FWD, outerWheelSpeed);
    analogWrite(LEFT_MOTOR_BWD, 0);
    analogWrite(RIGHT_MOTOR_FWD, innerWheelSpeed);
    analogWrite(RIGHT_MOTOR_BWD, 0);
  }
}

void stopMotors() {
  analogWrite(LEFT_MOTOR_FWD, 0);
  analogWrite(LEFT_MOTOR_BWD, 0);
  analogWrite(RIGHT_MOTOR_FWD, 0);
  analogWrite(RIGHT_MOTOR_BWD, 0);
}

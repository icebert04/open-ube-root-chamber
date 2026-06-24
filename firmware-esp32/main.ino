/**
 * open-root-chamber — firmware-esp32/main.ino
 *
 * Controls ultrasonic misters and heat mats for ube sett sprouting.
 * Reads DHT22 sensor data and runs a PID loop to maintain:
 *   - Humidity: 85–90%
 *   - Temperature: 28–30°C
 *
 * Board: ESP32 (tested on ESP32-WROOM-32)
 * Libraries needed (install via Arduino Library Manager):
 *   - DHT sensor library by Adafruit
 *   - Adafruit Unified Sensor
 *   - PID_v1 by Brett Beauregard
 */

#include "DHT.h"
#include "pid_controller.h"

// ─── Pin Definitions ─────────────────────────────────────────────────────────
#define DHT_PIN        4   // GPIO4  → DHT22 data pin
#define DHT_TYPE       DHT22
#define MISTER_PIN     16  // GPIO16 → Relay for ultrasonic mister
#define HEAT_MAT_PIN   17  // GPIO17 → Relay for heat mat
#define STATUS_LED_PIN 2   // GPIO2  → Onboard LED (heartbeat)

// ─── Target Setpoints ────────────────────────────────────────────────────────
const float HUMIDITY_TARGET    = 87.5; // midpoint of 85–90%
const float TEMPERATURE_TARGET = 29.0; // midpoint of 28–30°C

// ─── Timing ──────────────────────────────────────────────────────────────────
const unsigned long SENSOR_INTERVAL_MS = 2000;  // read sensor every 2s
const unsigned long SERIAL_LOG_MS      = 5000;  // log to Serial every 5s

// ─── Globals ─────────────────────────────────────────────────────────────────
DHT dht(DHT_PIN, DHT_TYPE);
PIDController humidityPID(HUMIDITY_TARGET);
PIDController tempPID(TEMPERATURE_TARGET);

unsigned long lastSensorRead = 0;
unsigned long lastSerialLog  = 0;

float currentHumidity    = 0.0;
float currentTemperature = 0.0;

// ─── Setup ───────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  dht.begin();

  pinMode(MISTER_PIN,     OUTPUT);
  pinMode(HEAT_MAT_PIN,   OUTPUT);
  pinMode(STATUS_LED_PIN, OUTPUT);

  // Safe default: everything OFF on boot
  digitalWrite(MISTER_PIN,     LOW);
  digitalWrite(HEAT_MAT_PIN,   LOW);

  Serial.println("[open-root-chamber] Firmware started.");
}

// ─── Main Loop ───────────────────────────────────────────────────────────────
void loop() {
  unsigned long now = esp_timer_get_time();

  // Heartbeat blink
  digitalWrite(STATUS_LED_PIN, (now / 500) % 2);

  // Read sensor on interval (DHT22 needs ≥2s between reads)
  if (now - lastSensorRead >= SENSOR_INTERVAL_MS) {
    lastSensorRead = now;
    readSensors();
    applyControl();
  }

  // Log to Serial on interval
  if (now - lastSerialLog >= SERIAL_LOG_MS) {
    lastSerialLog = now;
    logStatus();
  }
}

// ─── Sensor Read ─────────────────────────────────────────────────────────────
void readSensors() {
  float h = dht.readHumidity();
  float t = dht.readTemperature(); // Celsius

  // DHT22 returns NaN on read failure — keep last known good value
  if (!isnan(h)) currentHumidity    = h;
  if (!isnan(t)) currentTemperature = t;
}

// ─── PID Control → Actuators ─────────────────────────────────────────────────
void applyControl() {
  // Humidity: mister ON if below target band
  bool misterOn = humidityPID.needsActuation(currentHumidity, /*invertIfBelow=*/true);
  digitalWrite(MISTER_PIN, misterOn ? HIGH : LOW);

  // Temperature: heat mat ON if below target band
  bool heatOn = tempPID.needsActuation(currentTemperature, /*invertIfBelow=*/true);
  digitalWrite(HEAT_MAT_PIN, heatOn ? HIGH : LOW);
}

// ─── Serial Logging ──────────────────────────────────────────────────────────
void logStatus() {
  Serial.print("[LOG] Humidity: ");    Serial.print(currentHumidity);
  Serial.print("% | Temperature: ");  Serial.print(currentTemperature);
  Serial.print("°C | Mister: ");      Serial.print(digitalRead(MISTER_PIN) ? "ON" : "OFF");
  Serial.print(" | Heat Mat: ");      Serial.println(digitalRead(HEAT_MAT_PIN) ? "ON" : "OFF");
}

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
#include "config.h"      

// ─── Pin Definitions ─────────────────────────────────────────────────────────
#define DHT_PIN        4   // GPIO4  → DHT22 data pin
#define DHT_TYPE       DHT22
#define MISTER_PIN     16  // GPIO16 → Relay for ultrasonic mister
#define HEAT_MAT_PIN   17  // GPIO17 → Relay for heat mat
#define STATUS_LED_PIN 2   // GPIO2  → Onboard LED (heartbeat)


// ─── Globals ─────────────────────────────────────────────────────────────────
DHT dht(DHT_PIN, DHT_TYPE);
PIDController humidityPID(HUMIDITY_TARGET);
PIDController tempPID(TEMPERATURE_TARGET);

unsigned long lastSensorRead = 0;
unsigned long lastSerialLog  = 0;

float currentHumidity    = 0.0;
float currentTemperature = 0.0;

static bool prevMister = false;
static bool prevHeat   = false;
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

  Serial.print("[CONFIG] HUMIDITY_TARGET=");    Serial.println(HUMIDITY_TARGET);
  Serial.print("[CONFIG] TEMPERATURE_TARGET="); Serial.println(TEMPERATURE_TARGET);
  Serial.print("[CONFIG] DEADBAND=");           Serial.println(DEADBAND);
}

// ─── Main Loop ───────────────────────────────────────────────────────────────
void loop() {
  unsigned long now = millis();

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
  bool misterOn = humidityPID.needsActuation(currentHumidity,    true);
  bool heatOn   = tempPID.needsActuation(currentTemperature, true);

  digitalWrite(MISTER_PIN,   misterOn ? HIGH : LOW);
  digitalWrite(HEAT_MAT_PIN, heatOn   ? HIGH : LOW);

  if (misterOn != prevMister) {
    Serial.print("[MIST] "); Serial.print(misterOn ? "ON" : "OFF");
    Serial.print("  hum="); Serial.print(currentHumidity);
    Serial.print("% target="); Serial.println(HUMIDITY_TARGET);
    prevMister = misterOn;
  }
  if (heatOn != prevHeat) {
    Serial.print("[HEAT] "); Serial.print(heatOn ? "ON" : "OFF");
    Serial.print("  temp="); Serial.print(currentTemperature);
    Serial.print("C target="); Serial.println(TEMPERATURE_TARGET);
    prevHeat = heatOn;
  }
}

// ─── Serial Logging ──────────────────────────────────────────────────────────
void logStatus() {
  Serial.print("[LOG] Humidity: ");    Serial.print(currentHumidity);
  Serial.print("% | Temperature: ");  Serial.print(currentTemperature);
  Serial.print("°C | Mister: ");      Serial.print(digitalRead(MISTER_PIN) ? "ON" : "OFF");
  Serial.print(" | Heat Mat: ");      Serial.println(digitalRead(HEAT_MAT_PIN) ? "ON" : "OFF");
}

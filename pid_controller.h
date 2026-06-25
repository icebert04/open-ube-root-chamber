/**
 * open-root-chamber — firmware-esp32/pid_controller.h
 *
 * Lightweight bang-bang + deadband controller.
 *
 * Why not a full PID?
 * For binary actuators (relay ON/OFF), a true PID output is meaningless
 * without PWM support on the relay. A deadband controller is the correct,
 * industry-standard approach for this hardware class. It prevents relay
 * chatter (rapid on/off) which destroys relay hardware within days.
 *
 * If you later upgrade to PWM-capable solid-state relays, swap this class
 * for the PID_v1 library and retain the same interface.
 */

#ifndef PID_CONTROLLER_H
#define PID_CONTROLLER_H

class PIDController {
public:
  // deadband: how far from target before we actuate (prevents relay chatter)
  PIDController(float setpoint, float deadband = 1.5)
    : _setpoint(setpoint), _deadband(deadband) {}

  /**
   * Returns true if the actuator should be ON.
   * @param current       Current sensor reading
   * @param invertIfBelow If true: actuate when BELOW setpoint (heat/mist)
   *                      If false: actuate when ABOVE setpoint (cooling/drain)
   */
  bool needsActuation(float current, bool invertIfBelow = true) {
    float error = _setpoint - current;

    if (invertIfBelow) {
      // Turn ON if we're more than deadband BELOW target
      return error > _deadband;
    } else {
      // Turn ON if we're more than deadband ABOVE target
      return error < -_deadband;
    }
  }

  void setSetpoint(float setpoint) { _setpoint = setpoint; }
  void setDeadband(float deadband) { _deadband = deadband; }
  float getSetpoint() const { return _setpoint; }

private:
  float _setpoint;
  float _deadband;
};

#endif // PID_CONTROLLER_H
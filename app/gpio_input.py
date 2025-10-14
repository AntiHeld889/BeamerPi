from __future__ import annotations

import atexit
import threading
from typing import Callable, Optional


try:  # pragma: no cover - optional dependency on Raspberry Pi
    import RPi.GPIO as GPIO
except Exception:  # pragma: no cover - gracefully handle missing GPIO library
    GPIO = None  # type: ignore


class GPIOTriggerInput:
    """Configure a GPIO pin as trigger input and invoke a callback on rising edges."""

    def __init__(self, callback: Callable[[], bool]) -> None:
        self._callback = callback
        self._pin: Optional[int] = None
        self._lock = threading.Lock()
        self._available = GPIO is not None
        self._active_high = True
        if self._available:
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            atexit.register(self.close)
        else:
            print("RPi.GPIO konnte nicht geladen werden – GPIO-Trigger ist deaktiviert.")

    def configure(self, pin: Optional[int], active_high: bool = True) -> None:
        """Configure the trigger pin. Passing ``None`` disables the trigger."""

        trigger_when_configured = False
        with self._lock:
            if pin == self._pin and active_high == self._active_high:
                return
            self._cleanup_locked()
            self._active_high = active_high
            if not self._available or pin is None:
                self._pin = None
                return
            try:
                pull = GPIO.PUD_DOWN if active_high else GPIO.PUD_UP
                GPIO.setup(pin, GPIO.IN, pull_up_down=pull)
                GPIO.add_event_detect(pin, GPIO.BOTH, callback=self._handle_event, bouncetime=200)
                self._pin = pin
                level = "HIGH" if active_high else "LOW"
                print(f"GPIO-Trigger auf Pin {pin} aktiviert (aktiv bei {level}).")
                desired_state = GPIO.HIGH if active_high else GPIO.LOW
                if GPIO.input(pin) == desired_state:
                    trigger_when_configured = True
            except Exception as exc:
                print(f"GPIO-Pin {pin} konnte nicht konfiguriert werden: {exc}")
                self._pin = None
                return
        if trigger_when_configured and pin is not None:
            # Trigger once if the pin is already active when configuration completes.
            self._handle_event(pin)

    def close(self) -> None:
        with self._lock:
            self._cleanup_locked()
            if self._available:
                try:
                    GPIO.cleanup()
                except Exception:
                    pass
                self._available = False

    # Internal helpers -----------------------------------------------------
    def _cleanup_locked(self) -> None:
        if not self._available or self._pin is None:
            return
        try:
            GPIO.remove_event_detect(self._pin)
        except Exception:
            pass
        try:
            GPIO.cleanup(self._pin)
        except Exception:
            pass
        print(f"GPIO-Trigger auf Pin {self._pin} deaktiviert.")
        self._pin = None

    def _handle_event(self, channel: int) -> None:
        del channel  # unused, but required by GPIO callback signature
        pin = self._pin
        if pin is None:
            return
        if not self._available:
            return
        try:
            desired_state = GPIO.HIGH if self._active_high else GPIO.LOW
            if GPIO.input(pin) == desired_state:
                self._callback()
        except Exception as exc:
            print(f"GPIO-Trigger konnte nicht ausgelöst werden: {exc}")


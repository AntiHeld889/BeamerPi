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

    def configure(self, pin: Optional[int]) -> None:
        """Configure the trigger pin. Passing ``None`` disables the trigger."""

        with self._lock:
            if pin == self._pin:
                return
            self._cleanup_locked()
            if not self._available or pin is None:
                self._pin = None
                return
            try:
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                GPIO.add_event_detect(pin, GPIO.RISING, callback=self._handle_event, bouncetime=200)
                self._pin = pin
                print(f"GPIO-Trigger auf Pin {pin} aktiviert.")
            except Exception as exc:
                print(f"GPIO-Pin {pin} konnte nicht konfiguriert werden: {exc}")
                self._pin = None

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
            if GPIO.input(pin) == GPIO.HIGH:
                self._callback()
        except Exception as exc:
            print(f"GPIO-Trigger konnte nicht ausgelöst werden: {exc}")


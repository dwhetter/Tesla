"""Thin, thread-safe wrapper around the tesla_powerwall library (local gateway API).

The library is async; Flask and APScheduler are not. This module runs one
private asyncio event loop in a background thread and exposes simple blocking
methods: status(), go_off_grid(), go_on_grid().

Set POWERWALL_DEMO=1 to use a simulated Powerwall (no hardware needed).
"""

import asyncio
import os
import random
import threading
import time


class PowerwallError(Exception):
    pass


class RealPowerwall:
    def __init__(self, host, password, email=""):
        from tesla_powerwall import Powerwall  # imported lazily so demo mode works without it

        self._Powerwall = Powerwall
        self.host = host
        self.password = password
        self.email = email
        self._pw = None
        self._lock = threading.Lock()
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, daemon=True).start()

    def _run(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout=60)

    async def _ensure_login(self, force=False):
        if self._pw is None:
            self._pw = self._Powerwall(self.host)
        if force or not self._pw.is_authenticated():
            await self._pw.login(self.password, self.email)

    async def _call(self, fn):
        """Run fn(pw), logging in again once if the session has expired."""
        await self._ensure_login()
        try:
            return await fn(self._pw)
        except Exception:
            # Session may have expired; recreate and retry once.
            try:
                await self._pw.close()
            except Exception:
                pass
            self._pw = None
            await self._ensure_login(force=True)
            return await fn(self._pw)

    def status(self):
        async def get(pw):
            charge = await pw.get_charge()
            grid = await pw.get_grid_status()
            return {"charge": round(float(charge), 1), "grid": grid.name, "grid_raw": grid.value}

        with self._lock:
            try:
                return self._run(self._call(get))
            except Exception as e:
                raise PowerwallError(f"Could not read Powerwall status: {e}") from e

    def _set_mode(self, offgrid):
        from tesla_powerwall import IslandMode

        mode = IslandMode.OFFGRID if offgrid else IslandMode.ONGRID

        async def setm(pw):
            return await pw.set_island_mode(mode)

        with self._lock:
            try:
                self._run(self._call(setm))
            except Exception as e:
                raise PowerwallError(f"Could not change grid mode: {e}") from e

    def go_off_grid(self):
        self._set_mode(True)

    def go_on_grid(self):
        self._set_mode(False)


class DemoPowerwall:
    """Simulated Powerwall: drains while off-grid, charges while on-grid."""

    def __init__(self, start_charge=80.0, rate_per_min=0.5):
        self.charge = start_charge
        self.islanded = False
        self.rate = rate_per_min
        self._t = time.time()
        self._lock = threading.Lock()

    def _tick(self):
        now = time.time()
        minutes = (now - self._t) / 60
        self._t = now
        delta = self.rate * minutes
        self.charge += -delta if self.islanded else delta
        self.charge = max(0.0, min(100.0, self.charge))

    def status(self):
        with self._lock:
            self._tick()
            grid = "ISLANDED" if self.islanded else "CONNECTED"
            raw = "SystemIslandedActive" if self.islanded else "SystemGridConnected"
            return {"charge": round(self.charge + random.uniform(-0.05, 0.05), 1), "grid": grid, "grid_raw": raw}

    def go_off_grid(self):
        with self._lock:
            self._tick()
            self.islanded = True

    def go_on_grid(self):
        with self._lock:
            self._tick()
            self.islanded = False


def make_client():
    if os.environ.get("POWERWALL_DEMO", "").strip() in ("1", "true", "yes"):
        return DemoPowerwall()
    host = os.environ.get("POWERWALL_HOST")
    password = os.environ.get("POWERWALL_PASSWORD")
    if not host or not password:
        raise SystemExit(
            "Set POWERWALL_HOST and POWERWALL_PASSWORD in your .env file "
            "(or set POWERWALL_DEMO=1 to try the app without a Powerwall)."
        )
    return RealPowerwall(host, password, os.environ.get("POWERWALL_EMAIL", ""))

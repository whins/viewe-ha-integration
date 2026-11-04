"""Receipt-based ESPHome delivery; MQTT remains in hub.py."""

from copy import deepcopy
import asyncio
import logging
from time import monotonic

from .native import discover, encode_profile

_LOGGER = logging.getLogger(__name__)


class NativeHubMixin:
    def _native_init(self):
        self.native_nodes = {}
        self.native_detected = False
        self.native_pending = {}

    def _is_native(self, panel_id):
        return self.data["panels"].get(panel_id, {}).get("transport") == "esphome"

    async def _native_call(self, panel_id, action, data=None):
        node = self.native_nodes.get(panel_id)
        if not node or not node["available"]:
            raise ValueError("ESPHome panel is offline")
        async with asyncio.timeout(10):
            await self.hass.services.async_call("esphome", node["actions"][action], data or {}, blocking=True)

    async def _native_poll(self):
        if not hasattr(self.hass, "config_entries"):
            return
        nodes = discover(self.hass)
        async with self.lock:
            self.native_detected = bool(nodes)
            nodes = {key: node for key, node in nodes.items() if key not in self.dismissed_panels}
            self.native_nodes = nodes
            updated = deepcopy(self.data)
            for panel_id, node in nodes.items():
                panel = updated["panels"].setdefault(panel_id, {"id": panel_id, "profile_id": None})
                panel.update(transport="esphome", name=node["name"], device_id=node["device_id"], node_name=node["node_name"])
            if updated != self.data:
                await self._persist(updated)
            for panel_id in self.data["panels"]:
                if self._is_native(panel_id) and not nodes.get(panel_id, {}).get("available"):
                    self.online.discard(panel_id)
                    self.native_pending.pop(panel_id, None)
                    self.results[panel_id] = "offline"
        for panel_id, node in nodes.items():
            if node["available"]:
                try:
                    await self._native_call(panel_id, "viewe_profile_status")
                except Exception:
                    if panel_id not in self.data["panels"]:
                        continue
                    self.online.discard(panel_id)
                    self.results[panel_id] = "offline"
                    _LOGGER.debug("ESPHome status probe failed for %s", panel_id, exc_info=True)

    async def _native_deliver(self, panel_id):
        panel = self.data["panels"][panel_id]
        if panel_id not in self.online or not self.native_nodes.get(panel_id, {}).get("available"):
            self.results[panel_id] = "offline"
            return "offline"
        if panel_id in self.native_pending:
            return self.results.get(panel_id, "pending")
        profile = self.data["applied"].get(panel.get("profile_id"))
        data = {}
        if panel.get("reset_requested"):
            action, operation = "viewe_reset_profile", "reset"
        elif panel.get("resume_requested"):
            action, operation = "viewe_allow_remote_profiles", "allow"
        elif panel.get("remote_blocked"):
            self.results[panel_id] = "local_override"
            return "local_override"
        elif profile:
            action, operation = "viewe_apply_profile", "apply"
            try:
                data["payload"] = encode_profile(profile)
                for page in profile["pages"]:
                    if page["visible"] and not page.get("demo", False) and page["template"] == "bc250" and self.hass.states.get(page.get("guard_script", "script.viewe_guarded_start")) is None:
                        raise ValueError("Install or select the BC-250 guard script first")
            except (ValueError, KeyError, TypeError) as err:
                self.results[panel_id] = "incompatible"
                self.native_errors[panel_id] = str(err)
                return "incompatible"
        else:
            self.results[panel_id] = "unassigned"
            return "unassigned"
        self.results[panel_id] = "pending"
        self.pending_since[panel_id] = monotonic()
        self.native_errors.pop(panel_id, None)
        self.native_pending[panel_id] = (operation, profile["id"] if profile else None, profile["revision"] if profile else None)
        try:
            await self._native_call(panel_id, action, data)
        except Exception:
            self.native_pending.pop(panel_id, None)
            self.online.discard(panel_id)
            self.results[panel_id] = "offline"
            _LOGGER.exception("ESPHome profile delivery failed for %s", panel_id)
        return self.results[panel_id]

    async def _native_event(self, event):
        data = event.data
        if not isinstance(data, dict):
            return
        panel_id = next((key for key, node in self.native_nodes.items() if
                         node["available"] and node["device_id"] == data.get("device_id") and node["node_name"] == data.get("panel")), None)
        if panel_id is None or data.get("event") not in {"profile_status", "profile_applied", "profile_rejected", "profile_reset", "remote_profiles_allowed"}:
            return
        try:
            revision = int(data.get("revision", ""))
        except (TypeError, ValueError):
            return
        async with self.lock:
            if panel_id not in self.data["panels"]:
                return
            newly_online = panel_id not in self.online
            self.online.add(panel_id)
            self.last_seen[panel_id] = monotonic()
            name = data["event"]
            panel = self.data["panels"][panel_id]
            pending = self.native_pending.get(panel_id)
            updated = deepcopy(self.data)
            target = updated["panels"][panel_id]
            blocked = name == "profile_reset" or (name == "profile_status" and data.get("detail") == "yaml_override_active")
            if blocked:
                target["remote_blocked"] = True
                if name == "profile_reset":
                    target.pop("resume_requested", None)  # A newer local reset cancels an older HA resume.
                if pending and pending[0] == "reset":
                    target.pop("reset_requested", None)
                self.native_pending.pop(panel_id, None)
                self.results[panel_id] = "local_override" if panel.get("profile_id") else "unassigned"
            elif name == "remote_profiles_allowed":
                target["remote_blocked"] = False
                if pending and pending[0] == "allow":
                    target.pop("resume_requested", None)
                    self.native_pending.pop(panel_id, None)
                    self.results[panel_id] = "unassigned"
            elif name == "profile_rejected" and pending and pending[0] == "apply":
                self.native_pending.pop(panel_id, None)
                self.results[panel_id] = "error"
                self.native_errors[panel_id] = str(data.get("detail", "profile_rejected"))[:256]
                if data.get("detail") == "local_override_reset_in_ha_required":
                    target["remote_blocked"] = True
            elif name in {"profile_status", "profile_applied"}:
                if name == "profile_status":
                    target["remote_blocked"] = False
                reported = (data.get("profile_id"), revision)
                if pending and pending[0] == "apply" and reported == pending[1:]:
                    self.native_pending.pop(panel_id, None)
                    self.results[panel_id] = "unassigned"  # Deliver a newer queued applied revision below.
                desired = self.data["applied"].get(panel.get("profile_id"))
                if desired and reported == (desired["id"], desired["revision"]) and not self.native_pending.get(panel_id) and not panel.get("reset_requested") and not panel.get("resume_requested"):
                    self.results[panel_id] = "applied"
                    self.native_errors.pop(panel_id, None)
            if updated != self.data:
                await self._persist(updated)
            # Only explicit assignment may clear a device-side reset latch.
            if not self.native_pending.get(panel_id) and (
                self.data["panels"][panel_id].get("reset_requested") or self.data["panels"][panel_id].get("resume_requested") or
                (not blocked and (newly_online or self.results.get(panel_id) == "unassigned"))
            ) and self.results.get(panel_id) != "applied" and (newly_online or self.results.get(panel_id) not in {"timeout", "error"}):
                await self._native_deliver(panel_id)

"""One persistent HA notification per prolonged panel/profile problem."""

from hashlib import sha256
import re

from homeassistant.components import persistent_notification

from .const import DOMAIN, PANEL_URL, TITLE


class PanelNotifications:
    def __init__(self, hass, scope):
        self.hass = hass
        self.scope = scope
        self.issues = {}

    def notification_id(self, panel_id):
        identity = sha256((self.scope + ":" + panel_id).encode()).hexdigest()[:20]
        return f"{DOMAIN}_panel_{identity}"

    def clear(self, panel_id):
        issue = self.issues.pop(panel_id, None)
        if issue and issue["notified"]:
            persistent_notification.async_dismiss(self.hass, self.notification_id(panel_id))

    def close(self):
        for panel_id in list(self.issues):
            self.clear(panel_id)

    def update(self, candidates, now):
        for panel_id in set(self.issues) - set(candidates):
            self.clear(panel_id)
        for panel_id, problem in candidates.items():
            identity = (problem["profile_id"], problem["revision"], problem["reason"])
            issue = self.issues.get(panel_id)
            if issue is None or issue["identity"] != identity:
                self.clear(panel_id)
                issue = {"identity": identity, "since": now, "notified": False}
                self.issues[panel_id] = issue
            threshold = 300 if problem["reason"] == "offline" else 120
            if not issue["notified"] and now - issue["since"] >= threshold:
                persistent_notification.async_create(
                    self.hass, self.message(problem), title=TITLE,
                    notification_id=self.notification_id(panel_id),
                )
                # Do not recreate a manually dismissed notification in the same episode.
                issue["notified"] = True

    def message(self, problem):
        def escaped(value):
            return re.sub(r"([\\`*_{}\[\]<>()#!|])", r"\\\1", str(value))
        panel = escaped(problem["name"])
        profile = escaped(problem["profile_name"])
        language = getattr(getattr(self.hass, "config", None), "language", "en").split("-")[0]
        if language == "uk":
            reason = ("Панель не на зв’язку понад 5 хвилин." if problem["reason"] == "offline"
                      else "Профіль не вдалося доставити або застосувати понад 2 хвилини.")
            return f"**{panel}**\n\n{reason} Призначений профіль: **{profile}**.\n\n[Відкрити VIEWE Smart Panel](/{PANEL_URL})"
        reason = ("The panel has been offline for over 5 minutes." if problem["reason"] == "offline"
                  else "Profile delivery or application has been failing for over 2 minutes.")
        return f"**{panel}**\n\n{reason} Assigned profile: **{profile}**.\n\n[Open VIEWE Smart Panel](/{PANEL_URL})"

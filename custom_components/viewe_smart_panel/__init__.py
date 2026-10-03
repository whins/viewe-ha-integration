"""VIEWE Smart Panel integration setup."""

from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig

from .const import DOMAIN, PANEL_URL, STATIC_URL, TITLE
from .hub import VieweHub
from .websocket import async_register_commands


async def async_setup_entry(hass, entry):
    hub = VieweHub(hass, entry.data["topic_prefix"])
    await hub.async_start()
    hass.data[DOMAIN] = hub
    try:
        if not hass.data.get(f"{DOMAIN}_registered"):
            await hass.http.async_register_static_paths([StaticPathConfig(STATIC_URL, str(Path(__file__).parent / "frontend"), False)])
            async_register_commands(hass)
            hass.data[f"{DOMAIN}_registered"] = True
        await panel_custom.async_register_panel(
            hass, frontend_url_path=PANEL_URL, webcomponent_name="viewe-panel",
            sidebar_title=TITLE, sidebar_icon="mdi:tablet-dashboard",
            module_url=f"{STATIC_URL}/panel.js", require_admin=True,
        )
    except Exception:
        hub.async_stop()
        hass.data.pop(DOMAIN, None)
        raise
    return True


async def async_unload_entry(hass, entry):
    hub = hass.data.pop(DOMAIN)
    hub.async_stop()
    frontend.async_remove_panel(hass, PANEL_URL)
    return True

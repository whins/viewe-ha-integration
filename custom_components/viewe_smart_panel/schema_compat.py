"""Support HA's schema library transition without an extra dependency."""

try:
    import probatio as vol
except ImportError:
    import voluptuous as vol

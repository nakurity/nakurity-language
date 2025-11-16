# src/core/plugin_manager.py

import importlib.util
import json
import os
from typing import Dict, Any
from .events import EventBus


class PluginError(Exception):
    pass


class PluginManager:
    """
    True lazy plugin manager.
    - Loads config only
    - Loads NO plugins until requested
    - Allows forced loading only in development (released=False)
    """

    def __init__(self, root_dir: str, released: bool = False, event_bus = EventBus):
        self.root_dir = root_dir
        self.released = released  # production mode = no force
        self.event_bus = event_bus
        
        self.config: Dict[str, Any] = {}
        self.enabled: list[str] = []

        # Optional stuff
        self.version: str = "0.0.1"

        # plugin_key → python module object
        self._loaded_modules: Dict[str, Any] = {}

    # ----------------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------------
    def _abs(self, rel: str) -> str:
        """Return absolute path anchored inside static/."""
        if not rel.startswith("static/") and not rel.startswith("."):
            error_message = f"Invalid plugin path: {rel} (must be inside static/)"
            self.event_bus.emit('plugin:manager.error', error=error_message)
            raise PluginError(error_message)
        return os.path.join(self.root_dir, rel)

    def _check_static_exists(self):
        static_dir = os.path.join(self.root_dir, "static")
        if not os.path.isdir(static_dir):
            error_message = "Static directory missing. Please download the static package."
            self.event_bus.emit('plugin:manager.error', error=error_message)
            raise PluginError(
                error_message
            )

    def _module_key(self, path: str) -> str:
        """Stable key for loaded_modules mapping."""
        return os.path.relpath(path, self.root_dir).replace("\\", "/")

    # ----------------------------------------------------------------------
    # CONFIG
    # ----------------------------------------------------------------------
    def load_config(self):
        """Load the config file. Must exist."""
        self.event_bus.emit('plugin:manager.config.before_load')
        cfg_path = os.path.join(self.root_dir, "static/.masha/config.json")
        if not os.path.isfile(cfg_path):
            error_message = (
                "Config missing: static/.masha/config.json — "
                "download static package."
            )
            self.event_bus.emit('plugin:manager.config.error', error=error_message)
            raise PluginError(
                error_message
            )

        self._check_static_exists()

        with open(cfg_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        # Validate version
        if "version" not in self.config:
            error_message = "Config invalid: missing 'version' string"
            self.event_bus.emit('plugin:manager.config.error', error=error_message)
            raise PluginError(error_message)

        # Validate new format
        if "enabled" not in self.config:
            error_message = "Config invalid: missing 'enabled' array."
            self.event_bus.emit('plugin:manager.config.error', error=error_message)
            raise PluginError(error_message)

        self.version = self.config.get('version', 'error')

        # further validate version
        if self.version == 'error':
            error_message = "Config invalid: string 'version' missing its contents"
            self.event_bus.emit('plugin:manager.config.error', error=error_message)
            raise PluginError(error_message)

        self.enabled = self.config["enabled"]

    # ----------------------------------------------------------------------
    # LAZY LOADING
    # ----------------------------------------------------------------------
    def _import_plugin(self, rel_path: str, *, force=False):
        """Load a plugin file lazily."""

        # Resolve absolute path
        abs_path = self._abs("static/" + rel_path.replace("@", "", 1))

        if not os.path.isfile(abs_path):
            error_message = f"Plugin file not found: {rel_path}"
            self.event_bus.emit('plugin:import_validation.error', error=error_message)
            raise PluginError(error_message)

        mod_key = self._module_key(abs_path)
        if mod_key in self._loaded_modules:
            return self._loaded_modules[mod_key]

        # Enforce enabled only
        if rel_path not in self.enabled:
            if force and not self.released:
                self.event_bus.emit('plugin:force_load', plugin_path=rel_path)

                # allowed only in development
                print(f"[force-load] {rel_path}")
            else:
                error_message = (
                    f"Plugin '{rel_path}' is not in config.enabled "
                    "— blocked. (use force=True in development)"
                )
                self.event_bus.emit('plugin:force_load.error', error=error_message)
                raise PluginError(
                    error_message
                )
            
        self.event_bus.emit("plugin:before_load", path=rel_path)

        # Actually import lazily now
        spec = importlib.util.spec_from_file_location(mod_key, abs_path)
        if spec is None or spec.loader is None:
            raise PluginError(f"Failed to load plugin: {rel_path}")

        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
            self.event_bus.emit("plugin:after_load", path=rel_path, module=mod)
        except Exception as e:
            self.event_bus.emit("plugin:error", path=rel_path, error=e)
            raise PluginError(f"Plugin import error in {rel_path}: {e}")

        # Store
        self._loaded_modules[mod_key] = mod

        # call register if exists
        register_fn = getattr(mod, "register", None)
        if callable(register_fn):
            try:
                register_fn(self, module_key=mod_key)
                self.event_bus.emit("plugin:registered", path=rel_path, module=mod)
            except Exception as e:
                self.event_bus.emit("plugin:error", path=rel_path, error=e)
                raise PluginError(f"Plugin register() failed in {rel_path}: {e}")

        return mod

    # ----------------------------------------------------------------------
    # PUBLIC API — for accessing plugin modules
    # ----------------------------------------------------------------------
    def get_plugin(self, rel_path: str, *, force=False):
        """
        Get a plugin by its relative path inside static/.
        Example: pm.get_plugin(".needy/modules/runner.py")
        """
        if rel_path.startswith('> '): rel_path = rel_path.replace('> ', '@', 1)
        return self._import_plugin(rel_path, force=force)

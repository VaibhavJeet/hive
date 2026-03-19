"""
Configuration Watcher - Hot-reload configuration changes.

Uses watchdog library to monitor config files and trigger callbacks
when changes are detected. Supports safe hot-reload for applicable settings.
"""

import asyncio
import logging
import threading
from pathlib import Path
from typing import Optional, Callable, Set, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


# =============================================================================
# HOT-RELOAD SAFETY
# =============================================================================

class ReloadSafety(str, Enum):
    """Safety level for configuration hot-reload."""
    SAFE = "safe"  # Can be reloaded without restart
    RESTART_RECOMMENDED = "restart_recommended"  # Works but restart is better
    RESTART_REQUIRED = "restart_required"  # Requires restart to take effect


# Fields that are safe to hot-reload
SAFE_RELOAD_PATHS: Set[str] = {
    # Cache TTLs
    "cache.default_ttl",
    "cache.llm_response_ttl",
    "cache.bot_profile_ttl",
    "cache.community_ttl",

    # LLM parameters (can change model behavior on the fly)
    "llm.max_tokens",
    "llm.temperature",

    # Engine timing (affects new activities only)
    "engine.max_active_bots",
    "engine.min_typing_delay_ms",
    "engine.max_typing_delay_ms",
    "engine.min_response_delay_ms",
    "engine.max_response_delay_ms",
    "engine.activity_check_interval",

    # Memory settings
    "memory.retrieval_limit",
    "memory.consolidation_threshold",

    # Monitoring
    "monitoring.log_level",
    "monitoring.health_check_timeout",
}

# Fields that recommend restart
RESTART_RECOMMENDED_PATHS: Set[str] = {
    # LLM model changes
    "llm.ollama_model",
    "llm.ollama_embedding_model",
    "llm.max_concurrent_requests",
    "llm.batch_size",

    # Connection pools
    "redis.max_connections",
    "database.pool_size",
}

# Fields that require restart (connection strings, security, etc.)
RESTART_REQUIRED_PATHS: Set[str] = {
    "database.url",
    "redis.url",
    "security.jwt_secret_key",
    "security.jwt_algorithm",
    "api.host",
    "api.port",
    "api.workers",
    "environment",
}


def get_reload_safety(path: str) -> ReloadSafety:
    """Determine the reload safety level for a config path."""
    if path in SAFE_RELOAD_PATHS:
        return ReloadSafety.SAFE
    elif path in RESTART_RECOMMENDED_PATHS:
        return ReloadSafety.RESTART_RECOMMENDED
    elif path in RESTART_REQUIRED_PATHS:
        return ReloadSafety.RESTART_REQUIRED

    # Check prefixes
    for safe_path in SAFE_RELOAD_PATHS:
        if path.startswith(safe_path.split(".")[0] + "."):
            return ReloadSafety.SAFE

    return ReloadSafety.RESTART_RECOMMENDED


# =============================================================================
# CONFIG CHANGE EVENT
# =============================================================================

@dataclass
class ConfigChangeEvent:
    """Event representing a configuration change."""
    path: str  # Config file path
    changed_fields: List[str]  # List of changed config paths
    timestamp: datetime = field(default_factory=datetime.utcnow)
    safety_level: ReloadSafety = ReloadSafety.SAFE
    old_values: Dict[str, Any] = field(default_factory=dict)
    new_values: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# CONFIG WATCHER
# =============================================================================

class ConfigWatcher:
    """
    Watches configuration files for changes and triggers hot-reload.

    Usage:
        watcher = ConfigWatcher()
        watcher.watch(
            Path("config.yaml"),
            on_change=handle_config_change
        )
        # ... later
        watcher.stop()
    """

    def __init__(self):
        self._observers: Dict[Path, Any] = {}
        self._callbacks: Dict[Path, List[Callable[[ConfigChangeEvent], None]]] = {}
        self._running = False
        self._lock = threading.Lock()
        self._last_config: Dict[Path, Dict[str, Any]] = {}
        self._debounce_seconds = 1.0
        self._pending_events: Dict[Path, asyncio.Task] = {}

    def watch(
        self,
        config_path: Path,
        callback: Callable[[ConfigChangeEvent], None],
        debounce_seconds: float = 1.0,
    ) -> bool:
        """
        Start watching a configuration file.

        Args:
            config_path: Path to the config file to watch
            callback: Function to call when config changes
            debounce_seconds: Wait time to debounce rapid changes

        Returns:
            True if watching started successfully
        """
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler, FileModifiedEvent
        except ImportError:
            logger.warning(
                "watchdog library not installed. Config hot-reload disabled. "
                "Install with: pip install watchdog"
            )
            return False

        config_path = Path(config_path).resolve()

        if not config_path.exists():
            logger.warning(f"Config file does not exist: {config_path}")
            return False

        with self._lock:
            # Add callback
            if config_path not in self._callbacks:
                self._callbacks[config_path] = []
            self._callbacks[config_path].append(callback)

            # Store initial config
            self._last_config[config_path] = self._load_config(config_path)

            # If already watching this file, just add the callback
            if config_path in self._observers:
                logger.debug(f"Already watching {config_path}, added callback")
                return True

            # Create event handler
            watcher = self

            class ConfigEventHandler(FileSystemEventHandler):
                def on_modified(self, event):
                    if event.is_directory:
                        return
                    if Path(event.src_path).resolve() == config_path:
                        watcher._on_file_modified(config_path)

            # Create observer
            observer = Observer()
            observer.schedule(
                ConfigEventHandler(),
                str(config_path.parent),
                recursive=False
            )

            self._observers[config_path] = observer
            self._debounce_seconds = debounce_seconds

            # Start observer
            observer.start()
            self._running = True

            logger.info(f"Started watching config file: {config_path}")
            return True

    def stop_watching(self, config_path: Optional[Path] = None):
        """
        Stop watching a specific config file or all files.

        Args:
            config_path: Specific file to stop watching, or None for all
        """
        with self._lock:
            if config_path:
                config_path = Path(config_path).resolve()
                if config_path in self._observers:
                    self._observers[config_path].stop()
                    self._observers[config_path].join(timeout=5.0)
                    del self._observers[config_path]
                    self._callbacks.pop(config_path, None)
                    self._last_config.pop(config_path, None)
                    logger.info(f"Stopped watching: {config_path}")
            else:
                # Stop all observers
                for path, observer in list(self._observers.items()):
                    observer.stop()
                    observer.join(timeout=5.0)
                self._observers.clear()
                self._callbacks.clear()
                self._last_config.clear()
                self._running = False
                logger.info("Stopped watching all config files")

    def stop(self):
        """Stop all watchers (alias for stop_watching())."""
        self.stop_watching()

    def _on_file_modified(self, config_path: Path):
        """Handle file modification event with debouncing."""
        # Cancel any pending debounced event
        if config_path in self._pending_events:
            self._pending_events[config_path].cancel()

        # Schedule new debounced event
        def trigger_callbacks():
            try:
                event = self._create_change_event(config_path)
                if event and event.changed_fields:
                    self._notify_callbacks(config_path, event)
            except Exception as e:
                logger.error(f"Error processing config change: {e}")

        # Use a timer for debouncing
        timer = threading.Timer(self._debounce_seconds, trigger_callbacks)
        timer.start()

    def _load_config(self, config_path: Path) -> Dict[str, Any]:
        """Load config from file."""
        from mind.config.config_loader import ConfigLoader

        loader = ConfigLoader()
        try:
            return loader.load_from_file(config_path)
        except Exception as e:
            logger.error(f"Error loading config from {config_path}: {e}")
            return {}

    def _create_change_event(self, config_path: Path) -> Optional[ConfigChangeEvent]:
        """Create a change event by comparing old and new config."""
        new_config = self._load_config(config_path)
        old_config = self._last_config.get(config_path, {})

        # Find changed fields
        changed_fields = []
        old_values = {}
        new_values = {}

        def compare_dicts(old: Dict, new: Dict, prefix: str = ""):
            for key in set(list(old.keys()) + list(new.keys())):
                path = f"{prefix}.{key}" if prefix else key
                old_val = old.get(key)
                new_val = new.get(key)

                if isinstance(old_val, dict) and isinstance(new_val, dict):
                    compare_dicts(old_val, new_val, path)
                elif old_val != new_val:
                    changed_fields.append(path)
                    old_values[path] = old_val
                    new_values[path] = new_val

        compare_dicts(old_config, new_config)

        if not changed_fields:
            return None

        # Determine overall safety level
        safety_level = ReloadSafety.SAFE
        for field_path in changed_fields:
            field_safety = get_reload_safety(field_path)
            if field_safety == ReloadSafety.RESTART_REQUIRED:
                safety_level = ReloadSafety.RESTART_REQUIRED
                break
            elif field_safety == ReloadSafety.RESTART_RECOMMENDED:
                safety_level = ReloadSafety.RESTART_RECOMMENDED

        # Update stored config
        self._last_config[config_path] = new_config

        return ConfigChangeEvent(
            path=str(config_path),
            changed_fields=changed_fields,
            safety_level=safety_level,
            old_values=old_values,
            new_values=new_values,
        )

    def _notify_callbacks(self, config_path: Path, event: ConfigChangeEvent):
        """Notify all callbacks for a config file."""
        callbacks = self._callbacks.get(config_path, [])

        for callback in callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in config change callback: {e}")

        # Log the change
        if event.safety_level == ReloadSafety.RESTART_REQUIRED:
            logger.warning(
                f"Config changed (RESTART REQUIRED): {event.changed_fields}"
            )
        elif event.safety_level == ReloadSafety.RESTART_RECOMMENDED:
            logger.info(
                f"Config changed (restart recommended): {event.changed_fields}"
            )
        else:
            logger.info(f"Config changed (hot-reloaded): {event.changed_fields}")

    def is_watching(self, config_path: Optional[Path] = None) -> bool:
        """Check if watching a specific file or any file."""
        if config_path:
            return Path(config_path).resolve() in self._observers
        return len(self._observers) > 0

    def get_watched_files(self) -> List[Path]:
        """Get list of currently watched files."""
        return list(self._observers.keys())


# =============================================================================
# ASYNC CONFIG WATCHER
# =============================================================================

class AsyncConfigWatcher(ConfigWatcher):
    """
    Async-compatible config watcher.

    Wraps callbacks in async-safe execution.
    """

    def __init__(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        super().__init__()
        self._loop = loop
        self._async_callbacks: Dict[Path, List[Callable]] = {}

    async def watch_async(
        self,
        config_path: Path,
        callback: Callable[[ConfigChangeEvent], Any],
        debounce_seconds: float = 1.0,
    ) -> bool:
        """
        Start watching with an async callback.

        Args:
            config_path: Path to the config file
            callback: Async function to call on changes
            debounce_seconds: Debounce time

        Returns:
            True if watching started
        """
        config_path = Path(config_path).resolve()

        # Store async callback
        if config_path not in self._async_callbacks:
            self._async_callbacks[config_path] = []
        self._async_callbacks[config_path].append(callback)

        # Create sync wrapper that schedules async callback
        def sync_callback(event: ConfigChangeEvent):
            asyncio.run_coroutine_threadsafe(
                self._run_async_callbacks(config_path, event),
                self._loop or asyncio.get_event_loop()
            )

        return self.watch(config_path, sync_callback, debounce_seconds)

    async def _run_async_callbacks(
        self,
        config_path: Path,
        event: ConfigChangeEvent
    ):
        """Run all async callbacks for a config path."""
        callbacks = self._async_callbacks.get(config_path, [])

        for callback in callbacks:
            try:
                result = callback(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Error in async config callback: {e}")


# =============================================================================
# SINGLETON AND HELPERS
# =============================================================================

_config_watcher: Optional[ConfigWatcher] = None


def get_config_watcher() -> ConfigWatcher:
    """Get the global config watcher instance."""
    global _config_watcher
    if _config_watcher is None:
        _config_watcher = ConfigWatcher()
    return _config_watcher


def watch_config(
    config_path: Path,
    callback: Callable[[ConfigChangeEvent], None],
) -> bool:
    """Convenience function to start watching a config file."""
    return get_config_watcher().watch(config_path, callback)


def stop_watching_config():
    """Convenience function to stop all config watchers."""
    if _config_watcher:
        _config_watcher.stop()

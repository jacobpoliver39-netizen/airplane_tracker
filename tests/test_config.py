"""
Environment-variable parsing in config.py. Each case imports config in a
fresh interpreter, so the module-level settings are read exactly as at
startup and nothing leaks into other tests.
"""

import os
import pathlib
import subprocess
import sys

import pytest

import config

ROOT = pathlib.Path(__file__).resolve().parent.parent

SETTINGS = (
    "POLL_INTERVAL_SECONDS",
    "REPLAY_SPEED",
    "REPLAY_START_SECONDS",
    "REPLAY_LOOP",
    "REPLAY_FILE",
)
OVERRIDES = (
    "JACOBSKY_POLL_INTERVAL",
    "JACOBSKY_REPLAY_SPEED",
    "JACOBSKY_REPLAY_START",
    "JACOBSKY_REPLAY_LOOP",
    "JACOBSKY_REPLAY",
    "OPENSKY_CLIENT_ID",
    "OPENSKY_CLIENT_SECRET",
)


def load_config(**environment):
    """Import config with only the given overrides set. Returns (settings, error)."""
    env = {key: value for key, value in os.environ.items() if key not in OVERRIDES}
    env.update(environment)
    code = (
        "import config; "
        f"print(repr([getattr(config, name) for name in {SETTINGS!r}]))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, env=env,
        capture_output=True, text=True,
        check=False,  # a failing import is an expected outcome here
    )

    if result.returncode != 0:
        return None, result.stderr.strip().splitlines()[-1]

    return dict(zip(SETTINGS, eval(result.stdout))), None


def test_defaults_without_overrides():
    settings, error = load_config()

    assert error is None
    assert settings == {
        "POLL_INTERVAL_SECONDS": 15,
        "REPLAY_SPEED": 1.0,
        "REPLAY_START_SECONDS": 0.0,
        "REPLAY_LOOP": False,
        "REPLAY_FILE": None,
    }


@pytest.mark.parametrize(
    "value, expected",
    [
        ("1", True), ("true", True), ("Yes", True), ("ON", True),
        ("0", False), ("false", False), ("False", False), ("no", False), ("off", False),
        ("", False), ("  ", False),
    ],
)
def test_replay_loop_accepts_common_spellings(value, expected):
    settings, error = load_config(JACOBSKY_REPLAY_LOOP=value)

    assert error is None
    assert settings["REPLAY_LOOP"] is expected


@pytest.mark.parametrize(
    "name, value, message",
    [
        ("JACOBSKY_REPLAY_LOOP", "maybe", "JACOBSKY_REPLAY_LOOP must be one of"),
        ("JACOBSKY_POLL_INTERVAL", "abc", "JACOBSKY_POLL_INTERVAL must be a whole number"),
        ("JACOBSKY_POLL_INTERVAL", "0", "JACOBSKY_POLL_INTERVAL must be at least 1"),
        ("JACOBSKY_REPLAY_SPEED", "-5", "JACOBSKY_REPLAY_SPEED must be between 0.25 and 120"),
        ("JACOBSKY_REPLAY_SPEED", "fast", "JACOBSKY_REPLAY_SPEED must be a number"),
        ("JACOBSKY_REPLAY_START", "-1", "JACOBSKY_REPLAY_START must be at least 0"),
    ],
)
def test_invalid_values_fail_at_startup_naming_the_variable(name, value, message):
    settings, error = load_config(**{name: value})

    assert settings is None
    assert error.startswith("ValueError: ")
    assert message in error


def test_valid_overrides_are_used():
    settings, error = load_config(
        JACOBSKY_POLL_INTERVAL=" 45 ",
        JACOBSKY_REPLAY_SPEED="60",
        JACOBSKY_REPLAY_START="1800",
        JACOBSKY_REPLAY="data/recordings/x.jsonl",
    )

    assert error is None
    assert settings["POLL_INTERVAL_SECONDS"] == 45
    assert settings["REPLAY_SPEED"] == 60.0
    assert settings["REPLAY_START_SECONDS"] == 1800.0
    assert settings["REPLAY_FILE"] == "data/recordings/x.jsonl"


def test_data_paths_are_defined_once_in_config():
    import collect_opensky
    import flight_recording

    assert config.RECORDINGS_DIR == config.DATA_DIR / "recordings"
    assert collect_opensky.OUTPUT_FILE == config.OBSERVATIONS_CSV
    assert flight_recording.default_recording_path().parent == config.RECORDINGS_DIR
    assert not hasattr(flight_recording, "RECORDINGS_DIR")

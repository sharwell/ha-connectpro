"""Dependency loading with serialx versions shared with Home Assistant."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from packaging.requirements import Requirement

from homeassistant.core import HomeAssistant
from homeassistant.requirements import async_process_requirements

MANIFEST = json.loads(
    (
        Path(__file__).resolve().parents[1]
        / "custom_components/connectpro/manifest.json"
    ).read_text(encoding="utf-8")
)


@pytest.mark.parametrize("installed_version", ["1.10.0", "1.11.0", "1.99.0"])
async def test_compatible_serialx_does_not_trigger_install(tmp_path, installed_version):
    """An HA upgrade must not attempt to downgrade its compatible serial library."""
    hass = HomeAssistant(str(tmp_path))
    try:
        with (
            patch("homeassistant.util.package.version", return_value=installed_version),
            patch(
                "homeassistant.util.package.install_package", return_value=False
            ) as install,
        ):
            await async_process_requirements(
                hass, "connectpro", MANIFEST["requirements"]
            )
        install.assert_not_called()
    finally:
        await hass.async_stop(force=True)


@pytest.mark.parametrize("unsupported_version", ["1.9.0", "2.0.0"])
def test_unsupported_serialx_requires_dependency_resolution(unsupported_version):
    """Keep a minimum API version and require review of a new major release."""
    requirement = next(
        Requirement(value)
        for value in MANIFEST["requirements"]
        if Requirement(value).name == "serialx"
    )
    assert unsupported_version not in requirement.specifier

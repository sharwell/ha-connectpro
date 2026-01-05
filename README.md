# ConnectPro KVM (Home Assistant)

This repository contains a custom Home Assistant integration for the
ConnectPro KVM. It is currently a scaffold to enable early HACS installation
and iterative development.

## Status

- HACS installable
- Config flow stub for serial settings
- Protocol docs placeholder: docs/commands.md

## HACS installation (custom repo)

1. In HACS, add this repo as a custom integration.
2. Install "ConnectPro KVM".
3. Restart Home Assistant.
4. Add the integration in Settings -> Devices & Services.

## Development notes

- The serial protocol reference will live in docs/commands.md.
- Update `custom_components/connectpro/manifest.json` with your final
  documentation URL when the repo is published.

### Local Codex initialization prompt

> Read AGENTS.md and README.md to familiarize yourself with this repository. After performing any work which resulted in uncommitted changes to repository files, provide a commit message for the work. Commit messages should be provided in fenced code blocks for easy copy/paste.

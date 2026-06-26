# Hermes Skill Vault

**Hermes Skill Vault** is a Hermes plugin for managing installed skills by source.
It groups skills into four source-aware views and supports:

- **builtin** skills
- **hub** skills
- **local** skills
- **optional** official catalog skills

It also supports:

- **physical delete** with a local backup
- **restore** from backup or source
- **install** flows for builtin, hub, and optional skills

> Note: this repo is the plugin implementation, not a skill itself.

## Why this exists

Hermes already has strong skill lifecycle primitives. Skill Vault adds a thinner
operator-facing layer so you can inspect, manage, delete, restore, and install
skills without digging through separate commands.

## Features

### 1) Source-aware inventory

List skills by source:

- `builtin`
- `hub`
- `local`
- `optional`

### 2) Physical deletion

Delete an installed skill from disk, while keeping a backup in the plugin's own
trash area for recovery.

### 3) Restore

Restore a deleted skill from the backup copy. For builtin skills, restore uses
the bundled reset path.

### 4) Install

Install or reinstall from these sources:

- builtin
- hub
- optional official catalog

## Example commands

```bash
hermes skill-vault list
hermes skill-vault list --source builtin
hermes skill-vault delete --source local my-skill
hermes skill-vault restore --source local my-skill
hermes skill-vault install optional official/mlops/training/trl-fine-tuning
```

## Repository structure

```text
skill-vault/
├── __init__.py
├── cli.py
├── plugin.yaml
└── README.md
```

## Installation

If you are working inside the Hermes profile that has this plugin installed:

1. Copy the plugin into `~/.hermes/plugins/skill-vault/`
2. Add it to your Hermes plugin config if needed
3. Restart Hermes / reload plugins

## Development

This plugin is intentionally thin and reuses Hermes' existing skill lifecycle
helpers where possible.

If you extend it, keep the operations source-aware and keep destructive actions
backed by a recoverable backup path.

## Name

- **Human name:** Hermes Skill Vault
- **GitHub repo:** `hermes-skill-vault`
- **Plugin id:** `skill-vault`

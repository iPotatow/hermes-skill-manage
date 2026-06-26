"""Skill Vault plugin.

A source-aware CLI for listing, deleting, restoring, and installing Hermes
skills. Built on top of the existing Hermes skill lifecycle helpers instead of
reimplementing the hub logic from scratch.
"""

from __future__ import annotations

from .cli import register_cli, skill_vault_command


def register(ctx) -> None:
    """Register the CLI surface for this plugin."""
    ctx.register_cli_command(
        name="skill-vault",
        help="Manage installed Hermes skills by source",
        setup_fn=register_cli,
        handler_fn=skill_vault_command,
        description=(
            "List installed skills by source (builtin, hub, local), show the "
            "official optional catalog, and perform source-aware delete, "
            "restore, and install flows."
        ),
    )

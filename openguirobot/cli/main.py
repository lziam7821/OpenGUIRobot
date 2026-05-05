"""
OpenGUIRobot CLI entry point.

Usage:
    ogr doctor
    ogr explore <case_id> --device <id>
    ogr replay  <case_id> --device <id>
    ogr cases list
    ogr cases show <case_id>
    ogr kb lint [--strict]
"""
from __future__ import annotations

import click

from openguirobot.cli.commands.cases import cases
from openguirobot.cli.commands.doctor import doctor
from openguirobot.cli.commands.explore import explore
from openguirobot.cli.commands.kb import kb
from openguirobot.cli.commands.replay import replay


@click.group()
@click.version_option(version="0.2.0", prog_name="ogr")
def app() -> None:
    """OpenGUIRobot — LLM-powered GUI automation test platform."""


app.add_command(doctor)
app.add_command(explore)
app.add_command(replay)
app.add_command(cases)
app.add_command(kb)

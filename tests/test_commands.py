import pytest
from django.core.management import get_commands


def test_commands_are_registered():
    commands = get_commands()
    assert "star_admin" in commands

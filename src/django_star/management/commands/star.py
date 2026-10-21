from django.core.management.base import BaseCommand
from rich.panel import Panel
from rich.table import Table
from django_star.console import console

COMMANDS_REGISTRY = [
    {
        "category": "Architecture & Scaffolding",
        "commands": [
            {
                "name": "star_app",
                "args": "<app_name> [--dir]",
                "desc": "Scaffolds a new app and auto-wires settings.py, app urls.py, and root urls.py in one step.",
            },
            {
                "name": "star_route",
                "args": "<app_name> [--prefix] [--no-template]",
                "desc": "Wires up existing apps: creates urls.py, templates folder, and mounts route in root urls.py.",
            },
            {
                "name": "star_service",
                "args": "<app_name> <service_name>",
                "desc": "Generates a clean architecture service layer with transaction and logging boilerplate.",
            },
            {
                "name": "star_command",
                "args": "<app_name> <command_name>",
                "desc": "Generates a complete BaseCommand skeleton under <app>/management/commands/.",
            },
        ],
    },
    {
        "category": "Admin & ORM Automation",
        "commands": [
            {
                "name": "star_admin",
                "args": "<app_name> [model_name] [--all]",
                "desc": "Inspects ORM models and auto-generates ModelAdmin classes with search_fields and list_filter.",
            },
        ],
    },
    {
        "category": "Inspection & Debugging",
        "commands": [
            {
                "name": "star_urls",
                "args": "[filter] [-e/--exclude app ...]",
                "desc": "Displays an interactive table of all registered URLs, callback views, and namespaces.",
            },
        ],
    },
    {
        "category": "API & Serialization",
        "commands": [
            {
                "name": "star_serializer",
                "args": "<app_name> [model_name] [--all]",
                "desc": "Inspects models and auto-generates DRF ModelSerializer classes in <app>/serializers.py.",
            },
            {
                "name": "star_schema",
                "args": "<app_name> [model_name] [--all]",
                "desc": "Inspects models and auto-generates Django Ninja In and Out schemas in <app>/schemas.py.",
            },
        ],
    },
]


class Command(BaseCommand):
    help = "Displays the Django Star command catalog and documentation."

    def handle(self, *args, **options):
        # 1. Header Banner
        banner = (
            "[bold green]Django Star[/bold green] [dim]— Modern Developer Automation for Django[/dim]\n"
            "[cyan]Run any command using:[/cyan] [bold white]python manage.py <command>[/bold white]"
        )
        console.print(Panel(banner, border_style="green", expand=False))
        console.print()

        # 2. Command Categories Table
        table = Table(
            show_header=True,
            header_style="bold magenta",
            border_style="dim",
            expand=True,
        )
        table.add_column("Command", style="bold cyan", width=18)
        table.add_column("Arguments / Flags", style="yellow", width=36)
        table.add_column("Description", style="white")

        for group in COMMANDS_REGISTRY:
            # Group separator
            table.add_section()
            table.add_row(f"[bold green]▶ {group['category']}[/bold green]", "", "")
            for cmd in group["commands"]:
                table.add_row(cmd["name"], cmd["args"], cmd["desc"])

        console.print(table)
        console.print()
        console.print(
            "[dim]Tip: Add '--help' to any specific command for detailed argument flags (e.g. python manage.py star_urls --help)[/dim]"
        )

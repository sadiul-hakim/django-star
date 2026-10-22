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
                "desc": "Scaffolds a new app and auto-wires settings, urls & root urls.",
            },
            {
                "name": "star_crud",
                "args": "<app_name> [model] [--all] [--api]",
                "desc": "Scaffolds complete CRUD views, URL routes & HTML templates.",
            },
            {
                "name": "star_view",
                "args": "<app_name> [model_or_view] [--crud] [--api] [--fbv]",
                "desc": "Generates Class-Based Views, ViewSets, or FBVs with URL routes.",
            },
            {
                "name": "star_route",
                "args": "<app_name> [--prefix] [--no-template]",
                "desc": "Wires existing app: creates urls.py, templates & root route.",
            },
            {
                "name": "star_service",
                "args": "<app_name> <service_name>",
                "desc": "Scaffolds service layer with @transaction.atomic and logging.",
            },
            {
                "name": "star_command",
                "args": "<app_name> <command_name>",
                "desc": "Generates BaseCommand skeleton under management/commands/.",
            },
            {
                "name": "star_template",
                "args": "<app_name> <template> [-e] [--html5] [--flat]",
                "desc": "Scaffolds namespaced HTML template with inheritance or HTML5 options.",
            },
        ],
    },
    {
        "category": "Admin & ORM Automation",
        "commands": [
            {
                "name": "star_admin",
                "args": "<app_name> [model] [--all]",
                "desc": "Auto-generates ModelAdmin with search_fields and list_filter.",
            },
            {
                "name": "star_theme",
                "args": "[theme] [--remove] [--no-pip]",
                "desc": "Installs & configures admin themes (jazzmin, simpleui, etc.).",
            },
        ],
    },
    {
        "category": "Inspection & Debugging",
        "commands": [
            {
                "name": "star_about",
                "args": "[--json]",
                "desc": "Displays project overview, health, database, apps & config dashboard.",
            },
            {
                "name": "star_urls",
                "args": "[filter] [-e/--exclude app ...]",
                "desc": "Displays interactive table of registered URLs & callback views.",
            },
        ],
    },
    {
        "category": "API & Serialization",
        "commands": [
            {
                "name": "star_serializer",
                "args": "<app_name> [model] [--all]",
                "desc": "Auto-generates DRF ModelSerializer classes in serializers.py.",
            },
            {
                "name": "star_schema",
                "args": "<app_name> [model] [--all]",
                "desc": "Auto-generates Django Ninja In and Out schema classes.",
            },
        ],
    },
]


class Command(BaseCommand):
    help = "Displays the Django Star command catalog and documentation."

    def handle(self, *args, **options):
        # 1. Header Banner
        banner = (
            "[bold green]Django Star[/bold green] [dim]-- Modern Developer Automation for Django[/dim]\n"
            "[cyan]Run any command using:[/cyan] [bold white]python manage.py <command>[/bold white]"
        )
        console.print(Panel(banner, border_style="green", expand=False))
        console.print()

        # 2. Command Categories (Clean Artisan-style grouping)
        seen_commands = set()
        for group in COMMANDS_REGISTRY:
            console.print(f"[bold magenta]{group['category'].upper()}[/bold magenta]")
            table = Table(
                box=None,
                show_header=False,
                pad_edge=False,
                padding=(0, 2),
                expand=False,
            )
            table.add_column("Command", style="bold cyan", width=18, no_wrap=True)
            table.add_column("Arguments", style="yellow")
            table.add_column("Description", style="bright_white")

            for cmd in group["commands"]:
                if cmd["name"] in seen_commands:
                    continue
                seen_commands.add(cmd["name"])
                table.add_row(f"  {cmd['name']}", cmd["args"], cmd["desc"])

            console.print(table)
            console.print()

        console.print(
            "[dim]Tip: Add '--help' to any specific command for detailed argument flags (e.g. python manage.py star_urls --help)[/dim]"
        )


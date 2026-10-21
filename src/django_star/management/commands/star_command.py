from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.apps import apps
from rich.console import Console

console = Console()

COMMAND_TEMPLATE = """from django.core.management.base import BaseCommand
from rich.console import Console

console = Console()


class Command(BaseCommand):
    help = "{command_name} command description"

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=100, help="Batch processing size")

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        console.print(f"[bold cyan]Running {command_name} with batch size: {{batch_size}}[/bold cyan]")
        # Implement execution logic here
        console.print("[bold green]✔ Done![/bold green]")
"""


class Command(BaseCommand):
    help = "Generates a complete BaseCommand skeleton in <app>/management/commands/<name>.py"

    def add_arguments(self, parser):
        parser.add_argument("app_name", type=str, help="Target application label")
        parser.add_argument(
            "command_name", type=str, help="Name of the new management command"
        )

    def handle(self, *args, **options):
        app_label = options["app_name"]
        cmd_name = options["command_name"].lower()

        try:
            app_config = apps.get_app_config(app_label)
        except LookupError:
            raise CommandError(f"Application '{app_label}' not found.")

        commands_dir = Path(app_config.path) / "management" / "commands"
        commands_dir.mkdir(parents=True, exist_ok=True)
        (Path(app_config.path) / "management" / "__init__.py").touch(exist_ok=True)
        (commands_dir / "__init__.py").touch(exist_ok=True)

        target_file = commands_dir / f"{cmd_name}.py"
        if target_file.exists():
            console.print(
                f"[bold yellow]⚠ Command {cmd_name}.py already exists. Skipping.[/bold yellow]"
            )
            return

        target_file.write_text(
            COMMAND_TEMPLATE.format(command_name=cmd_name), encoding="utf-8"
        )
        console.print(
            f"[bold green]✔ Scaffolding complete: [cyan]{cmd_name}[/cyan] is ready at [white]{target_file}[/white][/bold green]"
        )

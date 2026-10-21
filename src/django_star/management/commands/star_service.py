from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.apps import apps
from rich.console import Console

console = Console()

SERVICE_TEMPLATE = '''"""
{service_name} business logic service.
"""
import logging
from django.db import transaction

logger = logging.getLogger(__name__)


class {class_name}:
    """
    Service responsible for {action_name} operations.
    """

    @staticmethod
    @transaction.atomic
    def execute(*args, **kwargs):
        logger.info("Executing {service_name}...")
        # Write domain business logic here
        return True
'''


class Command(BaseCommand):
    help = "Creates an enterprise service layer file under <app>/services/<name>_service.py"

    def add_arguments(self, parser):
        parser.add_argument("app_name", type=str, help="Target application label")
        parser.add_argument(
            "service_name",
            type=str,
            help="Snake_case service name (e.g. process_payment)",
        )

    def handle(self, *args, **options):
        app_label = options["app_name"]
        raw_name = options["service_name"].lower().removesuffix("_service")

        try:
            app_config = apps.get_app_config(app_label)
        except LookupError:
            raise CommandError(f"Application '{app_label}' not found.")

        services_dir = Path(app_config.path) / "services"
        services_dir.mkdir(parents=True, exist_ok=True)
        (services_dir / "__init__.py").touch(exist_ok=True)

        target_file = services_dir / f"{raw_name}_service.py"
        if target_file.exists():
            console.print(
                f"[bold yellow]⚠ Service file {target_file.name} already exists. Skipping.[/bold yellow]"
            )
            return

        class_name = (
            "".join(part.capitalize() for part in raw_name.split("_")) + "Service"
        )
        rendered = SERVICE_TEMPLATE.format(
            service_name=raw_name,
            class_name=class_name,
            action_name=raw_name.replace("_", " "),
        )

        target_file.write_text(rendered, encoding="utf-8")
        console.print(
            f"[bold green]✔ Created service [cyan]{class_name}[/cyan] at [white]{target_file}[/white][/bold green]"
        )

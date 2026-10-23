from django.core.management.base import BaseCommand
from django.apps import apps
from rich.table import Table
from django_star.console import console


class Command(BaseCommand):
    help = "Lists all registered Django models in a clean table with filtering and app exclusion."

    def add_arguments(self, parser):
        parser.add_argument(
            "app_name",
            nargs="?",
            default=None,
            help="Optional specific app name to list models for (e.g. auth, myapp). If omitted, lists all models.",
        )
        parser.add_argument(
            "-f",
            "--filter",
            default=None,
            help="Optional search filter to match against model name, app label, or table name",
        )
        parser.add_argument(
            "-e",
            "--exclude",
            nargs="+",
            default=[],
            help="List of apps or model names to exclude (e.g. -e admin contenttypes)",
        )

    def handle(self, *args, **options):
        app_name = options["app_name"]
        search_filter = options["filter"]
        excluded_terms = [term.lower() for term in options["exclude"]]

        # Determine which models to fetch: if app_name is provided, filter by it; otherwise get all models.
        if app_name:
            try:
                app_config = apps.get_app_config(app_name)
                raw_models = app_config.get_models(include_auto_created=True)
            except LookupError:
                console.print(f"[bold red]App '{app_name}' not found.[/bold red]")
                return
        else:
            raw_models = apps.get_models(include_auto_created=True)

        table = Table(
            title="[bold green]Django Registered Models[/bold green]", show_lines=True
        )
        table.add_column("App Label", style="cyan", no_wrap=True)
        table.add_column("Model Name", style="yellow")
        table.add_column("Table Name", style="white")
        table.add_column("Fields", style="green", justify="right")
        table.add_column("Type", style="magenta")

        models_data = []
        for model in raw_models:
            meta = model._meta
            model_type = (
                "Proxy" if meta.proxy else ("Abstract" if meta.abstract else "Concrete")
            )
            models_data.append(
                {
                    "app_label": meta.app_label,
                    "model_name": model.__name__,
                    "table_name": meta.db_table,
                    "fields": str(len(meta.get_fields())),
                    "type": model_type,
                }
            )

        # 1. Filter out excluded apps, model names, or table names
        if excluded_terms:
            models_data = [
                m
                for m in models_data
                if not any(
                    ex in m["app_label"].lower()
                    or ex in m["model_name"].lower()
                    or ex in m["table_name"].lower()
                    for ex in excluded_terms
                )
            ]

        # 2. Apply positive search filter if provided
        if search_filter:
            sf = search_filter.lower()
            models_data = [
                m
                for m in models_data
                if sf in m["app_label"].lower()
                or sf in m["model_name"].lower()
                or sf in m["table_name"].lower()
                or sf in m["type"].lower()
            ]

        if not models_data:
            console.print("[yellow]No matching models found.[/yellow]")
            return

        for m in models_data:
            table.add_row(
                m["app_label"],
                m["model_name"],
                m["table_name"],
                m["fields"],
                m["type"],
            )

        console.print(table)
        console.print(f"[bold cyan]Total Models: {len(models_data)}[/bold cyan]")

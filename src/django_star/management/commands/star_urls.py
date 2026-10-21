from django.core.management.base import BaseCommand
from django.urls import get_resolver, URLPattern, URLResolver
from rich.table import Table
from django_star.console import console


class Command(BaseCommand):
    help = "Lists all registered URL patterns in a clean table with filtering and app exclusion."

    def add_arguments(self, parser):
        parser.add_argument(
            "filter",
            nargs="?",
            default=None,
            help="Optional search filter to match against URL pattern, name, or view",
        )
        parser.add_argument(
            "-e",
            "--exclude",
            nargs="+",
            default=[],
            help="List of apps, namespaces, or pattern prefixes to exclude (e.g. -e admin debug_toolbar)",
        )

    def handle(self, *args, **options):
        search_filter = options["filter"]
        excluded_terms = [term.lower() for term in options["exclude"]]
        resolver = get_resolver()

        table = Table(
            title="[bold green]Django Registered Routes[/bold green]", show_lines=True
        )
        table.add_column("Pattern", style="cyan", no_wrap=True)
        table.add_column("Name", style="yellow")
        table.add_column("View / Handler", style="white")
        table.add_column("Namespace", style="magenta")

        routes = []
        self._extract_routes(
            resolver.url_patterns, prefix="", namespace="", routes=routes
        )

        # 1. Filter out excluded apps / namespaces / patterns
        if excluded_terms:
            routes = [
                r
                for r in routes
                if not any(
                    ex in r["pattern"].lower()
                    or ex in r["namespace"].lower()
                    or ex in r["view"].lower()
                    for ex in excluded_terms
                )
            ]

        # 2. Apply positive search filter if provided
        if search_filter:
            routes = [
                r
                for r in routes
                if search_filter.lower() in r["pattern"].lower()
                or search_filter.lower() in r["name"].lower()
                or search_filter.lower() in r["view"].lower()
            ]

        if not routes:
            console.print("[yellow]No matching routes found.[/yellow]")
            return

        for r in routes:
            table.add_row(r["pattern"], r["name"], r["view"], r["namespace"])

        console.print(table)
        console.print(f"[bold cyan]Total Routes: {len(routes)}[/bold cyan]")

    def _extract_routes(self, patterns, prefix="", namespace="", routes=None):
        for entry in patterns:
            if isinstance(entry, URLPattern):
                full_pattern = prefix + str(entry.pattern)
                view_name = self._format_view_name(entry.callback)
                routes.append(
                    {
                        "pattern": "/" + full_pattern.lstrip("^").rstrip("$"),
                        "name": entry.name or "-",
                        "view": view_name,
                        "namespace": namespace or "-",
                    }
                )
            elif isinstance(entry, URLResolver):
                nested_prefix = prefix + str(entry.pattern)
                nested_namespace = (
                    f"{namespace}:{entry.namespace}"
                    if namespace and entry.namespace
                    else (entry.namespace or namespace)
                )
                self._extract_routes(
                    entry.url_patterns, nested_prefix, nested_namespace, routes
                )

    @staticmethod
    def _format_view_name(callback):
        if hasattr(callback, "view_class"):
            return f"{callback.view_class.__module__}.{callback.view_class.__name__}"
        if hasattr(callback, "__name__"):
            return f"{callback.__module__}.{callback.__name__}"
        return str(callback)

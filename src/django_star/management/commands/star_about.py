import json
import os
import platform
from pathlib import Path

import django
from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import URLPattern, URLResolver, get_resolver
from rich.panel import Panel
from rich.table import Table

from django_star.console import console

THEME_DISPLAY_NAMES = {
    "jazzmin": "Django Jazzmin",
    "simpleui": "Django SimpleUI",
    "grappelli": "Django Grappelli",
    "admin_interface": "Django Admin Interface",
}


def _is_local_path(app_path: Path, base_dir: Path) -> bool:
    try:
        resolved_app = app_path.resolve()
        resolved_base = base_dir.resolve()
        # Must be under BASE_DIR and not inside a virtual environment directory
        if resolved_base in resolved_app.parents or resolved_app == resolved_base:
            parts = resolved_app.parts
            if not any(
                p in ("site-packages", "dist-packages", ".venv", "venv", "env")
                for p in parts
            ):
                return True
    except Exception:
        pass
    return False


def _count_routes(resolver=None) -> int:
    if resolver is None:
        try:
            resolver = get_resolver()
        except Exception:
            return 0
    count = 0

    def _traverse(patterns):
        nonlocal count
        for entry in patterns:
            if isinstance(entry, URLPattern):
                count += 1
            elif isinstance(entry, URLResolver):
                try:
                    _traverse(entry.url_patterns)
                except Exception:
                    pass

    try:
        _traverse(resolver.url_patterns)
    except Exception:
        return 0
    return count


class Command(BaseCommand):
    help = "Displays a comprehensive project overview, health status, database, apps, and configuration dashboard."

    def add_arguments(self, parser):
        parser.add_argument(
            "--json",
            action="store_true",
            help="Output project health and configuration metrics as JSON.",
        )

    def handle(self, *args, **options):
        base_dir_val = getattr(settings, "BASE_DIR", Path.cwd())
        base_dir = Path(base_dir_val) if base_dir_val else Path.cwd()
        output_json = options.get("json", False)

        # 1. Environment & Config
        django_ver = django.get_version()
        python_ver = platform.python_version()
        os_info = f"{platform.system()} {platform.release()}"
        settings_module = os.environ.get(
            "DJANGO_SETTINGS_MODULE", getattr(settings, "SETTINGS_MODULE", "-")
        )
        debug_mode = getattr(settings, "DEBUG", False)
        secret_key = getattr(settings, "SECRET_KEY", "")
        secret_status = (
            "Insecure / Default"
            if (not secret_key or "insecure" in secret_key or len(secret_key) < 30)
            else "Configured"
        )
        allowed_hosts = getattr(settings, "ALLOWED_HOSTS", [])
        time_zone = getattr(settings, "TIME_ZONE", "UTC")
        use_tz = getattr(settings, "USE_TZ", True)
        language_code = getattr(settings, "LANGUAGE_CODE", "en-us")

        # 2. Database & Migrations
        default_db = getattr(settings, "DATABASES", {}).get("default", {})
        db_engine = default_db.get("ENGINE", "-")
        db_name = default_db.get("NAME", "-")
        db_host = default_db.get("HOST") or "localhost"
        db_port = default_db.get("PORT") or "-"

        pending_migrations_count = None
        migration_status_text = "Unknown"
        try:
            from django.db import connection
            from django.db.migrations.executor import MigrationExecutor

            executor = MigrationExecutor(connection)
            targets = executor.loader.graph.leaf_nodes()
            plan = executor.migration_plan(targets)
            pending_migrations_count = len(plan)
            if pending_migrations_count == 0:
                migration_status_text = "Up to date (0 pending)"
            else:
                migration_status_text = f"{pending_migrations_count} pending"
        except Exception as e:
            migration_status_text = f"Unreachable ({e})"

        # 3. Applications & Architecture
        app_configs = list(apps.get_app_configs())
        total_apps = len(app_configs)
        django_apps = []
        local_apps = []
        third_party_apps = []

        for app in app_configs:
            app_path = Path(app.path)
            if (
                app.name.startswith("django.contrib.")
                or "django" in app_path.parts
                and "contrib" in app_path.parts
            ):
                django_apps.append(app.label)
            elif _is_local_path(app_path, base_dir):
                local_apps.append(app.label)
            else:
                third_party_apps.append(app.label)

        # Detect active admin theme
        installed_apps_list = getattr(settings, "INSTALLED_APPS", [])
        active_theme = "Default (Stock Django Admin)"
        for key, display_name in THEME_DISPLAY_NAMES.items():
            if key in installed_apps_list:
                active_theme = display_name
                break

        # Models count
        all_models = list(apps.get_models())
        total_models = len(all_models)
        local_models_count = sum(
            1
            for m in all_models
            if getattr(m._meta.app_config, "path", None)
            and _is_local_path(Path(m._meta.app_config.path), base_dir)
        )

        # Routes count
        total_routes = _count_routes()

        # 4. Cache & Storage
        default_cache = getattr(settings, "CACHES", {}).get("default", {})
        cache_backend = default_cache.get(
            "BACKEND", "django.core.cache.backends.locmem.LocMemCache"
        )
        static_url = getattr(settings, "STATIC_URL", "-")
        static_root = str(getattr(settings, "STATIC_ROOT", "") or "-")
        media_url = getattr(settings, "MEDIA_URL", "-")
        media_root = str(getattr(settings, "MEDIA_ROOT", "") or "-")
        email_backend = getattr(
            settings, "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"
        )

        # JSON Output Mode
        if output_json:
            data = {
                "environment": {
                    "django_version": django_ver,
                    "python_version": python_ver,
                    "os": os_info,
                    "settings_module": settings_module,
                    "debug": debug_mode,
                    "secret_key_status": secret_status,
                    "allowed_hosts": allowed_hosts,
                    "timezone": time_zone,
                    "use_tz": use_tz,
                    "language_code": language_code,
                },
                "database": {
                    "engine": db_engine,
                    "name": str(db_name),
                    "host": db_host,
                    "port": str(db_port),
                    "pending_migrations": pending_migrations_count,
                    "migration_status": migration_status_text,
                },
                "apps_architecture": {
                    "total_apps": total_apps,
                    "django_apps": django_apps,
                    "local_apps": local_apps,
                    "third_party_apps": third_party_apps,
                    "admin_theme": active_theme,
                    "total_models": total_models,
                    "local_models": local_models_count,
                    "total_routes": total_routes,
                },
                "cache_storage": {
                    "cache_backend": cache_backend,
                    "static_url": static_url,
                    "static_root": static_root,
                    "media_url": media_url,
                    "media_root": media_root,
                    "email_backend": email_backend,
                },
            }
            self.stdout.write(json.dumps(data, indent=2))
            return

        # Render Terminal UI Dashboard
        project_name = (
            Path(settings_module.split(".")[0]).name
            if "." in settings_module
            else "Django Project"
        )
        banner = (
            "[bold green]Django Star[/bold green] [dim]-- Project Overview & Health Dashboard[/dim]\n"
            f"[cyan]Project:[/cyan] [bold white]{project_name}[/bold white]   "
            f"[cyan]Django:[/cyan] [bold white]{django_ver}[/bold white]   "
            f"[cyan]Python:[/cyan] [bold white]{python_ver}[/bold white]   "
            f"[cyan]OS:[/cyan] [bold white]{os_info}[/bold white]"
        )
        console.print(Panel(banner, border_style="green", expand=False))
        console.print()

        def create_section_table(title: str) -> Table:
            t = Table(
                title=f"[bold magenta]{title}[/bold magenta]",
                title_justify="left",
                box=None,
                show_header=False,
                pad_edge=False,
                padding=(0, 2),
                expand=False,
            )
            t.add_column("Field", style="bold cyan", width=22, no_wrap=True)
            t.add_column("Value", style="bright_white")
            return t

        # Section 1: Environment & Config
        t_env = create_section_table("ENVIRONMENT & CONFIG")
        t_env.add_row("Settings Module", settings_module)
        if debug_mode:
            t_env.add_row(
                "Debug Mode",
                "[bold yellow]Enabled (Development)[/bold yellow]  [yellow]● ON[/yellow]",
            )
        else:
            t_env.add_row(
                "Debug Mode",
                "[bold green]Disabled (Production)[/bold green]  [green]✔ OFF[/green]",
            )

        if secret_status == "Configured":
            t_env.add_row("Secret Key", "[green]✔ Secure / Configured[/green]")
        else:
            t_env.add_row(
                "Secret Key",
                "[bold yellow]⚠ Insecure / Default Placeholder[/bold yellow]",
            )

        t_env.add_row(
            "Allowed Hosts",
            ", ".join(allowed_hosts)
            if allowed_hosts
            else "[dim]None (wildcard/empty)[/dim]",
        )
        t_env.add_row("Timezone / TZ", f"{time_zone} (USE_TZ = {use_tz})")
        t_env.add_row("Language Code", language_code)
        console.print(t_env)
        console.print()

        # Section 2: Database & Migrations
        t_db = create_section_table("DATABASE & MIGRATIONS")
        t_db.add_row("Default Engine", db_engine)
        t_db.add_row("Database Name", str(db_name))
        if db_host and db_host != "localhost":
            t_db.add_row("Host / Port", f"{db_host}:{db_port}")
        if pending_migrations_count == 0:
            t_db.add_row(
                "Migrations",
                "[bold green]✔ All migrations applied (Up to date)[/bold green]",
            )
        elif pending_migrations_count is not None and pending_migrations_count > 0:
            t_db.add_row(
                "Migrations",
                f"[bold yellow]⚠ {pending_migrations_count} unapplied migration(s) pending[/bold yellow]",
            )
        else:
            t_db.add_row("Migrations", f"[dim]{migration_status_text}[/dim]")
        console.print(t_db)
        console.print()

        # Section 3: Applications & Architecture
        t_apps = create_section_table("APPLICATIONS & ARCHITECTURE")
        apps_summary = f"{total_apps} total ({len(django_apps)} Django Core, {len(third_party_apps)} Third-Party, {len(local_apps)} Local)"
        t_apps.add_row("Installed Apps", apps_summary)
        if local_apps:
            t_apps.add_row("Local Apps", ", ".join(local_apps))
        t_apps.add_row("Admin Theme", f"[bold cyan]{active_theme}[/bold cyan]")
        t_apps.add_row(
            "Registered Models",
            f"{total_models} models ({local_models_count} local app models)",
        )
        t_apps.add_row("Registered Routes", f"{total_routes} URL pattern endpoints")
        console.print(t_apps)
        console.print()

        # Section 4: Cache & Storage
        t_storage = create_section_table("CACHE, STORAGE & SERVICES")
        t_storage.add_row("Default Cache", cache_backend)
        t_storage.add_row(
            "Static URL / Root", f"{static_url}  [dim](Root: {static_root})[/dim]"
        )
        t_storage.add_row(
            "Media URL / Root", f"{media_url}  [dim](Root: {media_root})[/dim]"
        )
        t_storage.add_row("Email Backend", email_backend.split(".")[-1])
        console.print(t_storage)
        console.print()

        console.print(
            "[dim]Run 'python manage.py star_about --json' for machine-readable JSON output.[/dim]"
        )

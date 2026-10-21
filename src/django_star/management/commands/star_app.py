import re
from pathlib import Path
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django_star.console import console
from django_star.utils import (
    create_backup,
    ensure_include_imported,
    is_route_mounted,
    locate_settings_file,
    safe_insert_into_collection,
)

APP_URLS_TEMPLATE = """from django.urls import path
# from . import views

app_name = "{app_name}"

urlpatterns = [
    # path("", views.index, name="index"),
]
"""


class Command(BaseCommand):
    help = "Creates a new app and automatically wires it into settings.py, creates app/urls.py, and binds it to root urls.py"

    def add_arguments(self, parser):
        parser.add_argument(
            "app_name", type=str, help="Name of the new application (e.g. billing)"
        )
        parser.add_argument(
            "--dir",
            type=str,
            default=None,
            help="Target subdirectory to place the app (e.g. apps/ or src/)",
        )

    def handle(self, *args, **options):
        app_name = options["app_name"].lower()
        base_dir = Path(settings.BASE_DIR)
        sub_dir = options.get("dir")

        # Auto-detect 'apps/' folder if --dir was not passed explicitly
        if not sub_dir and (base_dir / "apps").is_dir():
            sub_dir = "apps"
            console.print(
                "[dim]ℹ Detected 'apps/' directory. Placing new app under 'apps/'.[/dim]"
            )

        if sub_dir:
            sub_dir_path = Path(sub_dir)
            target_parent = (base_dir / sub_dir_path).resolve()
            target_parent.mkdir(parents=True, exist_ok=True)
            (target_parent / "__init__.py").touch(exist_ok=True)
            target_dir = target_parent / app_name
            try:
                rel_parts = target_parent.relative_to(base_dir.resolve()).parts
                dir_prefix = ".".join(rel_parts)
                app_module = f"{dir_prefix}.{app_name}" if dir_prefix else app_name
            except ValueError:
                app_module = app_name
        else:
            target_dir = base_dir / app_name
            app_module = app_name

        # 1. Check if the app directory already exists
        if target_dir.exists():
            raise CommandError(f"Directory or app '{app_name}' already exists at {target_dir}.")

        # 2. Run Django's startapp
        console.print(f"[bold cyan]Scaffolding app '{app_name}'...[/bold cyan]")
        if sub_dir:
            call_command("startapp", app_name, str(target_dir))
        else:
            call_command("startapp", app_name)
        console.print(f"[green]✔ App directory created at {target_dir}[/green]")

        # If created in a subdirectory, patch apps.py so AppConfig.name matches full module path
        if app_module != app_name:
            apps_py = target_dir / "apps.py"
            if apps_py.exists():
                content = apps_py.read_text(encoding="utf-8")
                patched = re.sub(
                    rf'name\s*=\s*["\']{re.escape(app_name)}["\']',
                    f'name = "{app_module}"',
                    content,
                )
                apps_py.write_text(patched, encoding="utf-8")

        # 3. Create app/urls.py
        app_urls_file = target_dir / "urls.py"
        app_urls_file.write_text(
            APP_URLS_TEMPLATE.format(app_name=app_name), encoding="utf-8"
        )
        console.print(f"[green]✔ Created {app_name}/urls.py[/green]")

        # 4. Auto-wire INSTALLED_APPS in settings.py
        self._wire_settings(app_module)

        # 5. Auto-wire root urls.py
        self._wire_root_urls(app_name, app_module)

        console.print(
            f"[bold green]✔ App '{app_name}' created and fully wired! Ready to build.[/bold green]"
        )

    def _wire_settings(self, app_module: str):
        settings_path = self._locate_settings_file()
        if not settings_path:
            console.print(
                f"[bold yellow]⚠ Could not safely locate settings.py automatically.[/bold yellow]\n"
                f"[yellow]Please add '{app_module}' to INSTALLED_APPS manually.[/yellow]"
            )
            return

        content = settings_path.read_text(encoding="utf-8")
        if f"'{app_module}'" in content or f'"{app_module}"' in content:
            console.print(f"[yellow]⚠ '{app_module}' already in INSTALLED_APPS.[/yellow]")
            return

        create_backup(settings_path)

        updated = safe_insert_into_collection(
            content, "INSTALLED_APPS", f'    "{app_module}",\n'
        )

        if updated is not None:
            settings_path.write_text(updated, encoding="utf-8")
            console.print(
                f"[green]✔ Registered '{app_module}' into {settings_path.name}[/green]"
            )
        else:
            console.print(
                f"[bold yellow]⚠ Could not safely insert '{app_module}' into {settings_path.name} automatically.[/bold yellow]\n"
                f"[yellow]Please add '{app_module}' to INSTALLED_APPS manually.[/yellow]"
            )

    def _wire_root_urls(self, app_name: str, app_module: str):
        root_urlconf = getattr(settings, "ROOT_URLCONF", None)
        if not root_urlconf:
            console.print(
                f"[bold yellow]⚠ ROOT_URLCONF not found in settings.[/bold yellow]\n"
                f"[yellow]Please add route manually to urlpatterns:[/yellow]\n"
                f'    path("{app_name}/", include("{app_module}.urls")),'
            )
            return

        base_dir = Path(settings.BASE_DIR)
        root_urls_path = base_dir / (root_urlconf.replace(".", "/") + ".py")
        if not root_urls_path.exists():
            console.print(
                f"[bold yellow]⚠ Root url file not found at {root_urls_path}.[/bold yellow]\n"
                f"[yellow]Please add route manually to urlpatterns:[/yellow]\n"
                f'    path("{app_name}/", include("{app_module}.urls")),'
            )
            return

        content = root_urls_path.read_text(encoding="utf-8")

        # Check if route is already mounted in urlpatterns
        if is_route_mounted(content, app_module):
            return

        create_backup(root_urls_path)

        # 1. Ensure 'include' is imported
        content = ensure_include_imported(content)

        # 2. Append route to urlpatterns
        new_route = f'    path("{app_name}/", include("{app_module}.urls")),\n'
        updated = safe_insert_into_collection(content, "urlpatterns", new_route)

        if updated is not None:
            root_urls_path.write_text(updated, encoding="utf-8")
            console.print(
                f"[green]✔ Mounted '{app_name}/' routes in {root_urls_path.name}[/green]"
            )
        else:
            console.print(
                f"[bold yellow]⚠ Could not safely insert route into {root_urls_path.name} automatically.[/bold yellow]\n"
                f"[yellow]Please add the following route manually to urlpatterns:[/yellow]\n"
                f'    path("{app_name}/", include("{app_module}.urls")),'
            )

    @staticmethod
    def _locate_settings_file():
        settings_module = getattr(settings, "SETTINGS_MODULE", None)
        base_dir = getattr(settings, "BASE_DIR", None)
        return locate_settings_file(base_dir=base_dir, settings_module=settings_module)



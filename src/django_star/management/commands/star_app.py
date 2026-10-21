import re
from pathlib import Path
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from rich.console import Console

console = Console()

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

    def handle(self, *args, **options):
        app_name = options["app_name"].lower()
        base_dir = Path(settings.BASE_DIR)

        # 1. Check if the app directory already exists
        target_dir = base_dir / app_name
        if target_dir.exists():
            raise CommandError(f"Directory or app '{app_name}' already exists.")

        # 2. Run Django's startapp
        console.print(f"[bold cyan]Scaffolding app '{app_name}'...[/bold cyan]")
        call_command("startapp", app_name)
        console.print(f"[green]✔ App directory created at {target_dir}[/green]")

        # 3. Create app/urls.py
        app_urls_file = target_dir / "urls.py"
        app_urls_file.write_text(
            APP_URLS_TEMPLATE.format(app_name=app_name), encoding="utf-8"
        )
        console.print(f"[green]✔ Created {app_name}/urls.py[/green]")

        # 4. Auto-wire INSTALLED_APPS in settings.py
        self._wire_settings(app_name)

        # 5. Auto-wire root urls.py
        self._wire_root_urls(app_name)

        console.print(
            f"[bold green]✔ App '{app_name}' created and fully wired! Ready to build.[/bold green]"
        )

    def _wire_settings(self, app_name: str):
        settings_path = self._locate_settings_file()
        if not settings_path:
            console.print(
                "[yellow]⚠ Could not automatically locate settings.py. Add app manually to INSTALLED_APPS.[/yellow]"
            )
            return

        content = settings_path.read_text(encoding="utf-8")
        if f"'{app_name}'" in content or f'"{app_name}"' in content:
            console.print("[yellow]⚠ App already in INSTALLED_APPS.[/yellow]")
            return

        # Insert app before closing bracket of INSTALLED_APPS
        pattern = r"(INSTALLED_APPS\s*=\s*\[)([\s\S]*?)(\])"
        match = re.search(pattern, content)
        if match:
            head, body, tail = match.group(1), match.group(2), match.group(3)
            new_entry = f'    "{app_name}",\n'
            new_installed_apps = f"{head}{body}{new_entry}{tail}"
            content = (
                content[: match.start()] + new_installed_apps + content[match.end() :]
            )
            settings_path.write_text(content, encoding="utf-8")
            console.print(
                f"[green]✔ Registered '{app_name}' into {settings_path.name}[/green]"
            )
        else:
            console.print(
                "[yellow]⚠ Could not parse INSTALLED_APPS bracket list in settings.py[/yellow]"
            )

    def _wire_root_urls(self, app_name: str):
        root_urlconf = getattr(settings, "ROOT_URLCONF", None)
        if not root_urlconf:
            return

        base_dir = Path(settings.BASE_DIR)
        root_urls_path = base_dir / (root_urlconf.replace(".", "/") + ".py")
        if not root_urls_path.exists():
            return

        content = root_urls_path.read_text(encoding="utf-8")

        # 1. Ensure 'include' is imported
        if "include" not in content:
            content = re.sub(
                r"from django\.urls import ([\w\s,]+)",
                r"from django.urls import \1, include",
                content,
                count=1,
            )

        # 2. Append route to urlpatterns
        new_route = f'    path("{app_name}/", include("{app_name}.urls")),\n'
        if f'"{app_name}.urls"' in content:
            return

        pattern = r"(urlpatterns\s*=\s*\[)([\s\S]*?)(\])"
        match = re.search(pattern, content)
        if match:
            head, body, tail = match.group(1), match.group(2), match.group(3)
            new_urlpatterns = f"{head}{body}{new_route}{tail}"
            content = (
                content[: match.start()] + new_urlpatterns + content[match.end() :]
            )
            root_urls_path.write_text(content, encoding="utf-8")
            console.print(
                f"[green]✔ Mounted '{app_name}/' routes in {root_urls_path.name}[/green]"
            )

    @staticmethod
    def _locate_settings_file():
        settings_module = getattr(settings, "SETTINGS_MODULE", None)
        if settings_module:
            candidate = Path(settings.BASE_DIR) / (
                settings_module.replace(".", "/") + ".py"
            )
            if candidate.exists():
                return candidate
        return None

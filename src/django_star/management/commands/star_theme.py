import importlib.util
import re
import subprocess
import sys
from pathlib import Path
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from rich.panel import Panel
from rich.table import Table
from django_star.console import console
from django_star.utils import (
    create_backup,
    locate_root_urls_file,
    locate_settings_file,
    safe_insert_into_collection,
    update_theme_in_settings,
)

THEMES = {
    "grappelli": {
        "key": "grappelli",
        "rank": 1,
        "name": "django-grappelli",
        "title": "Django Grappelli",
        "pypi": "django-grappelli",
        "module": "grappelli",
        "apps": ["grappelli"],
        "desc": "Alternative admin with drop-in navigation & autocomplete",
        "needs_grappelli_urls": True,
    },
    "simpleui": {
        "key": "simpleui",
        "rank": 2,
        "name": "django-simpleui",
        "title": "Django SimpleUI",
        "pypi": "django-simpleui",
        "module": "simpleui",
        "apps": ["simpleui"],
        "desc": "Modern UI based on Vue.js and Element-UI",
    },
    "admin_interface": {
        "key": "admin_interface",
        "rank": 3,
        "name": "django-admin-interface",
        "title": "Django Admin Interface",
        "pypi": "django-admin-interface",
        "module": "admin_interface",
        "apps": ["admin_interface", "colorfield"],
        "desc": "Customizable theme with color picker & modal popups",
        "needs_x_frame_options": True,
        "needs_migrate": True,
    },
    "jazzmin": {
        "key": "jazzmin",
        "rank": 4,
        "name": "django-jazzmin",
        "title": "Django Jazzmin",
        "pypi": "django-jazzmin",
        "module": "jazzmin",
        "apps": ["jazzmin"],
        "desc": "Clean admin skin based on AdminLTE 3 and Bootstrap 4",
    },
}


ALL_THEME_APPS = {"grappelli", "simpleui", "admin_interface", "colorfield", "jazzmin"}

THEME_ALIASES = {
    "1": "grappelli",
    "grappelli": "grappelli",
    "django-grappelli": "grappelli",
    "django_grappelli": "grappelli",
    "2": "simpleui",
    "simpleui": "simpleui",
    "django-simpleui": "simpleui",
    "django_simpleui": "simpleui",
    "3": "admin_interface",
    "admin_interface": "admin_interface",
    "admin-interface": "admin_interface",
    "django-admin-interface": "admin_interface",
    "django_admin_interface": "admin_interface",
    "4": "jazzmin",
    "jazzmin": "jazzmin",
    "django-jazzmin": "jazzmin",
    "django_jazzmin": "jazzmin",
    "5": "default",
    "default": "default",
    "none": "default",
    "reset": "default",
    "remove": "default",
}


class Command(BaseCommand):
    help = (
        "Inspects, installs, and auto-configures popular Django admin themes "
        "(grappelli, simpleui, admin_interface, jazzmin) with one-click switching."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "theme",
            nargs="?",
            default=None,
            help="Target theme name (grappelli, simpleui, admin_interface, jazzmin) or rank number (1-5)",
        )
        parser.add_argument(
            "--remove",
            "--reset",
            action="store_true",
            help="Remove any active custom admin theme and restore stock Django admin",
        )
        parser.add_argument(
            "--no-pip",
            action="store_true",
            help="Skip automatic pip installation of the theme package",
        )
        parser.add_argument(
            "-l",
            "--list",
            action="store_true",
            help="List all recognized admin themes and current active status",
        )
        parser.add_argument(
            "-y",
            "--yes",
            action="store_true",
            help="Non-interactive mode (automatically proceed with defaults)",
        )

    def handle(self, *args, **options):
        settings_path = locate_settings_file()
        if not settings_path:
            raise CommandError(
                "Could not locate Django settings.py file. Ensure DJANGO_SETTINGS_MODULE is set."
            )

        settings_content = settings_path.read_text(encoding="utf-8")
        current_theme_key = self._detect_active_theme(settings_content)

        # 1. Handle --list flag
        if options["list"]:
            self._render_theme_table(current_theme_key)
            return

        # 2. Determine requested theme target
        theme_input = options["theme"]
        is_remove = options["remove"]

        if is_remove:
            target_key = "default"
        elif theme_input:
            normalized = theme_input.strip().lower()
            if normalized not in THEME_ALIASES:
                valid_options = ", ".join(list(THEMES.keys()) + ["default (5)"])
                raise CommandError(
                    f"Unknown theme '{theme_input}'. Valid options: {valid_options}"
                )
            target_key = THEME_ALIASES[normalized]
        else:
            # Interactive prompt
            self._render_theme_table(current_theme_key)
            if not sys.stdin.isatty():
                console.print(
                    "[dim]Non-interactive environment detected. Run 'python manage.py star_theme <theme_name>'[/dim]"
                )
                return

            try:
                console.print()
                choice = input("Select a theme [1-5] (or 'q' to quit): ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Operation cancelled.[/dim]")
                return

            if choice in ("q", "quit", "exit", ""):
                console.print("[dim]No changes made.[/dim]")
                return

            if choice not in THEME_ALIASES:
                console.print(
                    f"[bold red]Invalid selection '{choice}'. Please pick a number from 1 to 5.[/bold red]"
                )
                return

            target_key = THEME_ALIASES[choice]

        # 3. Handle 'default' / reset target
        if target_key == "default":
            self._reset_to_default(settings_path, settings_content, current_theme_key)
            return

        # 4. Handle specific theme target
        target_theme = THEMES[target_key]
        self._apply_theme(
            settings_path=settings_path,
            settings_content=settings_content,
            theme_info=target_theme,
            current_theme_key=current_theme_key,
            skip_pip=options["no_pip"],
        )

    def _render_theme_table(self, active_key: str | None):
        banner = (
            "[bold green]Django Star — Admin Theme Manager[/bold green]\n"
            "[dim]One-click theme switching for modern Django admin interfaces[/dim]"
        )
        console.print(Panel(banner, border_style="green", expand=False))

        table = Table(
            show_header=True,
            header_style="bold magenta",
            border_style="dim",
            show_lines=True,
            expand=True,
        )
        table.add_column("#", style="bold yellow", width=4, justify="center")
        table.add_column("Theme", style="bold cyan", min_width=24, no_wrap=True)
        table.add_column("Status", width=14, justify="center")
        table.add_column("Description", style="bright_white")

        for key, t in THEMES.items():
            is_active = (active_key == key)
            status_text = "[bold green]Active[/bold green]" if is_active else "[dim]-[/dim]"
            table.add_row(
                str(t["rank"]),
                t["name"],
                status_text,
                t["desc"],
            )

        is_default = (active_key is None)
        default_status = "[bold green]Active[/bold green]" if is_default else "[dim]-[/dim]"
        table.add_row(
            "5",
            "Default Django Admin",
            default_status,
            "Reset to standard stock Django admin (removes custom theme)",
        )

        console.print(table)
        console.print()
        console.print(
            "[dim]Usage: [/dim][bold white]python manage.py star_theme <name_or_number>[/bold white]\n"
            "[dim]Both full names (with 'django-') and short names are accepted:[/dim]\n"
            "  • [cyan]django-grappelli[/cyan] [dim]or[/dim] [cyan]grappelli[/cyan] [dim]or[/dim] [yellow]1[/yellow]\n"
            "  • [cyan]django-simpleui[/cyan] [dim]or[/dim] [cyan]simpleui[/cyan] [dim]or[/dim] [yellow]2[/yellow]\n"
            "  • [cyan]django-admin-interface[/cyan] [dim]or[/dim] [cyan]admin_interface[/cyan] [dim]or[/dim] [yellow]3[/yellow]\n"
            "  • [cyan]django-jazzmin[/cyan] [dim]or[/dim] [cyan]jazzmin[/cyan] [dim]or[/dim] [yellow]4[/yellow]\n"
            "  • [dim]Reset to stock admin:[/dim] [cyan]default[/cyan] [dim]or[/dim] [yellow]5[/yellow] [dim]or[/dim] [cyan]--remove[/cyan]"
        )




    def _detect_active_theme(self, content: str) -> str | None:
        """
        Determines which recognized theme is currently declared in settings.
        """
        for key, t in THEMES.items():
            # Check for the primary app name
            primary_app = t["apps"][0]
            if re.search(rf"['\"]{re.escape(primary_app)}['\"]", content):
                return key
        return None

    def _ensure_package_installed(self, theme_info: dict, skip_pip: bool = False) -> bool:
        """
        Verifies the theme package is installed in the active Python environment,
        installing it via pip if absent.
        """
        pypi_pkg = theme_info["pypi"]
        import_mod = theme_info["module"]

        if importlib.util.find_spec(import_mod) is not None:
            console.print(f"[green]✔ Package [white]{pypi_pkg}[/white] is installed.[/green]")
            return True

        if skip_pip:
            console.print(
                f"[yellow]⚠ Package [white]{pypi_pkg}[/white] is not installed. "
                f"Please run: pip install {pypi_pkg}[/yellow]"
            )
            return False

        console.print(f"[bold cyan]📦 Installing [white]{pypi_pkg}[/white] via pip...[/bold cyan]")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", pypi_pkg],
                capture_output=True,
                text=True,
                check=True,
            )
            console.print(f"[bold green]✔ Successfully installed [white]{pypi_pkg}[/white][/bold green]")
            return True
        except subprocess.CalledProcessError as e:
            console.print(
                f"[bold red]✖ Failed to install {pypi_pkg} automatically.[/bold red]\n"
                f"[dim]{e.stderr.strip()}[/dim]\n"
                f"[yellow]Please run 'pip install {pypi_pkg}' manually.[/yellow]"
            )
            return False

    def _reset_to_default(self, settings_path: Path, settings_content: str, current_theme_key: str | None):
        """
        Removes any recognized theme from settings.py and cleans up routes.
        """
        if current_theme_key is None:
            console.print("[bold yellow]ℹ Stock Django admin is already active (no theme installed).[/bold yellow]")
            return

        create_backup(settings_path)
        updated_settings, removed = update_theme_in_settings(
            settings_content, new_theme_apps=None, all_theme_apps=ALL_THEME_APPS
        )

        if updated_settings is not None:
            settings_path.write_text(updated_settings, encoding="utf-8")
            # Unwire grappelli urls if present
            self._wire_grappelli_urls(remove=True)
            console.print(
                f"[bold green]✔ Successfully removed [cyan]{THEMES[current_theme_key]['name']}[/cyan]. "
                f"Restored stock Django admin.[/bold green]"
            )
        else:
            console.print("[bold red]⚠ Could not safely update INSTALLED_APPS in settings.py.[/bold red]")

    def _apply_theme(
        self,
        settings_path: Path,
        settings_content: str,
        theme_info: dict,
        current_theme_key: str | None,
        skip_pip: bool = False,
    ):
        """
        Installs the theme package and configures settings.py / urls.py.
        """
        theme_key = theme_info["key"]
        theme_name = theme_info["name"]

        # 1. Check if already active
        if current_theme_key == theme_key:
            console.print(f"[bold yellow]ℹ Theme [cyan]{theme_name}[/cyan] is already active in INSTALLED_APPS.[/bold yellow]")
            self._ensure_package_installed(theme_info, skip_pip=skip_pip)
            return

        # 2. Install package if needed
        self._ensure_package_installed(theme_info, skip_pip=skip_pip)

        # 3. Create backup before editing settings.py
        create_backup(settings_path)

        # 4. Update INSTALLED_APPS (replaces previous theme apps)
        updated_settings, removed_apps = update_theme_in_settings(
            settings_content,
            new_theme_apps=theme_info["apps"],
            all_theme_apps=ALL_THEME_APPS,
        )

        if updated_settings is None:
            raise CommandError(f"Could not safely modify INSTALLED_APPS in {settings_path.name}.")

        # 5. Handle theme-specific settings
        if theme_info.get("needs_x_frame_options"):
            if "X_FRAME_OPTIONS" not in updated_settings:
                updated_settings += '\n# Required by django-admin-interface for modal popups\nX_FRAME_OPTIONS = "SAMEORIGIN"\n'
                console.print("[green]✔ Configured X_FRAME_OPTIONS = 'SAMEORIGIN' in settings.py[/green]")

        settings_path.write_text(updated_settings, encoding="utf-8")

        if removed_apps:
            console.print(
                f"[dim]ℹ Replaced previous theme app(s): {', '.join(removed_apps)}[/dim]"
            )

        console.print(
            f"[bold green]✔ Configured [cyan]{theme_name}[/cyan] in {settings_path.name} (placed before django.contrib.admin)[/bold green]"
        )

        # 6. Grappelli route wiring
        if theme_info.get("needs_grappelli_urls"):
            self._wire_grappelli_urls(remove=False)
        else:
            # Switching away from grappelli - clean up grappelli route
            self._wire_grappelli_urls(remove=True)

        # 7. Run migrations if theme has database models (e.g. admin_interface)
        if theme_info.get("needs_migrate"):
            migrated = False
            try:
                proc = subprocess.run(
                    [sys.executable, sys.argv[0], "migrate", "admin_interface", "--noinput"],
                    capture_output=True,
                    text=True,
                )
                if proc.returncode == 0:
                    console.print("[green]✔ Applied migrations for admin_interface[/green]")
                    migrated = True
            except Exception:
                pass

            if not migrated:
                try:
                    call_command("migrate", "admin_interface", interactive=False)
                    console.print("[green]✔ Applied migrations for admin_interface[/green]")
                    migrated = True
                except Exception:
                    pass

            if not migrated:
                console.print(
                    "[dim]ℹ Tip: Run 'python manage.py migrate' to initialize theme database tables.[/dim]"
                )


        console.print(
            f"\n[bold green]🌟 {theme_info['title']} is ready! Run [white]'python manage.py runserver'[/white] to view.[/bold green]"
        )

    def _wire_grappelli_urls(self, remove: bool = False) -> bool:
        """
        Mounts or unwires path('grappelli/', include('grappelli.urls')) in root urls.py.
        """
        urls_path = locate_root_urls_file()
        if not urls_path:
            return False

        content = urls_path.read_text(encoding="utf-8")

        if remove:
            if "grappelli.urls" not in content:
                return False
            create_backup(urls_path)
            lines = content.splitlines(keepends=True)
            cleaned = [line for line in lines if "grappelli.urls" not in line]
            urls_path.write_text("".join(cleaned), encoding="utf-8")
            console.print(f"[green]✔ Removed Grappelli routes from {urls_path.name}[/green]")
            return True

        # Adding grappelli route
        if "grappelli.urls" in content:
            return True

        create_backup(urls_path)

        # Ensure include is imported
        if "include" not in content:
            if re.search(r"from django\.urls import ([^\n\r]+)", content):
                content = re.sub(
                    r"from django\.urls import ([^\n\r]+)",
                    r"from django.urls import \1, include",
                    content,
                    count=1,
                )
            else:
                content = "from django.urls import include\n" + content

        grappelli_entry = '    path("grappelli/", include("grappelli.urls")),\n'

        admin_match = re.search(r"([ \t]*path\([\'\"]admin/?[^\n\r]*)", content)
        if admin_match:
            content = (
                content[: admin_match.start()]
                + grappelli_entry
                + content[admin_match.start() :]
            )
        else:
            updated = safe_insert_into_collection(content, "urlpatterns", grappelli_entry)
            if updated:
                content = updated

        urls_path.write_text(content, encoding="utf-8")
        console.print(f"[green]✔ Mounted Grappelli routes before admin in {urls_path.name}[/green]")
        return True

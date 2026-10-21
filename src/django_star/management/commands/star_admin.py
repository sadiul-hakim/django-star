from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.apps import apps
from django.db import models
from django_star.console import console
from django_star.utils import create_backup


class Command(BaseCommand):
    help = (
        "Inspects models in a Django app and auto-generates decorated ModelAdmin "
        "classes in admin.py with search_fields and list_filter."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "app_name", type=str, help="Target application label (e.g. blog)"
        )
        parser.add_argument(
            "model_name",
            nargs="?",
            default=None,
            help="Specific Model name (optional; if omitted, all models in the app are processed)",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Explicit flag to register all models in the target app",
        )

    def handle(self, *args, **options):
        app_label = options["app_name"]
        model_name = options["model_name"]
        process_all = options["all"] or (model_name is None)

        try:
            app_config = apps.get_app_config(app_label)
        except LookupError:
            raise CommandError(
                f"Application '{app_label}' not found in INSTALLED_APPS."
            )

        # Determine which models to inspect
        if process_all:
            target_models = list(app_config.get_models())
            if not target_models:
                console.print(
                    f"[bold yellow]No models found in '{app_label}'.[/bold yellow]"
                )
                return
        else:
            try:
                target_models = [apps.get_model(app_label, model_name)]
            except LookupError:
                raise CommandError(
                    f"Could not find model '{model_name}' in app '{app_label}'."
                )

        # Filter out abstract models and auto-created join tables
        filtered_models = []
        for model in target_models:
            if getattr(model._meta, "abstract", False):
                if not process_all:
                    console.print(
                        f"[bold yellow]⚠ Model '{model.__name__}' is abstract and cannot be registered in admin. Skipping.[/bold yellow]"
                    )
                continue
            if getattr(model._meta, "auto_created", False):
                if not process_all:
                    console.print(
                        f"[bold yellow]⚠ Model '{model.__name__}' is auto-created. Skipping.[/bold yellow]"
                    )
                continue
            filtered_models.append(model)
        target_models = filtered_models

        if not target_models:
            console.print(
                f"[bold yellow]No eligible models found in '{app_label}'.[/bold yellow]"
            )
            return

        admin_file = Path(app_config.path) / "admin.py"
        if not admin_file.exists():
            admin_file.write_text(
                "from django.contrib import admin\n", encoding="utf-8"
            )
        else:
            create_backup(admin_file)

        existing_content = admin_file.read_text(encoding="utf-8")

        generated_classes = []
        models_to_import = []
        new_code_blocks = []

        for model in target_models:
            admin_class_name = f"{model.__name__}Admin"

            # Check if this ModelAdmin is already registered or defined
            if (
                f"class {admin_class_name}" in existing_content
                or f"@admin.register({model.__name__})" in existing_content
            ):
                console.print(
                    f"[bold yellow]⚠ {admin_class_name} already registered in {admin_file.name}. Skipping.[/bold yellow]"
                )
                continue

            list_display = []
            list_filter = []
            search_fields = []

            for field in model._meta.get_fields():
                # Skip reverse relations and ManyToMany
                if not hasattr(field, "column") or field.many_to_many:
                    continue

                name = field.name
                list_display.append(name)

                if isinstance(field, (models.CharField, models.TextField)):
                    search_fields.append(name)
                elif isinstance(
                    field,
                    (
                        models.BooleanField,
                        models.DateField,
                        models.DateTimeField,
                        models.ForeignKey,
                    ),
                ):
                    list_filter.append(name)

            # Cap list_display at first 6 columns so the admin table doesn't overflow
            trimmed_display = list_display[:6] or ["id"]

            code_block = (
                f"\n\n@admin.register({model.__name__})\n"
                f"class {admin_class_name}(admin.ModelAdmin):\n"
                f"    list_display = {tuple(trimmed_display)}\n"
            )
            if search_fields:
                code_block += f"    search_fields = {tuple(search_fields[:3])}\n"
            if list_filter:
                code_block += f"    list_filter = {tuple(list_filter[:4])}\n"

            new_code_blocks.append(code_block)
            models_to_import.append(model.__name__)
            generated_classes.append(admin_class_name)

        if not new_code_blocks:
            console.print("[bold yellow]No new ModelAdmins to add.[/bold yellow]")
            return

        # Prepare imports
        final_content = existing_content

        if "from django.contrib import admin" not in final_content:
            final_content = "from django.contrib import admin\n" + final_content

        # Handle appending models to existing import or creating a new line
        import_stmt = f"from .models import {', '.join(models_to_import)}"
        if "from .models import" in final_content:
            # Append imported models to the existing import line if missing
            lines = final_content.splitlines()
            updated_lines = []
            for line in lines:
                if line.startswith("from .models import "):
                    existing_imports = [
                        item.strip()
                        for item in line.replace("from .models import ", "").split(",")
                    ]
                    merged = sorted(list(set(existing_imports + models_to_import)))
                    updated_lines.append(f"from .models import {', '.join(merged)}")
                else:
                    updated_lines.append(line)
            final_content = "\n".join(updated_lines)
        else:
            final_content = f"{import_stmt}\n" + final_content

        final_content += "".join(new_code_blocks) + "\n"
        admin_file.write_text(final_content, encoding="utf-8")

        for cls in generated_classes:
            console.print(f"[bold green]✔ Generated [cyan]{cls}[/cyan][/bold green]")
        console.print(
            f"[bold green]Successfully updated [white]{admin_file}[/white]![/bold green]"
        )

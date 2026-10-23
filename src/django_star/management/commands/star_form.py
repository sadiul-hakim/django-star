from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.apps import apps
from django_star.console import console
from django_star.utils import create_backup


class Command(BaseCommand):
    help = (
        "Inspects models in a Django app and auto-generates ModelForm "
        "classes in forms.py with Meta fields."
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

        # Determine models to inspect
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
                        f"[bold yellow]⚠ Model '{model.__name__}' is abstract and cannot be used in a form. Skipping.[/bold yellow]"
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

        forms_file = Path(app_config.path) / "forms.py"
        if not forms_file.exists():
            forms_file.write_text("from django import forms\n", encoding="utf-8")
        else:
            create_backup(forms_file)

        existing_content = forms_file.read_text(encoding="utf-8")

        generated_classes = []
        models_to_import = []
        new_code_blocks = []

        for model in target_models:
            form_class_name = f"{model.__name__}Form"
            model_cls_name = model.__name__

            # Check if this ModelForm already exists; skip if it does
            if f"class {form_class_name}" in existing_content:
                console.print(
                    f"[bold yellow]⚠ {form_class_name} already exists in {forms_file.name}. Skipping.[/bold yellow]"
                )
                continue

            # Gather form fields (excluding primary key 'id' and reverse relations/m2m)
            fields = [
                f.name
                for f in model._meta.get_fields()
                if hasattr(f, "column") and not f.many_to_many and f.name != "id"
            ]

            # Format fields tuple safely
            if len(fields) > 1:
                fields_str = str(tuple(fields))
            elif len(fields) == 1:
                fields_str = f'("{fields[0]}",)'
            else:
                fields_str = "__all__"

            code_block = (
                f"\n\nclass {form_class_name}(forms.ModelForm):\n"
                f"    class Meta:\n"
                f"        model = {model_cls_name}\n"
                f"        fields = {fields_str}\n"
            )

            new_code_blocks.append(code_block)
            models_to_import.append(model_cls_name)
            generated_classes.append(form_class_name)

        if not new_code_blocks:
            console.print("[bold yellow]No new ModelForms to add.[/bold yellow]")
            return

        # Prepare imports
        final_content = existing_content

        if "from django import forms" not in final_content:
            final_content = "from django import forms\n" + final_content

        # Handle appending models to existing import or creating a new line
        import_stmt = f"from .models import {', '.join(models_to_import)}"
        if "from .models import" in final_content:
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
        forms_file.write_text(final_content, encoding="utf-8")

        for cls in generated_classes:
            console.print(f"[bold green]✔ Generated [cyan]{cls}[/cyan][/bold green]")
        console.print(
            f"[bold green]Successfully updated [white]{forms_file}[/white]![/bold green]"
        )

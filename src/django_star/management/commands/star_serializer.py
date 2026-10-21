from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.apps import apps
from rich.console import Console

console = Console()


class Command(BaseCommand):
    help = (
        "Inspects Django models and auto-generates DRF ModelSerializer classes "
        "inside <app>/serializers.py."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "app_name", type=str, help="Target application label (e.g. blog)"
        )
        parser.add_argument(
            "model_name",
            nargs="?",
            default=None,
            help="Specific Model name (optional; if omitted or --all is used, all models are processed)",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Generate serializers for all models in the application",
        )

    def handle(self, *args, **options):
        app_label = options["app_name"].lower()
        model_name = options["model_name"]
        process_all = options["all"] or (model_name is None)

        try:
            app_config = apps.get_app_config(app_label)
        except LookupError:
            raise CommandError(
                f"Application '{app_label}' not found in INSTALLED_APPS."
            )

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

        target_file = Path(app_config.path) / "serializers.py"
        if not target_file.exists():
            target_file.write_text(
                "from rest_framework import serializers\n", encoding="utf-8"
            )

        existing_content = target_file.read_text(encoding="utf-8")
        generated_names = []
        models_to_import = []
        new_blocks = []

        for model in target_models:
            serializer_name = f"{model.__name__}Serializer"
            if f"class {serializer_name}(" in existing_content:
                console.print(
                    f"[bold yellow]⚠ {serializer_name} already exists in {target_file.name}. Skipping.[/bold yellow]"
                )
                continue

            field_names = []
            read_only_fields = []

            for field in model._meta.get_fields():
                if not hasattr(field, "column") and not field.many_to_many:
                    continue

                field_names.append(field.name)
                if (
                    field.primary_key
                    or getattr(field, "auto_now", False)
                    or getattr(field, "auto_now_add", False)
                    or field.name in ("created_at", "updated_at")
                ):
                    read_only_fields.append(field.name)

            block = (
                f"\n\nclass {serializer_name}(serializers.ModelSerializer):\n"
                f"    class Meta:\n"
                f"        model = {model.__name__}\n"
                f"        fields = {field_names}\n"
            )
            if read_only_fields:
                block += f"        read_only_fields = {tuple(read_only_fields)}\n"

            new_blocks.append(block)
            models_to_import.append(model.__name__)
            generated_names.append(serializer_name)

        if not new_blocks:
            console.print(
                "[bold yellow]No new DRF serializers to generate.[/bold yellow]"
            )
            return

        final_content = existing_content
        if "from rest_framework import serializers" not in final_content:
            final_content = "from rest_framework import serializers\n" + final_content

        # Cleanly merge model imports
        if "from .models import" in final_content:
            lines = final_content.splitlines()
            updated_lines = []
            for line in lines:
                if line.startswith("from .models import "):
                    existing = [
                        item.strip()
                        for item in line.replace("from .models import ", "").split(",")
                    ]
                    merged = sorted(list(set(existing + models_to_import)))
                    updated_lines.append(f"from .models import {', '.join(merged)}")
                else:
                    updated_lines.append(line)
            final_content = "\n".join(updated_lines)
        else:
            final_content = (
                f"from .models import {', '.join(sorted(set(models_to_import)))}\n"
                + final_content
            )

        final_content += "".join(new_blocks) + "\n"
        target_file.write_text(final_content, encoding="utf-8")

        for name in generated_names:
            console.print(
                f"[bold green]✔ Generated DRF Serializer [cyan]{name}[/cyan][/bold green]"
            )
        console.print(
            f"[bold green]Successfully updated [white]{target_file}[/white]![/bold green]"
        )

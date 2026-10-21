from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.apps import apps
from django.db import models
from rich.console import Console

console = Console()

FIELD_TYPE_MAP = {
    models.AutoField: "int",
    models.BigAutoField: "int",
    models.IntegerField: "int",
    models.SmallIntegerField: "int",
    models.BigIntegerField: "int",
    models.PositiveIntegerField: "int",
    models.CharField: "str",
    models.TextField: "str",
    models.SlugField: "str",
    models.EmailField: "str",
    models.URLField: "str",
    models.BooleanField: "bool",
    models.FloatField: "float",
    models.DecimalField: "Decimal",
    models.DateField: "date",
    models.DateTimeField: "datetime",
    models.TimeField: "time",
    models.UUIDField: "UUID",
    models.JSONField: "dict",
    models.ForeignKey: "int",
    models.OneToOneField: "int",
}


class Command(BaseCommand):
    help = (
        "Inspects Django models and auto-generates Django Ninja In and Out Schema "
        "classes inside <app>/schemas.py."
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
            help="Generate schemas for all models in the application",
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

        target_file = Path(app_config.path) / "schemas.py"
        needed_typing = set()

        if not target_file.exists():
            target_file.write_text("from ninja import Schema\n", encoding="utf-8")

        existing_content = target_file.read_text(encoding="utf-8")
        generated_names = []
        new_blocks = []

        for model in target_models:
            in_schema_name = f"{model.__name__}In"
            out_schema_name = f"{model.__name__}Out"

            in_fields = []
            out_fields = []

            for field in model._meta.get_fields():
                if not hasattr(field, "column") and not field.many_to_many:
                    continue

                py_type = "str"
                for field_cls, mapped_type in FIELD_TYPE_MAP.items():
                    if isinstance(field, field_cls):
                        py_type = mapped_type
                        break

                if py_type == "Decimal":
                    needed_typing.add("from decimal import Decimal")
                elif py_type in ("date", "datetime", "time"):
                    needed_typing.add(f"from datetime import {py_type}")
                elif py_type == "UUID":
                    needed_typing.add("from uuid import UUID")

                is_optional = getattr(field, "null", False) or getattr(
                    field, "blank", False
                )
                type_hint = f"{py_type} | None = None" if is_optional else py_type

                is_read_only = (
                    field.primary_key
                    or getattr(field, "auto_now", False)
                    or getattr(field, "auto_now_add", False)
                    or field.name in ("created_at", "updated_at")
                )

                out_fields.append(f"    {field.name}: {type_hint}")
                if not is_read_only:
                    in_fields.append(f"    {field.name}: {type_hint}")

            block = ""
            if f"class {in_schema_name}(" not in existing_content:
                in_lines = "\n".join(in_fields) if in_fields else "    pass"
                block += f"\n\nclass {in_schema_name}(Schema):\n{in_lines}\n"
                generated_names.append(in_schema_name)

            if f"class {out_schema_name}(" not in existing_content:
                out_lines = "\n".join(out_fields) if out_fields else "    pass"
                block += f"\n\nclass {out_schema_name}(Schema):\n{out_lines}\n"
                generated_names.append(out_schema_name)

            if block:
                new_blocks.append(block)

        if not new_blocks:
            console.print(
                "[bold yellow]No new Ninja schemas to generate.[/bold yellow]"
            )
            return

        final_content = existing_content
        for imp in sorted(needed_typing):
            if imp not in final_content:
                final_content = imp + "\n" + final_content

        if "from ninja import Schema" not in final_content:
            final_content = "from ninja import Schema\n" + final_content

        final_content += "".join(new_blocks) + "\n"
        target_file.write_text(final_content, encoding="utf-8")

        for name in generated_names:
            console.print(
                f"[bold green]✔ Generated Ninja Schema [cyan]{name}[/cyan][/bold green]"
            )
        console.print(
            f"[bold green]Successfully updated [white]{target_file}[/white]![/bold green]"
        )

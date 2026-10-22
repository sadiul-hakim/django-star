import re
from pathlib import Path

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import models
from rich.panel import Panel

from django_star.console import console
from django_star.utils import create_backup, safe_insert_into_collection


def pluralize_name(name: str) -> str:
    """Returns a simple pluralized form of a model or entity name."""
    lower = name.lower()
    if lower == "person":
        return "people"
    if lower == "child":
        return "children"
    if lower.endswith("y") and len(lower) > 1 and lower[-2] not in "aeiou":
        return lower[:-1] + "ies"
    if lower.endswith(("s", "x", "z", "ch", "sh", "o")):
        return lower + "es"
    return lower + "s"


def get_model_editable_fields(model) -> list[str]:
    """Returns list of editable field names for forms/views (excluding auto timestamps, PKs, M2M)."""
    fields = []
    for field in model._meta.get_fields():
        if not hasattr(field, "column"):
            continue
        if getattr(field, "primary_key", False):
            continue
        if getattr(field, "auto_now", False) or getattr(field, "auto_now_add", False):
            continue
        fields.append(field.name)
    return fields


def get_model_display_fields(model) -> list[str]:
    """Returns first 5 column field names for table display."""
    fields = []
    for field in model._meta.get_fields():
        if not hasattr(field, "column") or field.many_to_many:
            continue
        fields.append(field.name)
        if len(fields) >= 5:
            break
    return fields or ["id"]


class Command(BaseCommand):
    help = (
        "Auto-generates Django views (CRUD Class-Based Views, DRF ModelViewSets, or FBVs), "
        "wires URL patterns into <app>/urls.py, and scaffolds templates."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "app_name", type=str, help="Target application label (e.g. blog, main)"
        )
        parser.add_argument(
            "name",
            type=str,
            nargs="?",
            default=None,
            help="Model name (e.g. Post, Book) for CRUD or View name for single view",
        )
        parser.add_argument(
            "--crud",
            action="store_true",
            default=False,
            help="Generate full CRUD views (List, Detail, Create, Update, Delete)",
        )
        parser.add_argument(
            "--api",
            "--drf",
            action="store_true",
            default=False,
            help="Generate DRF ModelViewSet instead of standard Django CBVs",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            default=False,
            help="Generate CRUD views for all eligible models in the target app",
        )
        parser.add_argument(
            "--no-templates",
            action="store_true",
            default=False,
            help="Skip generating HTML templates for the views",
        )
        parser.add_argument(
            "--no-urls",
            action="store_true",
            default=False,
            help="Skip auto-wiring URL patterns into <app>/urls.py",
        )
        parser.add_argument(
            "--fbv",
            action="store_true",
            default=False,
            help="Generate a Function-Based View instead of a Class-Based View",
        )
        parser.add_argument(
            "--type",
            type=str,
            default=None,
            choices=["TemplateView", "ListView", "DetailView", "CreateView", "UpdateView", "DeleteView", "FormView"],
            help="Specify a single Class-Based View generic type",
        )
        parser.add_argument(
            "-f",
            "--force",
            action="store_true",
            default=False,
            help="Overwrite existing template files if they already exist",
        )

    def handle(self, *args, **options):
        app_label = options["app_name"].lower()
        target_name = options.get("name")
        process_all = options.get("all", False)
        is_api = options.get("api", False)
        no_templates = options.get("no_templates", False)
        no_urls = options.get("no_urls", False)
        is_fbv = options.get("fbv", False)
        view_type = options.get("type")
        force = options.get("force", False)

        try:
            app_config = apps.get_app_config(app_label)
        except LookupError:
            raise CommandError(f"Application '{app_label}' not found in INSTALLED_APPS.")

        app_dir = Path(app_config.path)
        views_path = app_dir / "views.py"
        urls_path = app_dir / "urls.py"

        # Check if target is a Model
        matched_model = None
        if target_name and not process_all:
            try:
                matched_model = apps.get_model(app_label, target_name)
            except LookupError:
                matched_model = None

        # Determine mode
        # Mode 1: Processing models for CRUD (either --all, or target matches a model, or --crud specified)
        if process_all or matched_model is not None or (options.get("crud") and not is_fbv and not view_type):
            if process_all:
                target_models = [
                    m for m in app_config.get_models()
                    if not getattr(m._meta, "abstract", False) and not getattr(m._meta, "auto_created", False)
                ]
                if not target_models:
                    console.print(f"[bold yellow]No eligible models found in '{app_label}'.[/bold yellow]")
                    return
            elif matched_model is not None:
                target_models = [matched_model]
            else:
                if not target_name:
                    raise CommandError("Please specify a model name or use --all.")
                raise CommandError(f"Could not find model '{target_name}' in app '{app_label}'.")

            for model in target_models:
                if is_api:
                    self._generate_api_crud(app_label, app_dir, views_path, urls_path, model, no_urls)
                else:
                    self._generate_standard_crud(
                        app_label, app_dir, views_path, urls_path, model, no_templates, no_urls, force
                    )
            return

        # Mode 2: Single Custom View (FBV or specific CBV)
        if not target_name:
            raise CommandError("Please provide a view or model name (e.g. python manage.py star_view blog Post).")

        self._generate_single_view(
            app_label, app_dir, views_path, urls_path, target_name, is_fbv, view_type, no_templates, no_urls, force
        )

    # -------------------------------------------------------------------------
    # Standard Django CRUD Generation (CBVs)
    # -------------------------------------------------------------------------
    def _generate_standard_crud(
        self,
        app_label: str,
        app_dir: Path,
        views_path: Path,
        urls_path: Path,
        model,
        no_templates: bool,
        no_urls: bool,
        force: bool,
    ):
        model_name = model.__name__
        model_lower = model_name.lower()
        plural_lower = pluralize_name(model_name)
        plural_title = pluralize_name(model_name).title()
        editable_fields = get_model_editable_fields(model)
        fields_repr = repr(editable_fields) if editable_fields else "'__all__'"

        # 1. Update views.py
        if not views_path.exists():
            views_path.write_text("from django.shortcuts import render\n", encoding="utf-8")
        else:
            create_backup(views_path)

        views_content = views_path.read_text(encoding="utf-8")
        views_to_generate = []
        crud_classes = [
            f"{model_name}ListView",
            f"{model_name}DetailView",
            f"{model_name}CreateView",
            f"{model_name}UpdateView",
            f"{model_name}DeleteView",
        ]

        # Check if already generated
        already_present = [cls for cls in crud_classes if f"class {cls}" in views_content]
        if len(already_present) == len(crud_classes):
            console.print(f"[bold yellow]⚠ CRUD views for '{model_name}' already exist in {views_path.name}.[/bold yellow]")
        else:
            # Prepare code block
            code_parts = []
            if f"class {model_name}ListView" not in views_content:
                code_parts.append(
                    f"class {model_name}ListView(ListView):\n"
                    f"    model = {model_name}\n"
                    f'    template_name = "{app_label}/{model_lower}_list.html"\n'
                    f'    context_object_name = "{plural_lower}"\n'
                    f"    paginate_by = 10\n"
                )
            if f"class {model_name}DetailView" not in views_content:
                code_parts.append(
                    f"class {model_name}DetailView(DetailView):\n"
                    f"    model = {model_name}\n"
                    f'    template_name = "{app_label}/{model_lower}_detail.html"\n'
                    f'    context_object_name = "{model_lower}"\n'
                )
            if f"class {model_name}CreateView" not in views_content:
                code_parts.append(
                    f"class {model_name}CreateView(CreateView):\n"
                    f"    model = {model_name}\n"
                    f'    template_name = "{app_label}/{model_lower}_form.html"\n'
                    f"    fields = {fields_repr}\n"
                    f'    success_url = reverse_lazy("{app_label}:{model_lower}_list")\n'
                )
            if f"class {model_name}UpdateView" not in views_content:
                code_parts.append(
                    f"class {model_name}UpdateView(UpdateView):\n"
                    f"    model = {model_name}\n"
                    f'    template_name = "{app_label}/{model_lower}_form.html"\n'
                    f"    fields = {fields_repr}\n"
                    f'    success_url = reverse_lazy("{app_label}:{model_lower}_list")\n'
                )
            if f"class {model_name}DeleteView" not in views_content:
                code_parts.append(
                    f"class {model_name}DeleteView(DeleteView):\n"
                    f"    model = {model_name}\n"
                    f'    template_name = "{app_label}/{model_lower}_confirm_delete.html"\n'
                    f'    success_url = reverse_lazy("{app_label}:{model_lower}_list")\n'
                )

            # Ensure imports
            import_block = ""
            if "from django.urls import reverse_lazy" not in views_content:
                import_block += "from django.urls import reverse_lazy\n"
            if "from django.views.generic import" not in views_content:
                import_block += "from django.views.generic import (\n    ListView,\n    DetailView,\n    CreateView,\n    UpdateView,\n    DeleteView,\n)\n"
            if f"from .models import" not in views_content and f"import {model_name}" not in views_content:
                import_block += f"from .models import {model_name}\n"
            elif f"{model_name}" not in views_content:
                # Add to existing .models import if possible
                views_content = re.sub(
                    r"(from\s+\.models\s+import\s+)([^\n]+)",
                    rf"\1{model_name}, \2",
                    views_content,
                )

            updated_views = views_content
            if import_block:
                updated_views = import_block + "\n" + updated_views

            updated_views = updated_views.rstrip() + "\n\n\n" + "\n\n".join(code_parts) + "\n"
            views_path.write_text(updated_views, encoding="utf-8")
            console.print(f"[bold green]✔ Generated CRUD views for '{model_name}' in {views_path.name}[/bold green]")

        # 2. Wire URLs
        if not no_urls:
            self._wire_crud_urls(app_label, urls_path, model_name, model_lower, plural_lower)

        # 3. Generate HTML Templates
        if not no_templates:
            self._scaffold_crud_templates(app_dir, app_label, model, model_name, model_lower, plural_lower, plural_title, force)

    # -------------------------------------------------------------------------
    # DRF API ModelViewSet Generation
    # -------------------------------------------------------------------------
    def _generate_api_crud(
        self,
        app_label: str,
        app_dir: Path,
        views_path: Path,
        urls_path: Path,
        model,
        no_urls: bool,
    ):
        model_name = model.__name__
        model_lower = model_name.lower()
        plural_lower = pluralize_name(model_name)
        viewset_name = f"{model_name}ViewSet"

        if not views_path.exists():
            views_path.write_text("", encoding="utf-8")
        else:
            create_backup(views_path)

        views_content = views_path.read_text(encoding="utf-8")
        if f"class {viewset_name}" in views_content:
            console.print(f"[bold yellow]⚠ {viewset_name} already exists in {views_path.name}.[/bold yellow]")
            return

        import_block = ""
        if "from rest_framework import viewsets" not in views_content:
            import_block += "from rest_framework import viewsets\n"
        if f"from .models import" not in views_content:
            import_block += f"from .models import {model_name}\n"
        if f"from .serializers import" not in views_content:
            import_block += f"from .serializers import {model_name}Serializer\n"

        viewset_code = (
            f"class {viewset_name}(viewsets.ModelViewSet):\n"
            f"    queryset = {model_name}.objects.all()\n"
            f"    serializer_class = {model_name}Serializer\n"
        )

        updated_views = views_content
        if import_block:
            updated_views = import_block + "\n" + updated_views
        updated_views = updated_views.rstrip() + "\n\n\n" + viewset_code + "\n"
        views_path.write_text(updated_views, encoding="utf-8")
        console.print(f"[bold green]✔ Generated {viewset_name} in {views_path.name}[/bold green]")

        # Wire DRF Router into urls.py
        if not no_urls:
            self._wire_api_urls(app_label, urls_path, model_name, plural_lower)

    # -------------------------------------------------------------------------
    # Single Custom View (FBV or CBV)
    # -------------------------------------------------------------------------
    def _generate_single_view(
        self,
        app_label: str,
        app_dir: Path,
        views_path: Path,
        urls_path: Path,
        view_name: str,
        is_fbv: bool,
        view_type: str | None,
        no_templates: bool,
        no_urls: bool,
        force: bool,
    ):
        if not views_path.exists():
            views_path.write_text("from django.shortcuts import render\n", encoding="utf-8")
        else:
            create_backup(views_path)

        views_content = views_path.read_text(encoding="utf-8")
        clean_name = re.sub(r"[^a-zA-Z0-9_]", "", view_name)

        if is_fbv:
            func_name = clean_name.lower()
            if f"def {func_name}(" in views_content:
                console.print(f"[bold yellow]⚠ View function '{func_name}' already exists in {views_path.name}.[/bold yellow]")
                return

            import_line = "from django.shortcuts import render\n" if "render" not in views_content else ""
            template_ref = f"{app_label}/{func_name}.html"
            code = (
                f"def {func_name}(request):\n"
                f'    return render(request, "{template_ref}", {{}})\n'
            )
            route_pattern = f'{func_name}/'
            route_handler = f"views.{func_name}"
            route_name = func_name
        else:
            # CBV mode
            cbv_type = view_type or "TemplateView"
            class_name = clean_name if clean_name.endswith("View") else f"{clean_name}View"
            stem = class_name[:-4].lower() if class_name.endswith("View") else class_name.lower()

            if f"class {class_name}" in views_content:
                console.print(f"[bold yellow]⚠ Class '{class_name}' already exists in {views_path.name}.[/bold yellow]")
                return

            import_line = f"from django.views.generic import {cbv_type}\n" if cbv_type not in views_content else ""
            template_ref = f"{app_label}/{stem}.html"
            code = (
                f"class {class_name}({cbv_type}):\n"
                f'    template_name = "{template_ref}"\n'
            )
            route_pattern = f'{stem}/'
            route_handler = f"views.{class_name}.as_view()"
            route_name = stem

        updated_views = views_content
        if import_line:
            updated_views = import_line + updated_views
        updated_views = updated_views.rstrip() + "\n\n\n" + code + "\n"
        views_path.write_text(updated_views, encoding="utf-8")
        console.print(f"[bold green]✔ Generated view '{clean_name}' in {views_path.name}[/bold green]")

        # Wire URL
        if not no_urls:
            self._wire_single_url(urls_path, route_pattern, route_handler, route_name)

        # Template
        if not no_templates:
            template_file = app_dir / "templates" / app_label / f"{route_name}.html"
            template_file.parent.mkdir(parents=True, exist_ok=True)
            if not template_file.exists() or force:
                template_file.write_text(
                    f"{{% extends 'base.html' %}}\n\n"
                    f"{{% block title %}}{route_name.title()}{{% endblock %}}\n\n"
                    f"{{% block content %}}\n"
                    f"<div class=\"{app_label}-{route_name}\">\n"
                    f"    <h1>{route_name.title()}</h1>\n"
                    f"    <p>Template generated by <strong>django-star</strong>.</p>\n"
                    f"</div>\n"
                    f"{{% endblock %}}\n",
                    encoding="utf-8",
                )
                console.print(f"[green]✔ Created template: {template_file}[/green]")

    # -------------------------------------------------------------------------
    # Route Wiring Helpers
    # -------------------------------------------------------------------------
    def _wire_crud_urls(self, app_label: str, urls_path: Path, model_name: str, model_lower: str, plural_lower: str):
        routes_to_add = [
            f'    path("{plural_lower}/", views.{model_name}ListView.as_view(), name="{model_lower}_list"),\n',
            f'    path("{plural_lower}/create/", views.{model_name}CreateView.as_view(), name="{model_lower}_create"),\n',
            f'    path("{plural_lower}/<int:pk>/", views.{model_name}DetailView.as_view(), name="{model_lower}_detail"),\n',
            f'    path("{plural_lower}/<int:pk>/edit/", views.{model_name}UpdateView.as_view(), name="{model_lower}_update"),\n',
            f'    path("{plural_lower}/<int:pk>/delete/", views.{model_name}DeleteView.as_view(), name="{model_lower}_delete"),\n',
        ]

        if not urls_path.exists():
            content = (
                "from django.urls import path\n"
                "from . import views\n\n"
                f'app_name = "{app_label}"\n\n'
                "urlpatterns = [\n"
                + "".join(routes_to_add)
                + "]\n"
            )
            urls_path.write_text(content, encoding="utf-8")
            console.print(f"[green]✔ Created {urls_path.name} with CRUD routes for '{model_name}'[/green]")
            return

        create_backup(urls_path)
        content = urls_path.read_text(encoding="utf-8")

        # Skip if routes already registered
        if f'"{model_lower}_list"' in content or f"'{model_lower}_list'" in content:
            console.print(f"[yellow]⚠ Routes for '{model_name}' already present in {urls_path.name}.[/yellow]")
            return

        # Ensure imports
        if "from . import views" not in content and "import views" not in content:
            content = "from . import views\n" + content
        if "from django.urls import path" not in content:
            content = "from django.urls import path\n" + content

        # Insert routes into urlpatterns
        new_routes_str = "".join(routes_to_add)
        updated = safe_insert_into_collection(content, "urlpatterns", new_routes_str)
        if updated is not None:
            urls_path.write_text(updated, encoding="utf-8")
            console.print(f"[green]✔ Wired CRUD routes for '{model_name}' into {urls_path.name}[/green]")
        else:
            console.print(f"[yellow]⚠ Could not automatically parse urlpatterns in {urls_path.name}. Please add routes manually.[/yellow]")

    def _wire_api_urls(self, app_label: str, urls_path: Path, model_name: str, plural_lower: str):
        register_line = f'router.register(r"{plural_lower}", views.{model_name}ViewSet, basename="{model_name.lower()}")\n'

        if not urls_path.exists():
            content = (
                "from django.urls import path, include\n"
                "from rest_framework.routers import DefaultRouter\n"
                "from . import views\n\n"
                f'app_name = "{app_label}"\n\n'
                "router = DefaultRouter()\n"
                + register_line
                + "\nurlpatterns = router.urls\n"
            )
            urls_path.write_text(content, encoding="utf-8")
            console.print(f"[green]✔ Created {urls_path.name} with DRF router for '{model_name}'[/green]")
            return

        create_backup(urls_path)
        content = urls_path.read_text(encoding="utf-8")

        if f'views.{model_name}ViewSet' in content:
            console.print(f"[yellow]⚠ Router for '{model_name}' already present in {urls_path.name}.[/yellow]")
            return

        if "DefaultRouter" not in content:
            content = "from rest_framework.routers import DefaultRouter\n" + content

        if "router = DefaultRouter()" not in content:
            content = content.rstrip() + "\n\nrouter = DefaultRouter()\n" + register_line + "\nurlpatterns += router.urls\n"
        else:
            # Insert register line right after router = DefaultRouter()
            content = re.sub(
                r"(router\s*=\s*DefaultRouter\(\)[^\n]*\n)",
                rf"\1{register_line}",
                content,
            )

        urls_path.write_text(content, encoding="utf-8")
        console.print(f"[green]✔ Registered '{model_name}ViewSet' in DRF router in {urls_path.name}[/green]")

    def _wire_single_url(self, urls_path: Path, route_pattern: str, handler: str, name: str):
        route_line = f'    path("{route_pattern}", {handler}, name="{name}"),\n'
        if not urls_path.exists():
            content = (
                "from django.urls import path\n"
                "from . import views\n\n"
                "urlpatterns = [\n"
                + route_line
                + "]\n"
            )
            urls_path.write_text(content, encoding="utf-8")
            console.print(f"[green]✔ Created {urls_path.name} with route '{name}'[/green]")
            return

        create_backup(urls_path)
        content = urls_path.read_text(encoding="utf-8")
        if f'"{name}"' in content or f"'{name}'" in content:
            return

        if "from . import views" not in content and "import views" not in content:
            content = "from . import views\n" + content

        updated = safe_insert_into_collection(content, "urlpatterns", route_line)
        if updated:
            urls_path.write_text(updated, encoding="utf-8")
            console.print(f"[green]✔ Wired route '{name}' into {urls_path.name}[/green]")

    # -------------------------------------------------------------------------
    # Template Scaffolding Helpers
    # -------------------------------------------------------------------------
    def _scaffold_crud_templates(
        self,
        app_dir: Path,
        app_label: str,
        model,
        model_name: str,
        model_lower: str,
        plural_lower: str,
        plural_title: str,
        force: bool,
    ):
        templates_dir = app_dir / "templates" / app_label
        templates_dir.mkdir(parents=True, exist_ok=True)

        display_fields = get_model_display_fields(model)
        headers_html = "\n".join(f"                <th>{f.replace('_', ' ').title()}</th>" for f in display_fields)
        cells_html = "\n".join(f"                <td>{{{{ item.{f} }}}}</td>" for f in display_fields)
        detail_rows_html = "\n".join(
            f"        <tr><th>{f.replace('_', ' ').title()}</th><td>{{{{ object.{f} }}}}</td></tr>"
            for f in display_fields
        )

        templates_map = {
            f"{model_lower}_list.html": (
                f"{{% extends 'base.html' %}}\n\n"
                f"{{% block title %}}{plural_title}{{% endblock %}}\n\n"
                f"{{% block content %}}\n"
                f"<div class=\"{app_label}-{model_lower}-list\">\n"
                f"    <div style=\"display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;\">\n"
                f"        <h1>{plural_title}</h1>\n"
                f"        <a href=\"{{% url '{app_label}:{model_lower}_create' %}}\" class=\"btn btn-primary\">+ Add {model_name}</a>\n"
                f"    </div>\n\n"
                f"    {{% if {plural_lower} %}}\n"
                f"    <table border=\"1\" cellpadding=\"8\" cellspacing=\"0\" style=\"width: 100%; border-collapse: collapse;\">\n"
                f"        <thead>\n"
                f"            <tr>\n"
                f"{headers_html}\n"
                f"                <th>Actions</th>\n"
                f"            </tr>\n"
                f"        </thead>\n"
                f"        <tbody>\n"
                f"            {{% for item in {plural_lower} %}}\n"
                f"            <tr>\n"
                f"{cells_html}\n"
                f"                <td>\n"
                f"                    <a href=\"{{% url '{app_label}:{model_lower}_detail' item.pk %}}\">View</a> |\n"
                f"                    <a href=\"{{% url '{app_label}:{model_lower}_update' item.pk %}}\">Edit</a> |\n"
                f"                    <a href=\"{{% url '{app_label}:{model_lower}_delete' item.pk %}}\">Delete</a>\n"
                f"                </td>\n"
                f"            </tr>\n"
                f"            {{% endfor %}}\n"
                f"        </tbody>\n"
                f"    </table>\n\n"
                f"    {{% if is_paginated %}}\n"
                f"    <div style=\"margin-top: 1rem;\">\n"
                f"        {{% if page_obj.has_previous %}}<a href=\"?page={{{{ page_obj.previous_page_number }}}}\">Previous</a>{{% endif %}}\n"
                f"        <span>Page {{{{ page_obj.number }}}} of {{{{ page_obj.paginator.num_pages }}}}</span>\n"
                f"        {{% if page_obj.has_next %}}<a href=\"?page={{{{ page_obj.next_page_number }}}}\">Next</a>{{% endif %}}\n"
                f"    </div>\n"
                f"    {{% endif %}}\n\n"
                f"    {{% else %}}\n"
                f"    <p>No {plural_lower} found. <a href=\"{{% url '{app_label}:{model_lower}_create' %}}\">Create the first one</a>.</p>\n"
                f"    {{% endif %}}\n"
                f"</div>\n"
                f"{{% endblock %}}\n"
            ),
            f"{model_lower}_detail.html": (
                f"{{% extends 'base.html' %}}\n\n"
                f"{{% block title %}}{model_name} Detail{{% endblock %}}\n\n"
                f"{{% block content %}}\n"
                f"<div class=\"{app_label}-{model_lower}-detail\">\n"
                f"    <h1>{model_name} Details</h1>\n"
                f"    <table border=\"1\" cellpadding=\"8\" cellspacing=\"0\" style=\"margin-bottom: 1.5rem;\">\n"
                f"{detail_rows_html}\n"
                f"    </table>\n"
                f"    <div>\n"
                f"        <a href=\"{{% url '{app_label}:{model_lower}_update' object.pk %}}\">Edit</a> |\n"
                f"        <a href=\"{{% url '{app_label}:{model_lower}_delete' object.pk %}}\">Delete</a> |\n"
                f"        <a href=\"{{% url '{app_label}:{model_lower}_list' %}}\">Back to List</a>\n"
                f"    </div>\n"
                f"</div>\n"
                f"{{% endblock %}}\n"
            ),
            f"{model_lower}_form.html": (
                f"{{% extends 'base.html' %}}\n\n"
                f"{{% block title %}}{{{{ object|yesno:'Edit,Create' }}}} {model_name}{{% endblock %}}\n\n"
                f"{{% block content %}}\n"
                f"<div class=\"{app_label}-{model_lower}-form\">\n"
                f"    <h1>{{% if object %}}Edit {model_name}{{% else %}}Create {model_name}{{% endif %}}</h1>\n"
                f"    <form method=\"post\">\n"
                f"        {{% csrf_token %}}\n"
                f"        {{{{ form.as_p }}}}\n"
                f"        <button type=\"submit\">Save</button>\n"
                f"        <a href=\"{{% url '{app_label}:{model_lower}_list' %}}\">Cancel</a>\n"
                f"    </form>\n"
                f"</div>\n"
                f"{{% endblock %}}\n"
            ),
            f"{model_lower}_confirm_delete.html": (
                f"{{% extends 'base.html' %}}\n\n"
                f"{{% block title %}}Delete {model_name}{{% endblock %}}\n\n"
                f"{{% block content %}}\n"
                f"<div class=\"{app_label}-{model_lower}-delete\">\n"
                f"    <h1>Delete {model_name}</h1>\n"
                f"    <p>Are you sure you want to delete <strong>{{{{ object }}}}</strong>?</p>\n"
                f"    <form method=\"post\">\n"
                f"        {{% csrf_token %}}\n"
                f"        <button type=\"submit\" style=\"color: red;\">Yes, Delete</button>\n"
                f"        <a href=\"{{% url '{app_label}:{model_lower}_list' %}}\">Cancel</a>\n"
                f"    </form>\n"
                f"</div>\n"
                f"{{% endblock %}}\n"
            ),
        }

        for fname, content in templates_map.items():
            tpl_path = templates_dir / fname
            if tpl_path.exists() and not force:
                console.print(f"[dim]ℹ Template already exists: {tpl_path.name} (use --force to overwrite)[/dim]")
                continue
            tpl_path.write_text(content, encoding="utf-8")
            console.print(f"[green]✔ Created template: {tpl_path.name}[/green]")

# django-star 🌟

Artisan-style developer automation, route inspection, and code generators for Django.

`django-star` eliminates repetitive boilerplate in Django projects. It automates tedious multi-file tasks such as introspecting models to generate rich `ModelAdmin` classes, zero-wiring app creation, interactive route visualizers, service layer architectures, DRF serializers, Django Ninja schemas, and custom management commands.

---

## Features

* **Interactive Command Catalog (`star`)**: Built-in dashboard listing all available tools, syntax, and categories.
* **Project Health & Environment Dashboard (`star_about`)**: Artisan-style overview of system configuration, database engine, unapplied migrations, app breakdown, active theme, and storage with optional `--json` export.
* **Admin Theme Manager (`star_theme`)**: One-click installation and configuration for top Django admin themes (`django-grappelli`, `django-simpleui`, `django-admin-interface`, `django-jazzmin`) with automatic dependency installation, settings.py injection, route management, and seamless theme switching.
* **Automated `admin.py` Generation (`star_admin`)**: Reflects on Django ORM models and automatically configures `list_display`, `search_fields`, and `list_filter` for single models or an entire app at once.

* **Route Inspector (`star_urls`)**: Interactive terminal table displaying all registered URL patterns, callback views, and namespaces with search filters and app exclusion (`-e`).
* **Zero-Wiring App Generator (`star_app`)**: Scaffolds a new app, registers it in `settings.py` (`INSTALLED_APPS`), creates `urls.py`, and mounts it directly into root `urls.py`.
* **Existing App Route & Template Wiring (`star_route`)**: Wires up pre-existing apps by generating `urls.py`, default HTML templates, and mounting routes in root `urls.py`.
* **DRF Serializer Generator (`star_serializer`)**: Inspects ORM models and generates `ModelSerializer` classes with auto-detected fields and read-only timestamps.
* **Django Ninja Schema Generator (`star_schema`)**: Maps ORM model field types to typed Python type hints, generating `In` and `Out` Pydantic `Schema` definitions.
* **Service Layer Scaffolding (`star_service`)**: Instantly creates `<app>/services/<name>_service.py` files with atomic transaction wrappers.
* **Management Command Generator (`star_command`)**: Generates nested `management/commands/` directories and runnable `BaseCommand` skeletons in a single step.
* **Template Scaffolding (`star_template`)**: Creates namespaced templates with smart root layout detection (`base`/`layout`), template inheritance (`-e`), HTML5 boilerplates (`--html5`), and flat options (`--flat`).
* **Terminal Styling**: Powered by [Rich](https://github.com/Textualize/rich) for formatted terminal feedback.

---

## Installation

### From GitHub

Install directly into your active virtual environment:

```bash
pip install git+https://github.com/sadiul-hakim/django-star.git

# With optional framework extras:
pip install "django-star[drf] @ git+https://github.com/sadiul-hakim/django-star.git"
pip install "django-star[ninja] @ git+https://github.com/sadiul-hakim/django-star.git"
pip install "django-star[all] @ git+https://github.com/sadiul-hakim/django-star.git"
```

Or add it to your `requirements.txt`:

```text
django-star @ git+https://github.com/sadiul-hakim/django-star.git@main
```

### Local Development (Editable Mode)

```bash
pip install -e /path/to/django-star

# With optional framework extras:
pip install -e "/path/to/django-star[all]"
```

---

## Configuration

Add `django_star` to your `INSTALLED_APPS` inside `settings.py`:

```python
INSTALLED_APPS = [
    # Core Django apps...
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party apps
    "django_star",
    # Your local apps...
]
```

---

## Usage

### 0. Command Catalog & Help Dashboard

View all available `django-star` commands and flags:

```bash
python manage.py star
```

---

### 1. Project Health & Environment Dashboard (`star_about`)

Inspect your live Django configuration, database health, migration status, and application architecture in an interactive terminal dashboard:

```bash
# Display terminal health dashboard
python manage.py star_about

# Output machine-readable metrics as JSON
python manage.py star_about --json
```

---

### 2. Route Inspector (`star_urls`)

Display all project routes in a clean, colored table:

```bash
# View all routes
python manage.py star_urls

# Filter routes by keyword
python manage.py star_urls api

# Exclude verbose/internal apps (e.g. admin or debug toolbar)
python manage.py star_urls -e admin __debug__

```

---

### 3. Zero-Wiring App Generator (`star_app`)

Runs `startapp`, registers the app in `settings.py`, generates `urls.py`, and mounts the route inside root `urls.py` in one step. Automatically creates `.bak` backups before modifying any files:

```bash
# Standard layout (app created at project root)
python manage.py star_app billing

# Custom subdirectory layout (e.g. apps/billing or src/billing)
python manage.py star_app billing --dir apps/
```

---

### 4. Existing App Route & Template Wiring (`star_route`)

For existing apps: generates `<app>/urls.py`, creates `templates/<app>/index.html`, and mounts the route into root `urls.py`:

```bash
# Standard wiring
python manage.py star_route blog

# Custom URL route prefix
python manage.py star_route accounts --prefix api/v1/auth

# Headless / API-only (skip template generation)
python manage.py star_route payments --no-template

```

---

### 5. Auto-generate `ModelAdmin` (`star_admin`)

Inspects models via runtime ORM reflection and appends configured `@admin.register` blocks to `<app>/admin.py`:

```bash
# Register a single model
python manage.py star_admin blog Post

# Scan and register ALL models in the app
python manage.py star_admin blog

```

---

### 6. Admin Theme Manager (`star_theme`)

Instantly switch between popular Django admin themes without manually touching `admin.py`. Automatically handles `pip install`, `INSTALLED_APPS` replacement, `X_FRAME_OPTIONS`, route wiring, and database migrations:

```bash
# Interactive selection dashboard
python manage.py star_theme

# View active theme status
python manage.py star_theme --list

# Switch directly by name or rank number
python manage.py star_theme jazzmin
python manage.py star_theme simpleui
python manage.py star_theme grappelli
python manage.py star_theme admin_interface

# Reset to default stock Django admin
python manage.py star_theme --remove
```

---

### 7. DRF Serializer Generator (`star_serializer`)

Auto-generates `serializers.ModelSerializer` classes inside `<app>/serializers.py`:

```bash
# Generate for a single model
python manage.py star_serializer blog Post

# Generate for ALL models in the app
python manage.py star_serializer blog

```

---

### 8. Django Ninja Schema Generator (`star_schema`)

Maps ORM fields to Python types and creates `ModelIn` and `ModelOut` schemas in `<app>/schemas.py`:

```bash
# Generate for a single model
python manage.py star_schema blog Post

# Generate for ALL models in the app
python manage.py star_schema blog

```

---

### 9. Scaffold a Service Layer (`star_service`)

Creates a service module inside `<app>/services/<name>_service.py` wrapped with `@transaction.atomic`:

```bash
python manage.py star_service billing process_payment

```

---

### 10. Scaffold a Management Command (`star_command`)


Sets up nested directory paths (`<app>/management/commands/`), `__init__.py` files, and a ready-to-run command skeleton:

```bash
python manage.py star_command core sync_data

```

---

### 11. Template Scaffolding (`star_template`)

Generates templates inside your app following Django's official **template namespacing** standard (`<app>/templates/<app>/<name>.html`), preventing naming collisions across installed applications:

```bash
python manage.py star_template <app_name> <template_name> [options]
```

#### Smart Template Behavior

* **Intelligent Root Layout Detection**:
  If the template is named `base` or `layout` (e.g. `python manage.py star_template website base`), `star_template` automatically detects that it is your root layout and generates a full HTML5 boilerplate with semantic tags (`<header>`, `<main>`, `<footer>`), viewport meta, and template blocks (`title`, `extra_css`, `content`, `extra_js`) without needing `--html5`.
* **Standard Component Fragments**:
  Regular templates (e.g. `page1`, `detail`) default to modular component sections wrapped in `{% block content %}`.
* **Template Inheritance (`-e` / `--extends`)**:
  Inherits from another template. Automatically resolves template names without `.html` (e.g. `-e base` $\rightarrow$ `{% extends "base.html" %}`):
  ```bash
  python manage.py star_template website page2 -e base
  ```
* **Explicit HTML5 Boilerplate (`--html5`)**:
  Forces complete HTML5 document generation on any template name:
  ```bash
  python manage.py star_template website landing --html5
  ```
* **Flat Templates (`--flat`)**:
  Drops the template directly into `<app>/templates/<template>.html` without the app-named subfolder:
  ```bash
  python manage.py star_template website footer --flat
  ```
* **Custom Block Name (`--block`)**:
  Overrides the primary block name (defaults to `content`):
  ```bash
  python manage.py star_template website profile -e base --block main_content
  ```
* **Overwrite Protection (`-f` / `--force`)**:
  Skips existing templates by default to protect your code. Use `-f` or `--force` to overwrite.

---

## License

MIT
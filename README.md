# django-star 🌟

Artisan-style developer automation, route inspection, and code generators for Django.

`django-star` eliminates repetitive boilerplate in Django projects. It automates tedious multi-file tasks such as introspecting models to generate rich `ModelAdmin` classes, zero-wiring app creation, URL visualizers, service layer architectures, and custom management commands without manual folder wiring.

---

## Features

- **Interactive Command Catalog (`star`)**: Built-in dashboard listing all available generator tools and argument flags.
- **Automated `admin.py` Generation (`star_admin`)**: Reflects on existing Django ORM models and automatically configures `list_display`, `search_fields`, and `list_filter` for a single model or an entire app at once.
- **Route Inspector (`star_urls`)**: Interactive terminal table displaying all registered URL patterns, callback views, and namespaces with app-exclusion and search filters.
- **Zero-Wiring App Generator (`star_app`)**: Scaffolds a new app and automatically updates `settings.py` (`INSTALLED_APPS`), creates `urls.py`, and binds it to the root URLconf.
- **Existing App Route Scaffolder (`star_route`)**: Wires up pre-existing apps by generating `urls.py`, templates, and mounting routes in the root URLconf.
- **Service Layer Scaffolding (`star_service`)**: Instantly creates `<app>/services/<name>_service.py` files with atomic transaction wrappers.
- **Management Command Generator (`star_command`)**: Generates nested `management/commands/` directories and runnable `BaseCommand` skeletons in a single step.
- **Terminal Styling**: Powered by [Rich](https://github.com/Textualize/rich) for formatted terminal feedback.

---

## Installation

### From GitHub

Install directly into your active virtual environment:

```bash
pip install git+https://github.com/sadiul-hakim/django-star.git

```

Or add it to your `requirements.txt`:

```text
django-star @ git+https://github.com/sadiul-hakim/django-star.git

```

### Local Development (Editable Mode)

```bash
pip install -e /path/to/django-star

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

View all available `django-star` commands, syntax, and categories in a clean terminal panel:

```bash
python manage.py star

```

---

### 1. Route Inspector (`star_urls`)

Display all project routes in a clean formatted table (similar to Laravel's `route:list`):

```bash
# View all routes
python manage.py star_urls

# Filter routes by keyword
python manage.py star_urls api

# Exclude verbose/internal apps (e.g. admin or debug toolbar)
python manage.py star_urls -e admin __debug__

```

---

### 2. Zero-Wiring App Generator (`star_app`)

Runs `startapp`, registers the app in `settings.py`, generates `urls.py`, and mounts the route inside the root URLconf in one step:

```bash
python manage.py star_app billing

```

---

### 3. Existing App Route & Template Wiring (`star_route`)

For apps created without `star_app`: generates `<app>/urls.py`, creates standard `templates/<app>/index.html`, and mounts the route into the root `urls.py`:

```bash
# Standard wiring
python manage.py star_route blog

# Custom URL route prefix
python manage.py star_route accounts --prefix api/v1/auth

# Headless / API-only (skip template generation)
python manage.py star_route payments --no-template

```

---

### 4. Auto-generate `ModelAdmin` (`star_admin`)

Inspects your models using runtime ORM reflection and appends configured `@admin.register` blocks to `<app>/admin.py`:

```bash
# Register a single model
python manage.py star_admin blog Post

# Scan and register ALL models in the app
python manage.py star_admin blog

```

---

### 5. Scaffold a Service Layer (`star_service`)

Creates an isolated service class inside `<app>/services/<name>_service.py` wrapped with `@transaction.atomic`:

```bash
python manage.py star_service billing process_payment

```

---

### 6. Scaffold a Management Command (`star_command`)

Sets up the necessary directory tree (`<app>/management/commands/`), `__init__.py` files, and a ready-to-run command skeleton:

```bash
python manage.py star_command core sync_data

```

---

## License

MIT

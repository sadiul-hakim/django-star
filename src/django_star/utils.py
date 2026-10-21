import ast
import re
from pathlib import Path
from django.conf import settings
from django_star.console import console


def create_backup(file_path: Path) -> Path | None:
    """
    Creates a .bak backup of the specified file before modification.
    """
    try:
        backup_path = file_path.with_name(f"{file_path.name}.bak")
        backup_path.write_text(file_path.read_text(encoding="utf-8"), encoding="utf-8")
        return backup_path
    except Exception as e:
        console.print(f"[dim]⚠ Could not create backup for {file_path.name}: {e}[/dim]")
        return None


def safe_insert_into_collection(content: str, variable_name: str, new_entry: str) -> str | None:
    """
    Safely inserts new_entry into a list [...] or tuple (...) variable definition
    by tracking delimiter depth to handle nested calls (like path()) without corrupting code.
    Returns the updated content string, or None if the variable could not be safely parsed.
    """
    pattern = rf"({variable_name}\s*=\s*(\[|\())"
    match = re.search(pattern, content)
    if not match:
        return None

    open_char = match.group(2)
    close_char = "]" if open_char == "[" else ")"
    start_idx = match.end() - 1
    depth = 0
    close_idx = None

    for i in range(start_idx, len(content)):
        char = content[i]
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                close_idx = i
                break

    if close_idx is None:
        return None

    head = content[: match.end()]
    body = content[match.end() : close_idx]
    tail = content[close_idx:]

    entry = new_entry
    if body and not body.endswith("\n"):
        entry = "\n" + entry

    return f"{head}{body}{entry}{tail}"


def locate_settings_file(
    base_dir: Path | str | None = None, settings_module: str | None = None
) -> Path | None:
    """
    Discovers the active Django settings file (e.g. settings.py, config/settings/base.py).
    """
    if settings_module is None:
        settings_module = getattr(settings, "SETTINGS_MODULE", None)
    if not settings_module:
        return None

    if base_dir is None:
        base_dir = getattr(settings, "BASE_DIR", None)
    if not base_dir:
        return None

    base_dir = Path(base_dir)
    module_rel_path = settings_module.replace(".", "/")

    # 1. Direct file match: e.g. config/settings.py
    candidate = base_dir / f"{module_rel_path}.py"
    if candidate.exists():
        if "INSTALLED_APPS" in candidate.read_text(encoding="utf-8"):
            return candidate
        parent_dir = candidate.parent
        for fname in ["base.py", "common.py", "__init__.py"]:
            sf = parent_dir / fname
            if sf.exists() and "INSTALLED_APPS" in sf.read_text(encoding="utf-8"):
                return sf
        return candidate

    # 2. Package / directory match: e.g. config/settings/
    dir_candidate = base_dir / module_rel_path
    if dir_candidate.is_dir():
        for fname in ["base.py", "common.py", "__init__.py", "local.py", "dev.py"]:
            sf = dir_candidate / fname
            if sf.exists() and "INSTALLED_APPS" in sf.read_text(encoding="utf-8"):
                return sf
        for py_file in dir_candidate.glob("*.py"):
            if "INSTALLED_APPS" in py_file.read_text(encoding="utf-8"):
                return py_file

    return None



def locate_root_urls_file() -> Path | None:
    """
    Discovers the project's root urls.py file from ROOT_URLCONF.
    """
    root_urlconf = getattr(settings, "ROOT_URLCONF", None)
    if not root_urlconf:
        return None
    base_dir = Path(settings.BASE_DIR)
    root_urls_path = base_dir / (root_urlconf.replace(".", "/") + ".py")
    if root_urls_path.exists():
        return root_urls_path
    return None


def update_theme_in_settings(
    content: str,
    new_theme_apps: list[str] | None,
    all_theme_apps: set[str],
) -> tuple[str | None, list[str]]:
    """
    Safely replaces or removes third-party admin theme apps in INSTALLED_APPS.
    The new theme apps are positioned immediately before 'django.contrib.admin'.
    Returns (updated_content, list_of_removed_apps).
    """
    pattern = r"(INSTALLED_APPS\s*=\s*(\[|\())"
    match = re.search(pattern, content)
    if not match:
        return None, []

    open_char = match.group(2)
    close_char = "]" if open_char == "[" else ")"
    start_idx = match.end() - 1
    depth = 0
    close_idx = None

    for i in range(start_idx, len(content)):
        char = content[i]
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                close_idx = i
                break

    if close_idx is None:
        return None, []

    head = content[: match.end()]
    body = content[match.end() : close_idx]
    tail = content[close_idx:]

    theme_pattern = rf"['\"]({'|'.join(re.escape(a) for a in all_theme_apps)})['\"]"

    removed_apps = []
    lines = body.splitlines(keepends=True)
    kept_lines = []

    for line in lines:
        m = re.search(theme_pattern, line)
        if m:
            removed_apps.append(m.group(1))
        else:
            kept_lines.append(line)

    if new_theme_apps:
        admin_idx = None
        indent = "    "
        quote = '"'

        for idx, line in enumerate(kept_lines):
            admin_match = re.search(r"([ \t]*)['\"]django\.contrib\.admin['\"]", line)
            if admin_match:
                admin_idx = idx
                indent = admin_match.group(1) or "    "
                if "'django.contrib.admin'" in line:
                    quote = "'"
                break

        new_entries = [f"{indent}{quote}{app}{quote},\n" for app in new_theme_apps]
        new_block = "".join(new_entries)

        if admin_idx is not None:
            kept_lines.insert(admin_idx, new_block)
        else:
            if kept_lines and not kept_lines[0].startswith("\n"):
                kept_lines.insert(0, "\n" + new_block)
            else:
                kept_lines.insert(0, new_block)

    new_body = "".join(kept_lines)
    return f"{head}{new_body}{tail}", removed_apps


def is_include_imported(content: str) -> bool:
    """
    Checks if 'include' is already imported from django.urls.
    Uses AST to avoid false positives in docstrings or comments.
    """
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "django.urls":
                for alias in node.names:
                    if alias.name in ("include", "*"):
                        return True
    except Exception:
        # Fallback regex if AST parsing fails
        if re.search(
            r"^[ \t]*from\s+django\.urls\s+import\s+[^#\n]*\binclude\b",
            content,
            re.MULTILINE,
        ):
            return True
        if re.search(
            r"from\s+django\.urls\s+import\s*\([^)]*\binclude\b[^)]*\)",
            content,
            re.DOTALL,
        ):
            return True
    return False


def is_route_mounted(content: str, app_module: str) -> bool:
    """
    Checks if an app's URLs are already mounted inside urlpatterns.
    Parses urlpatterns specifically to avoid false positives from docstrings or comments.
    """
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "urlpatterns":
                        lines = content.splitlines()
                        start_line = node.lineno - 1
                        end_line = getattr(node, "end_lineno", len(lines))
                        urls_block = "\n".join(lines[start_line:end_line])
                        return (f'"{app_module}.urls"' in urls_block) or (f"'{app_module}.urls'" in urls_block)
    except Exception:
        pass

    m = re.search(r"urlpatterns\s*=\s*(\[|\()(.*?)(\]|\))", content, re.DOTALL)
    if m:
        block = m.group(2)
        return (f'"{app_module}.urls"' in block) or (f"'{app_module}.urls'" in block)

    return (f'"{app_module}.urls"' in content) or (f"'{app_module}.urls'" in content)


def ensure_include_imported(content: str) -> str:
    """
    Ensures that 'include' is imported from django.urls in the provided urls.py content.
    If 'include' is already imported, returns content unmodified.
    Otherwise, appends 'include' to an existing 'from django.urls import ...' statement,
    or adds a new import line.
    """
    if is_include_imported(content):
        return content

    # 1. Multiline import: from django.urls import ( ... )
    multiline_match = re.search(
        r"(from\s+django\.urls\s+import\s*\()([^)]*)(\))", content, re.DOTALL
    )
    if multiline_match:
        imports = multiline_match.group(2)
        trimmed = imports.rstrip()
        if trimmed and not trimmed.endswith(","):
            new_imports = f"{trimmed},\n    include,\n"
        else:
            new_imports = f"{trimmed}\n    include,\n"
        return (
            content[: multiline_match.start(2)]
            + new_imports
            + content[multiline_match.start(3) :]
        )

    # 2. Single line import: from django.urls import path
    single_line_match = re.search(
        r"^[ \t]*from\s+django\.urls\s+import\s+([^#\n\r]+?)(\s*(?:#.*)?)$",
        content,
        re.MULTILINE,
    )
    if single_line_match:
        line_start = single_line_match.start()
        line_end = single_line_match.end()
        raw_imports = single_line_match.group(1).rstrip()
        trailing = single_line_match.group(2)
        if trailing.strip() and not trailing.startswith(" "):
            trailing = "  " + trailing.lstrip()
        new_line = f"from django.urls import {raw_imports}, include{trailing}"
        return content[:line_start] + new_line + content[line_end:]

    # 3. No django.urls import found; prepend to content
    return "from django.urls import include\n" + content


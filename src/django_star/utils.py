import re
from pathlib import Path
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

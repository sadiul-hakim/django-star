# <app>/management/commands/make_gitignore.py
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from django_star.console import console

GITIGNORE_TEMPLATE = """# ==========================================
# Python
# ==========================================
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# PyInstaller
*.manifest
*.spec

# Unit test / coverage reports
htmlcov/
.tox/
.nox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.py,cover
.hypothesis/
.pytest_cache/
cover/

# Translations
*.mo
*.pot

# Django stuff
*.log
local_settings.py
db.sqlite3
db.sqlite3-journal

# Sphinx documentation
docs/_build/

# Jupyter Notebook
.ipynb_checkpoints

# IPython
profile_default/
ipython_config.py

# pyenv
.python-version

# pipenv
Pipfile.lock

# poetry
poetry.lock

# pdm
.pdm.toml
.pdm-python
.pdm.lock

# PEP 582
__pypackages__/

# Celery stuff
celerybeat-schedule
celerybeat.pid

# Environments
.env
.env.*
!.env.example
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# mypy
.mypy_cache/
.dmypy.json
dmypy.json

# Pyre type checker
.pyre/

# pytype static type analyzer
.pytype/

# Cython debug symbols
cython_debug/

# ==========================================
# Django specific
# ==========================================
# Media files (user uploads)
media/
/media/

# Static files collected by collectstatic
staticfiles/
/staticfiles/

# Local database
*.sqlite3
*.sqlite3-journal

# Django secrets / local settings
local_settings.py

# ==========================================
# IDEs and editors
# ==========================================
# PyCharm
.idea/
*.iml
*.iws
*.ipr
out/

# VS Code
.vscode/
!.vscode/settings.json
!.vscode/tasks.json
!.vscode/launch.json
!.vscode/extensions.json
.history/

# Sublime Text
*.sublime-workspace
*.sublime-project

# Vim
*.swp
*.swo
*~
.vim/

# Emacs
*~
\\#*\\#
.\\#*

# NetBeans
nbproject/private/
nbbuild/
dist/
nbdist/
.nb-gradle/

# ==========================================
# OS generated files
# ==========================================
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db
desktop.ini

# ==========================================
# Docker
# ==========================================
docker-compose.override.yml

# ==========================================
# Logs & temp
# ==========================================
logs/
*.log
tmp/
temp/
.cache/
"""


class Command(BaseCommand):
    help = "Creates a .gitignore file at the project root (next to manage.py)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite the existing .gitignore file if it exists",
        )
        parser.add_argument(
            "--path",
            type=str,
            default=None,
            help="Custom path to write the .gitignore (defaults to project root)",
        )

    def handle(self, *args, **options):
        project_root = (
            Path(options["path"]).resolve()
            if options["path"]
            else Path(settings.BASE_DIR).resolve()
        )

        if not project_root.exists():
            project_root.mkdir(parents=True, exist_ok=True)

        target_file = project_root / ".gitignore"

        if target_file.exists() and not options["force"]:
            console.print(
                f"[bold yellow]⚠ .gitignore already exists at "
                f"{target_file}. Use --force to overwrite.[/bold yellow]"
            )
            return

        target_file.write_text(GITIGNORE_TEMPLATE, encoding="utf-8")

        action = "Overwrote" if options["force"] and target_file.exists() else "Created"
        console.print(
            f"[bold green]✔ {action} [cyan].gitignore[/cyan] at "
            f"[white]{target_file}[/white][/bold green]"
        )

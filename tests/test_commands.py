import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from django.core.management import get_commands
from django_star.utils import (
    safe_insert_into_collection,
    create_backup,
    ensure_include_imported,
    is_include_imported,
)
from django_star.management.commands.star_app import Command as StarAppCommand
from django_star.management.commands.star_route import Command as StarRouteCommand
from django_star.management.commands.star_admin import Command as StarAdminCommand
from django_star.management.commands.star_serializer import Command as StarSerializerCommand
from django_star.management.commands.star_schema import Command as StarSchemaCommand
from django_star.management.commands.star_theme import Command as StarThemeCommand
from django_star.management.commands.star_template import Command as StarTemplateCommand
from django_star.management.commands.star_about import (
    Command as StarAboutCommand,
    _is_local_path,
)
from django_star.management.commands.star_view import (
    Command as StarViewCommand,
    pluralize_name,
)
from django_star.management.commands.star_crud import Command as StarCrudCommand


class DjangoStarEdgeCaseTests(unittest.TestCase):
    def test_all_commands_are_registered(self):
        commands = get_commands()
        expected = [
            "star",
            "star_about",
            "star_app",
            "star_crud",
            "star_route",
            "star_service",
            "star_command",
            "star_admin",
            "star_urls",
            "star_serializer",
            "star_schema",
            "star_theme",
            "star_template",
            "star_view",
        ]
        for cmd in expected:
            self.assertIn(cmd, commands, f"Command {cmd} should be registered")


    def test_safe_insert_into_collection_lists_and_tuples(self):
        # 1. Standard list
        c_list = 'INSTALLED_APPS = [\n    "django.contrib.admin",\n]\n'
        res_list = safe_insert_into_collection(c_list, "INSTALLED_APPS", '    "billing",\n')
        self.assertIsNotNone(res_list)
        self.assertIn('"billing",', res_list)

        # 2. Standard tuple
        c_tuple = 'INSTALLED_APPS = (\n    "django.contrib.admin",\n)\n'
        res_tuple = safe_insert_into_collection(c_tuple, "INSTALLED_APPS", '    "billing",\n')
        self.assertIsNotNone(res_tuple)
        self.assertIn('"billing",', res_tuple)

        # 3. Tuple with nested parentheses (e.g., urlpatterns with path(...) calls)
        c_nested = (
            'urlpatterns = (\n'
            '    path("admin/", admin.site.urls),\n'
            '    path("api/", include("api.urls")),\n'
            ')\n'
        )
        res_nested = safe_insert_into_collection(c_nested, "urlpatterns", '    path("billing/", include("billing.urls")),\n')
        self.assertIsNotNone(res_nested)
        # Verify route was inserted before the final closing delimiter, not inside path()
        self.assertTrue(res_nested.endswith('    path("billing/", include("billing.urls")),\n)\n'))

    def test_safe_insert_into_collection_inline_item_adds_comma(self):
        c_inline = 'urlpatterns = [path("", views.home, name="home")]'
        new_route = '    path("authors/", views.AuthorListView.as_view(), name="author_list"),\n'
        res = safe_insert_into_collection(c_inline, "urlpatterns", new_route)
        self.assertIsNotNone(res)
        # Verify comma was added to previous entry
        self.assertIn('path("", views.home, name="home"),', res)
        self.assertIn('path("authors/", views.AuthorListView.as_view(), name="author_list"),', res)

    def test_safe_insert_into_collection_multiline_missing_comma_adds_comma(self):
        c_multiline = 'urlpatterns = [\n    path("admin/", admin.site.urls)\n]\n'
        new_route = '    path("blog/", include("blog.urls")),\n'
        res = safe_insert_into_collection(c_multiline, "urlpatterns", new_route)
        self.assertIsNotNone(res)
        self.assertIn('path("admin/", admin.site.urls),', res)

    def test_safe_insert_into_collection_line_with_comment_adds_comma_before_comment(self):
        c_comment = 'urlpatterns = [\n    path("admin/", admin.site.urls)  # admin site\n]\n'
        new_route = '    path("blog/", include("blog.urls")),\n'
        res = safe_insert_into_collection(c_comment, "urlpatterns", new_route)
        self.assertIsNotNone(res)
        self.assertIn('path("admin/", admin.site.urls),  # admin site', res)

    def test_safe_insert_into_collection_unparseable_returns_none(self):
        c_dynamic = 'INSTALLED_APPS += ["dynamic_app"]\n'
        res = safe_insert_into_collection(c_dynamic, "INSTALLED_APPS", '    "billing",\n')
        self.assertIsNone(res)

    def test_settings_bracket_injection_creates_backup(self):
        cmd = StarAppCommand()
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.py"
            initial_content = 'INSTALLED_APPS = [\n    "django.contrib.admin",\n]\n'
            settings_file.write_text(initial_content, encoding="utf-8")

            with patch.object(cmd, "_locate_settings_file", return_value=settings_file):
                cmd._wire_settings("testapp")

            # Check that backup was created
            backup_file = Path(tmpdir) / "settings.py.bak"
            self.assertTrue(backup_file.exists(), "settings.py.bak should be created")
            self.assertEqual(backup_file.read_text(encoding="utf-8"), initial_content)

            # Check that app was inserted
            updated = settings_file.read_text(encoding="utf-8")
            self.assertIn('"testapp"', updated)

    def test_settings_tuple_injection(self):
        cmd = StarAppCommand()
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.py"
            initial_content = 'INSTALLED_APPS = (\n    "django.contrib.auth",\n)\n'
            settings_file.write_text(initial_content, encoding="utf-8")

            with patch.object(cmd, "_locate_settings_file", return_value=settings_file):
                cmd._wire_settings("billing")

            backup_file = Path(tmpdir) / "settings.py.bak"
            self.assertTrue(backup_file.exists())
            updated = settings_file.read_text(encoding="utf-8")
            self.assertIn('"billing"', updated)

    def test_settings_unparseable_fallback_warning(self):
        cmd = StarAppCommand()
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.py"
            initial_content = 'INSTALLED_APPS += ["custom_app"]\n'
            settings_file.write_text(initial_content, encoding="utf-8")

            with patch.object(cmd, "_locate_settings_file", return_value=settings_file):
                with patch("django_star.management.commands.star_app.console.print") as mock_print:
                    cmd._wire_settings("billing")
                    printed_messages = [str(call[0][0]) for call in mock_print.call_args_list if call[0]]
                    combined = " ".join(printed_messages)
                    self.assertIn("Could not safely insert 'billing'", combined)

            # Original file should not be corrupted
            self.assertEqual(settings_file.read_text(encoding="utf-8"), initial_content)

    def test_root_urls_tuple_injection(self):
        cmd = StarAppCommand()
        with tempfile.TemporaryDirectory() as tmpdir:
            urls_file = Path(tmpdir) / "urls.py"
            initial_content = 'from django.urls import path\nurlpatterns = (\n    path("admin/", None),\n)\n'
            urls_file.write_text(initial_content, encoding="utf-8")

            with patch("django_star.management.commands.star_app.settings") as mock_settings:
                mock_settings.BASE_DIR = tmpdir
                mock_settings.ROOT_URLCONF = "urls"
                cmd._wire_root_urls("billing", "billing")

            backup_file = Path(tmpdir) / "urls.py.bak"
            self.assertTrue(backup_file.exists(), "urls.py.bak should be created")
            updated = urls_file.read_text(encoding="utf-8")
            self.assertIn('"billing/"', updated)
            self.assertIn('include("billing.urls")', updated)
            self.assertIn("include", updated)

    def test_root_urls_with_django_docstring_imports_include(self):
        cmd = StarAppCommand()
        django_default_urls = '''"""
URL configuration for myproject.

Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
]
'''
        with tempfile.TemporaryDirectory() as tmpdir:
            urls_file = Path(tmpdir) / "urls.py"
            urls_file.write_text(django_default_urls, encoding="utf-8")

            with patch("django_star.management.commands.star_app.settings") as mock_settings:
                mock_settings.BASE_DIR = tmpdir
                mock_settings.ROOT_URLCONF = "urls"
                cmd._wire_root_urls("blog", "blog")

            updated = urls_file.read_text(encoding="utf-8")
            # Verify include is imported in the code, not just in the docstring
            self.assertIn("from django.urls import path, include", updated)
            self.assertIn('path("blog/", include("blog.urls"))', updated)

    def test_ensure_include_imported_helper(self):
        # 1. Single line without include
        code1 = "from django.urls import path\nurlpatterns = []"
        self.assertEqual(
            ensure_include_imported(code1),
            "from django.urls import path, include\nurlpatterns = []",
        )

        # 2. Single line with comment
        code2 = "from django.urls import path  # url helpers\nurlpatterns = []"
        self.assertEqual(
            ensure_include_imported(code2),
            "from django.urls import path, include  # url helpers\nurlpatterns = []",
        )

        # 3. Already imported single line
        code3 = "from django.urls import path, include\nurlpatterns = []"
        self.assertEqual(ensure_include_imported(code3), code3)

        code3_rev = "from django.urls import include, path\nurlpatterns = []"
        self.assertEqual(ensure_include_imported(code3_rev), code3_rev)

        # 4. Multiline import without include
        code4 = "from django.urls import (\n    path,\n)\nurlpatterns = []"
        res4 = ensure_include_imported(code4)
        self.assertIn("include,", res4)
        self.assertTrue(is_include_imported(res4))

        # 5. Multiline import with include already present
        code5 = "from django.urls import (\n    path,\n    include,\n)\nurlpatterns = []"
        self.assertEqual(ensure_include_imported(code5), code5)

        # 6. No django.urls import
        code6 = "urlpatterns = []"
        self.assertEqual(
            ensure_include_imported(code6),
            "from django.urls import include\nurlpatterns = []",
        )

    def test_root_urls_unparseable_fallback_warning(self):
        cmd = StarRouteCommand()
        with tempfile.TemporaryDirectory() as tmpdir:
            urls_file = Path(tmpdir) / "urls.py"
            initial_content = '# Custom routing without urlpatterns list\n'
            urls_file.write_text(initial_content, encoding="utf-8")

            with patch("django_star.management.commands.star_route.settings") as mock_settings:
                mock_settings.BASE_DIR = tmpdir
                mock_settings.ROOT_URLCONF = "urls"
                with patch("django_star.management.commands.star_route.console.print") as mock_print:
                    cmd._wire_root_urls("blog", "blog")
                    printed_messages = [str(call[0][0]) for call in mock_print.call_args_list if call[0]]
                    combined = " ".join(printed_messages)
                    self.assertIn("Could not safely insert route", combined)

            # Unaltered file
            self.assertEqual(urls_file.read_text(encoding="utf-8"), initial_content)

    def test_abstract_and_auto_created_models_skipped_in_admin(self):
        cmd = StarAdminCommand()
        abstract_model = MagicMock()
        abstract_model.__name__ = "BaseAbstractModel"
        abstract_model._meta.abstract = True
        abstract_model._meta.auto_created = False

        auto_created_model = MagicMock()
        auto_created_model.__name__ = "App_M2M_Through"
        auto_created_model._meta.abstract = False
        auto_created_model._meta.auto_created = True

        standard_model = MagicMock()
        standard_model.__name__ = "Post"
        standard_model._meta.abstract = False
        standard_model._meta.auto_created = False
        standard_model._meta.get_fields.return_value = []

        mock_app_config = MagicMock()
        mock_app_config.get_models.return_value = [abstract_model, auto_created_model, standard_model]
        mock_app_config.path = tempfile.gettempdir()

        with patch("django_star.management.commands.star_admin.apps.get_app_config", return_value=mock_app_config):
            with patch("pathlib.Path.write_text") as mock_write, patch("pathlib.Path.read_text", return_value=""):
                with patch("django_star.management.commands.star_admin.console.print"):
                    cmd.handle(app_name="blog", model_name=None, all=True)

                written_content = "".join(call[0][0] for call in mock_write.call_args_list if call[0])
                self.assertNotIn("BaseAbstractModelAdmin", written_content)
                self.assertNotIn("App_M2M_ThroughAdmin", written_content)
                self.assertIn("PostAdmin", written_content)

    def test_abstract_and_auto_created_models_skipped_in_serializer(self):
        cmd = StarSerializerCommand()
        abstract_model = MagicMock()
        abstract_model.__name__ = "AbstractItem"
        abstract_model._meta.abstract = True
        abstract_model._meta.auto_created = False

        standard_model = MagicMock()
        standard_model.__name__ = "Item"
        standard_model._meta.abstract = False
        standard_model._meta.auto_created = False
        standard_model._meta.get_fields.return_value = []

        mock_app_config = MagicMock()
        mock_app_config.get_models.return_value = [abstract_model, standard_model]
        mock_app_config.path = tempfile.gettempdir()

        with patch("django_star.management.commands.star_serializer.apps.get_app_config", return_value=mock_app_config):
            with patch("pathlib.Path.write_text") as mock_write, patch("pathlib.Path.read_text", return_value=""):
                with patch("django_star.management.commands.star_serializer.console.print"):
                    cmd.handle(app_name="items", model_name=None, all=True)

                written_content = "".join(call[0][0] for call in mock_write.call_args_list if call[0])
                self.assertNotIn("AbstractItemSerializer", written_content)
                self.assertIn("ItemSerializer", written_content)

    def test_optional_drf_dependency_warning(self):
        cmd = StarSerializerCommand()
        mock_app_config = MagicMock()
        mock_app_config.get_models.return_value = []

        with patch("django_star.management.commands.star_serializer.importlib.util.find_spec", return_value=None):
            with patch("django_star.management.commands.star_serializer.apps.get_app_config", return_value=mock_app_config):
                with patch("django_star.management.commands.star_serializer.console.print") as mock_print:
                    cmd.handle(app_name="blog", model_name=None, all=True)
                    printed_messages = [str(call[0][0]) for call in mock_print.call_args_list if call[0]]
                    combined = " ".join(printed_messages)
                    self.assertIn("rest_framework' is not installed", combined)

    def test_optional_ninja_dependency_warning(self):
        cmd = StarSchemaCommand()
        mock_app_config = MagicMock()
        mock_app_config.get_models.return_value = []

        with patch("django_star.management.commands.star_schema.importlib.util.find_spec", return_value=None):
            with patch("django_star.management.commands.star_schema.apps.get_app_config", return_value=mock_app_config):
                with patch("django_star.management.commands.star_schema.console.print") as mock_print:
                    cmd.handle(app_name="blog", model_name=None, all=True)
                    printed_messages = [str(call[0][0]) for call in mock_print.call_args_list if call[0]]
                    combined = " ".join(printed_messages)
                    self.assertIn("ninja' is not installed", combined)

    def test_star_app_with_custom_dir(self):
        cmd = StarAppCommand()
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            settings_file = base_dir / "settings.py"
            settings_file.write_text('INSTALLED_APPS = [\n]\n', encoding="utf-8")

            urls_file = base_dir / "urls.py"
            urls_file.write_text('from django.urls import path\nurlpatterns = [\n]\n', encoding="utf-8")

            with patch("django_star.management.commands.star_app.settings") as mock_settings:
                mock_settings.BASE_DIR = base_dir
                mock_settings.SETTINGS_MODULE = "settings"
                mock_settings.ROOT_URLCONF = "urls"

                with patch("django_star.management.commands.star_app.call_command") as mock_call:
                    def fake_startapp(cmd_name, app_name, target=None):
                        target_path = Path(target)
                        target_path.mkdir(parents=True, exist_ok=True)
                        (target_path / "apps.py").write_text(
                            f'from django.apps import AppConfig\nclass BillingConfig(AppConfig):\n    name = "{app_name}"\n'
                        )
                    mock_call.side_effect = fake_startapp

                    cmd.handle(app_name="billing", dir="apps")

                    # Target app should be inside apps/billing
                    app_dir = base_dir / "apps" / "billing"
                    self.assertTrue(app_dir.is_dir())
                    self.assertTrue((base_dir / "apps" / "__init__.py").exists())
                    self.assertTrue((app_dir / "urls.py").exists())

                    # apps.py should be patched to full module path
                    apps_content = (app_dir / "apps.py").read_text(encoding="utf-8")
                    self.assertIn('name = "apps.billing"', apps_content)

                    # settings.py should have registered 'apps.billing'
                    settings_content = settings_file.read_text(encoding="utf-8")
                    self.assertIn('"apps.billing"', settings_content)

                    # urls.py should have mounted apps.billing.urls
                    urls_content = urls_file.read_text(encoding="utf-8")
                    self.assertIn('include("apps.billing.urls")', urls_content)

    def test_star_theme_switch_to_jazzmin(self):
        cmd = StarThemeCommand()
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            settings_file = base_dir / "settings.py"
            initial_content = 'INSTALLED_APPS = [\n    "django.contrib.admin",\n    "django.contrib.auth",\n]\n'
            settings_file.write_text(initial_content, encoding="utf-8")

            with patch("django_star.management.commands.star_theme.locate_settings_file", return_value=settings_file):
                with patch.object(cmd, "_ensure_package_installed", return_value=True):
                    cmd.handle(theme="jazzmin", remove=False, no_pip=True, list=False, yes=True)

            updated = settings_file.read_text(encoding="utf-8")
            self.assertIn('"jazzmin",\n    "django.contrib.admin",', updated)
            self.assertTrue((base_dir / "settings.py.bak").exists())

    def test_star_theme_replaces_existing_theme(self):
        cmd = StarThemeCommand()
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            settings_file = base_dir / "settings.py"
            initial_content = 'INSTALLED_APPS = [\n    "simpleui",\n    "django.contrib.admin",\n]\n'
            settings_file.write_text(initial_content, encoding="utf-8")

            with patch("django_star.management.commands.star_theme.locate_settings_file", return_value=settings_file):
                with patch.object(cmd, "_ensure_package_installed", return_value=True):
                    cmd.handle(theme="jazzmin", remove=False, no_pip=True, list=False, yes=True)

            updated = settings_file.read_text(encoding="utf-8")
            self.assertNotIn("simpleui", updated)
            self.assertIn('"jazzmin",\n    "django.contrib.admin",', updated)

    def test_star_theme_admin_interface_adds_colorfield_and_x_frame(self):
        cmd = StarThemeCommand()
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            settings_file = base_dir / "settings.py"
            initial_content = 'INSTALLED_APPS = [\n    "django.contrib.admin",\n]\n'
            settings_file.write_text(initial_content, encoding="utf-8")

            with patch("django_star.management.commands.star_theme.locate_settings_file", return_value=settings_file):
                with patch.object(cmd, "_ensure_package_installed", return_value=True):
                    with patch("django_star.management.commands.star_theme.call_command"):
                        cmd.handle(theme="admin_interface", remove=False, no_pip=True, list=False, yes=True)

            updated = settings_file.read_text(encoding="utf-8")
            self.assertIn('"admin_interface",\n    "colorfield",\n    "django.contrib.admin",', updated)
            self.assertIn('X_FRAME_OPTIONS = "SAMEORIGIN"', updated)

    def test_star_theme_switch_from_admin_interface_to_simpleui(self):
        cmd = StarThemeCommand()
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            settings_file = base_dir / "settings.py"
            initial_content = 'INSTALLED_APPS = [\n    "admin_interface",\n    "colorfield",\n    "django.contrib.admin",\n]\n'
            settings_file.write_text(initial_content, encoding="utf-8")

            with patch("django_star.management.commands.star_theme.locate_settings_file", return_value=settings_file):
                with patch.object(cmd, "_ensure_package_installed", return_value=True):
                    cmd.handle(theme="simpleui", remove=False, no_pip=True, list=False, yes=True)

            updated = settings_file.read_text(encoding="utf-8")
            self.assertNotIn("admin_interface", updated)
            self.assertNotIn("colorfield", updated)
            self.assertIn('"simpleui",\n    "django.contrib.admin",', updated)

    def test_star_theme_grappelli_wires_and_unwires_urls(self):
        cmd = StarThemeCommand()
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            settings_file = base_dir / "settings.py"
            settings_file.write_text('INSTALLED_APPS = [\n    "django.contrib.admin",\n]\n', encoding="utf-8")

            urls_file = base_dir / "urls.py"
            urls_file.write_text('from django.urls import path\nurlpatterns = [\n    path("admin/", None),\n]\n', encoding="utf-8")

            with patch("django_star.management.commands.star_theme.locate_settings_file", return_value=settings_file):
                with patch("django_star.management.commands.star_theme.locate_root_urls_file", return_value=urls_file):
                    with patch.object(cmd, "_ensure_package_installed", return_value=True):
                        # 1. Switch to grappelli -> mounts grappelli.urls
                        cmd.handle(theme="grappelli", remove=False, no_pip=True, list=False, yes=True)

                        urls_after_grappelli = urls_file.read_text(encoding="utf-8")
                        self.assertIn('path("grappelli/", include("grappelli.urls")),', urls_after_grappelli)
                        self.assertIn("include", urls_after_grappelli)

                        # 2. Switch from grappelli to jazzmin -> unwires grappelli.urls
                        cmd.handle(theme="jazzmin", remove=False, no_pip=True, list=False, yes=True)

                        urls_after_jazzmin = urls_file.read_text(encoding="utf-8")
                        self.assertNotIn("grappelli.urls", urls_after_jazzmin)

    def test_star_theme_remove_restores_stock_admin(self):
        cmd = StarThemeCommand()
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            settings_file = base_dir / "settings.py"
            initial_content = 'INSTALLED_APPS = [\n    "jazzmin",\n    "django.contrib.admin",\n]\n'
            settings_file.write_text(initial_content, encoding="utf-8")

            with patch("django_star.management.commands.star_theme.locate_settings_file", return_value=settings_file):
                with patch.object(cmd, "_wire_grappelli_urls"):
                    cmd.handle(theme=None, remove=True, no_pip=True, list=False, yes=True)

            updated = settings_file.read_text(encoding="utf-8")
            self.assertNotIn("jazzmin", updated)
            self.assertIn('"django.contrib.admin",', updated)

    def test_star_theme_invalid_choice_raises_command_error(self):
        from django.core.management.base import CommandError
        cmd = StarThemeCommand()
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.py"
            settings_file.write_text('INSTALLED_APPS = []\n', encoding="utf-8")
            with patch("django_star.management.commands.star_theme.locate_settings_file", return_value=settings_file):
                with self.assertRaises(CommandError):
                    cmd.handle(theme="invalid_theme_name", remove=False, no_pip=True, list=False, yes=True)

    def test_star_route_with_django_docstrings(self):
        cmd = StarRouteCommand()
        django_default_urls = '''"""
URL configuration for myproject.

Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
]
'''
        with tempfile.TemporaryDirectory() as tmpdir:
            urls_file = Path(tmpdir) / "urls.py"
            urls_file.write_text(django_default_urls, encoding="utf-8")

            with patch("django_star.management.commands.star_route.settings") as mock_settings:
                mock_settings.BASE_DIR = tmpdir
                mock_settings.ROOT_URLCONF = "urls"
                cmd._wire_root_urls("blog", "blog")

            updated = urls_file.read_text(encoding="utf-8")
            self.assertIn("from django.urls import path, include", updated)
            self.assertIn('path("blog/", include("blog.urls"))', updated)

    def test_star_theme_grappelli_with_django_docstrings(self):
        cmd = StarThemeCommand()
        django_default_urls = '''"""
URL configuration for myproject.

Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
]
'''
        with tempfile.TemporaryDirectory() as tmpdir:
            urls_file = Path(tmpdir) / "urls.py"
            urls_file.write_text(django_default_urls, encoding="utf-8")
            with patch("django_star.management.commands.star_theme.locate_root_urls_file", return_value=urls_file):
                res = cmd._wire_grappelli_urls(remove=False)
            self.assertTrue(res)
            updated = urls_file.read_text(encoding="utf-8")
            self.assertIn("from django.urls import path, include", updated)
            self.assertIn('path("grappelli/", include("grappelli.urls"))', updated)

    def test_star_template_default_namespaced(self):
        cmd = StarTemplateCommand()
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_config = MagicMock()
            mock_config.label = "main"
            mock_config.path = tmpdir

            with patch("django_star.management.commands.star_template.apps.get_app_config", return_value=mock_config):
                cmd.handle(
                    app_name="main",
                    template_name="index",
                    extends=None,
                    html5=False,
                    flat=False,
                    block="content",
                    force=False,
                )

            target = Path(tmpdir) / "templates" / "main" / "index.html"
            self.assertTrue(target.exists())
            content = target.read_text(encoding="utf-8")
            self.assertIn("{% block content %}", content)
            self.assertIn("main-index", content)

    def test_star_template_with_extends(self):
        cmd = StarTemplateCommand()
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_config = MagicMock()
            mock_config.label = "main"
            mock_config.path = tmpdir

            with patch("django_star.management.commands.star_template.apps.get_app_config", return_value=mock_config):
                cmd.handle(
                    app_name="main",
                    template_name="dashboard.html",
                    extends="base",
                    html5=False,
                    flat=False,
                    block="body",
                    force=False,
                )

            target = Path(tmpdir) / "templates" / "main" / "dashboard.html"
            self.assertTrue(target.exists())
            content = target.read_text(encoding="utf-8")
            self.assertIn('{% extends "base.html" %}', content)
            self.assertIn("{% block body %}", content)
            self.assertIn("Main - Dashboard", content)

    def test_star_template_with_html5(self):
        cmd = StarTemplateCommand()
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_config = MagicMock()
            mock_config.label = "main"
            mock_config.path = tmpdir

            with patch("django_star.management.commands.star_template.apps.get_app_config", return_value=mock_config):
                cmd.handle(
                    app_name="main",
                    template_name="landing",
                    extends=None,
                    html5=True,
                    flat=False,
                    block="content",
                    force=False,
                )

            target = Path(tmpdir) / "templates" / "main" / "landing.html"
            self.assertTrue(target.exists())
            content = target.read_text(encoding="utf-8")
            self.assertIn("<!DOCTYPE html>", content)
            self.assertIn('<html lang="en">', content)
            self.assertIn("{% block content %}", content)

    def test_star_template_flat_flag(self):
        cmd = StarTemplateCommand()
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_config = MagicMock()
            mock_config.label = "main"
            mock_config.path = tmpdir

            with patch("django_star.management.commands.star_template.apps.get_app_config", return_value=mock_config):
                cmd.handle(
                    app_name="main",
                    template_name="header.html",
                    extends=None,
                    html5=False,
                    flat=True,
                    block="content",
                    force=False,
                )

            # In flat mode, should be directly in templates/header.html
            target = Path(tmpdir) / "templates" / "header.html"
            self.assertTrue(target.exists())
            namespaced = Path(tmpdir) / "templates" / "main" / "header.html"
            self.assertFalse(namespaced.exists())

    def test_star_template_nested_subpath(self):
        cmd = StarTemplateCommand()
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_config = MagicMock()
            mock_config.label = "auth"
            mock_config.path = tmpdir

            with patch("django_star.management.commands.star_template.apps.get_app_config", return_value=mock_config):
                cmd.handle(
                    app_name="auth",
                    template_name="emails/welcome",
                    extends=None,
                    html5=False,
                    flat=False,
                    block="content",
                    force=False,
                )

            target = Path(tmpdir) / "templates" / "auth" / "emails" / "welcome.html"
            self.assertTrue(target.exists())

    def test_star_template_force_overwrite(self):
        cmd = StarTemplateCommand()
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_config = MagicMock()
            mock_config.label = "main"
            mock_config.path = tmpdir

            target = Path(tmpdir) / "templates" / "main" / "existing.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("ORIGINAL CONTENT", encoding="utf-8")

            with patch("django_star.management.commands.star_template.apps.get_app_config", return_value=mock_config):
                # Without force: should NOT overwrite
                cmd.handle(
                    app_name="main",
                    template_name="existing.html",
                    extends=None,
                    html5=False,
                    flat=False,
                    block="content",
                    force=False,
                )
                self.assertEqual(target.read_text(encoding="utf-8"), "ORIGINAL CONTENT")

                # With force: SHOULD overwrite
                cmd.handle(
                    app_name="main",
                    template_name="existing.html",
                    extends=None,
                    html5=True,
                    flat=False,
                    block="content",
                    force=True,
                )
                self.assertIn("<!DOCTYPE html>", target.read_text(encoding="utf-8"))

    def test_star_template_invalid_app_raises_command_error(self):
        cmd = StarTemplateCommand()
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            cmd.handle(
                app_name="nonexistent_app_xyz",
                template_name="index",
                extends=None,
                html5=False,
                flat=False,
                block="content",
                force=False,
            )

    def test_star_about_runs_terminal_dashboard(self):
        import io
        from rich.console import Console
        cmd = StarAboutCommand()
        buf = io.StringIO()
        test_console = Console(file=buf, force_terminal=False, width=120)
        with patch("django_star.management.commands.star_about.console", test_console):
            cmd.handle(json=False)
            output = buf.getvalue()
            self.assertIn("Django Star", output)
            self.assertIn("ENVIRONMENT & CONFIG", output)
            self.assertIn("DATABASE & MIGRATIONS", output)
            self.assertIn("APPLICATIONS & ARCHITECTURE", output)

    def test_star_about_json_output(self):
        import io
        import json
        from django.core.management import call_command
        out = io.StringIO()
        call_command("star_about", "--json", stdout=out)
        output_str = out.getvalue()
        data = json.loads(output_str)
        self.assertIn("environment", data)
        self.assertIn("database", data)
        self.assertIn("apps_architecture", data)
        self.assertIn("cache_storage", data)
        self.assertIn("django_version", data["environment"])
        self.assertIn("total_apps", data["apps_architecture"])

    def test_star_about_migration_unreachable_fallback(self):
        import io
        from rich.console import Console
        cmd = StarAboutCommand()
        buf = io.StringIO()
        test_console = Console(file=buf, force_terminal=False, width=120)
        with patch("django.db.migrations.executor.MigrationExecutor", side_effect=Exception("DB connection error")):
            with patch("django_star.management.commands.star_about.console", test_console):
                cmd.handle(json=False)
                output = buf.getvalue()
                self.assertIn("Unreachable", output)

    def test_star_about_is_local_path_helper(self):
        base_dir = Path("/home/user/project")
        # Direct local app
        local_app = Path("/home/user/project/blog")
        self.assertTrue(_is_local_path(local_app, base_dir))

        # Nested apps/ subfolder
        nested_local = Path("/home/user/project/apps/billing")
        self.assertTrue(_is_local_path(nested_local, base_dir))

        # Virtual environment inside base_dir should be recognized as non-local
        venv_app = Path("/home/user/project/.venv/lib/site-packages/some_pkg")
        self.assertFalse(_is_local_path(venv_app, base_dir))

        # Outside base_dir
        outside_app = Path("/usr/lib/python3.12/site-packages/django")
        self.assertFalse(_is_local_path(outside_app, base_dir))

    def test_pluralize_name_helper(self):
        self.assertEqual(pluralize_name("Post"), "posts")
        self.assertEqual(pluralize_name("Category"), "categories")
        self.assertEqual(pluralize_name("Box"), "boxes")
        self.assertEqual(pluralize_name("Person"), "people")
        self.assertEqual(pluralize_name("Child"), "children")
        self.assertEqual(pluralize_name("Hero"), "heroes")

    def test_star_view_crud_generation(self):
        cmd = StarViewCommand()
        with tempfile.TemporaryDirectory() as tmpdir:
            app_dir = Path(tmpdir)
            views_file = app_dir / "views.py"
            views_file.write_text("from django.shortcuts import render\n", encoding="utf-8")
            urls_file = app_dir / "urls.py"
            urls_file.write_text("from django.urls import path\nurlpatterns = []\n", encoding="utf-8")

            mock_model = MagicMock()
            mock_model.__name__ = "Article"
            mock_model._meta.abstract = False
            mock_model._meta.auto_created = False
            field1 = MagicMock()
            field1.name = "title"
            field1.column = "title"
            field1.primary_key = False
            field1.many_to_many = False
            field1.auto_now = False
            field1.auto_now_add = False
            mock_model._meta.get_fields.return_value = [field1]

            mock_app_config = MagicMock()
            mock_app_config.label = "blog"
            mock_app_config.path = str(app_dir)

            with patch("django_star.management.commands.star_view.apps.get_app_config", return_value=mock_app_config):
                with patch("django_star.management.commands.star_view.apps.get_model", return_value=mock_model):
                    cmd.handle(
                        app_name="blog",
                        name="Article",
                        crud=True,
                        api=False,
                        all=False,
                        no_templates=False,
                        no_urls=False,
                        fbv=False,
                        type=None,
                        force=False,
                    )

            # Check views.py
            views_content = views_file.read_text(encoding="utf-8")
            self.assertIn("class ArticleListView(ListView):", views_content)
            self.assertIn("class ArticleDetailView(DetailView):", views_content)
            self.assertIn("class ArticleCreateView(CreateView):", views_content)
            self.assertIn("class ArticleUpdateView(UpdateView):", views_content)
            self.assertIn("class ArticleDeleteView(DeleteView):", views_content)

            # Check urls.py
            urls_content = urls_file.read_text(encoding="utf-8")
            self.assertIn("article_list", urls_content)
            self.assertIn("article_create", urls_content)
            self.assertIn("article_detail", urls_content)

            # Check templates
            tpl_dir = app_dir / "templates" / "blog"
            self.assertTrue((tpl_dir / "article_list.html").exists())
            self.assertTrue((tpl_dir / "article_detail.html").exists())
            self.assertTrue((tpl_dir / "article_form.html").exists())
            self.assertTrue((tpl_dir / "article_confirm_delete.html").exists())

    def test_star_crud_shortcut_command(self):
        cmd = StarCrudCommand()
        with tempfile.TemporaryDirectory() as tmpdir:
            app_dir = Path(tmpdir)
            views_file = app_dir / "views.py"
            views_file.write_text("", encoding="utf-8")
            urls_file = app_dir / "urls.py"
            urls_file.write_text("from django.urls import path\nurlpatterns = []\n", encoding="utf-8")

            mock_model = MagicMock()
            mock_model.__name__ = "Product"
            mock_model._meta.abstract = False
            mock_model._meta.auto_created = False
            mock_model._meta.get_fields.return_value = []

            mock_app_config = MagicMock()
            mock_app_config.label = "shop"
            mock_app_config.path = str(app_dir)

            with patch("django_star.management.commands.star_view.apps.get_app_config", return_value=mock_app_config):
                with patch("django_star.management.commands.star_view.apps.get_model", return_value=mock_model):
                    cmd.handle(
                        app_name="shop",
                        name="Product",
                        api=False,
                        all=False,
                        no_templates=True,
                        no_urls=False,
                        fbv=False,
                        type=None,
                        force=False,
                    )

            views_content = views_file.read_text(encoding="utf-8")
            self.assertIn("class ProductListView(ListView):", views_content)

    def test_star_view_api_mode(self):
        cmd = StarViewCommand()
        with tempfile.TemporaryDirectory() as tmpdir:
            app_dir = Path(tmpdir)
            views_file = app_dir / "views.py"
            views_file.write_text("", encoding="utf-8")
            urls_file = app_dir / "urls.py"
            urls_file.write_text("from django.urls import path\nurlpatterns = []\n", encoding="utf-8")

            mock_model = MagicMock()
            mock_model.__name__ = "Order"
            mock_model._meta.abstract = False
            mock_model._meta.auto_created = False
            mock_model._meta.get_fields.return_value = []

            mock_app_config = MagicMock()
            mock_app_config.label = "shop"
            mock_app_config.path = str(app_dir)

            with patch("django_star.management.commands.star_view.apps.get_app_config", return_value=mock_app_config):
                with patch("django_star.management.commands.star_view.apps.get_model", return_value=mock_model):
                    cmd.handle(
                        app_name="shop",
                        name="Order",
                        crud=True,
                        api=True,
                        all=False,
                        no_templates=True,
                        no_urls=False,
                        fbv=False,
                        type=None,
                        force=False,
                    )

            views_content = views_file.read_text(encoding="utf-8")
            self.assertIn("class OrderViewSet(viewsets.ModelViewSet):", views_content)
            urls_content = urls_file.read_text(encoding="utf-8")
            self.assertIn("DefaultRouter", urls_content)

    def test_star_view_single_fbv_mode(self):
        cmd = StarViewCommand()
        with tempfile.TemporaryDirectory() as tmpdir:
            app_dir = Path(tmpdir)
            views_file = app_dir / "views.py"
            views_file.write_text("", encoding="utf-8")
            urls_file = app_dir / "urls.py"
            urls_file.write_text("from django.urls import path\nurlpatterns = []\n", encoding="utf-8")

            mock_app_config = MagicMock()
            mock_app_config.label = "main"
            mock_app_config.path = str(app_dir)

            with patch("django_star.management.commands.star_view.apps.get_app_config", return_value=mock_app_config):
                with patch("django_star.management.commands.star_view.apps.get_model", side_effect=LookupError):
                    cmd.handle(
                        app_name="main",
                        name="about_us",
                        crud=False,
                        api=False,
                        all=False,
                        no_templates=False,
                        no_urls=False,
                        fbv=True,
                        type=None,
                        force=False,
                    )

            views_content = views_file.read_text(encoding="utf-8")
            self.assertIn("def about_us(request):", views_content)
            urls_content = urls_file.read_text(encoding="utf-8")
            self.assertIn('path("about_us/", views.about_us, name="about_us")', urls_content)

    def test_star_view_single_cbv_template_view(self):
        cmd = StarViewCommand()
        with tempfile.TemporaryDirectory() as tmpdir:
            app_dir = Path(tmpdir)
            views_file = app_dir / "views.py"
            views_file.write_text("", encoding="utf-8")
            urls_file = app_dir / "urls.py"
            urls_file.write_text("from django.urls import path\nurlpatterns = []\n", encoding="utf-8")

            mock_app_config = MagicMock()
            mock_app_config.label = "main"
            mock_app_config.path = str(app_dir)

            with patch("django_star.management.commands.star_view.apps.get_app_config", return_value=mock_app_config):
                with patch("django_star.management.commands.star_view.apps.get_model", side_effect=LookupError):
                    cmd.handle(
                        app_name="main",
                        name="DashboardView",
                        crud=False,
                        api=False,
                        all=False,
                        no_templates=False,
                        no_urls=False,
                        fbv=False,
                        type="TemplateView",
                        force=False,
                    )

            views_content = views_file.read_text(encoding="utf-8")
            self.assertIn("class DashboardView(TemplateView):", views_content)
            urls_content = urls_file.read_text(encoding="utf-8")
            self.assertIn("views.DashboardView.as_view()", urls_content)


if __name__ == "__main__":
    unittest.main()


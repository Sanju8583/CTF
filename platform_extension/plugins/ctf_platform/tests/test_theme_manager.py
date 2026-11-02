import io
import os
import stat
import tempfile
import unittest
import zipfile
from types import SimpleNamespace

from ctf_platform.theme_manager import (
    ThemePackageError,
    install_theme_archive,
    installed_themes,
)


def make_theme_archive(root=""):
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as theme:
        theme.writestr(root + "templates/base.html", "<html></html>")
        theme.writestr(root + "static/theme.css", "body {}")
    return archive.getvalue()


class ThemeManagerTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.app = SimpleNamespace(
            config={
                "CTF_PLATFORM_THEME_DIR": self.temporary_directory.name,
            }
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_installs_theme_and_lists_it(self):
        theme_name = install_theme_archive(
            self.app, make_theme_archive(), "neon-theme.zip"
        )

        self.assertEqual(theme_name, "custom-neon-theme")
        self.assertEqual(installed_themes(self.app), [theme_name])
        stylesheet = os.path.join(
            self.temporary_directory.name, theme_name, "static", "theme.css"
        )
        with open(stylesheet, encoding="utf-8") as theme_file:
            self.assertEqual(theme_file.read(), "body {}")

    def test_accepts_single_enclosing_folder(self):
        theme_name = install_theme_archive(
            self.app, make_theme_archive("package/"), "package.zip"
        )

        self.assertTrue(
            os.path.isfile(
                os.path.join(
                    self.temporary_directory.name,
                    theme_name,
                    "templates",
                    "base.html",
                )
            )
        )

    def test_accepts_windows_style_zip_paths(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as theme:
            theme.writestr("package\\templates\\base.html", "<html></html>")
            theme.writestr("package\\static\\theme.css", "body {}")

        theme_name = install_theme_archive(
            self.app, archive.getvalue(), "windows-theme.zip"
        )

        self.assertTrue(
            os.path.isfile(
                os.path.join(
                    self.temporary_directory.name,
                    theme_name,
                    "templates",
                    "base.html",
                )
            )
        )

    def test_rejects_traversal_without_writing_outside_theme_root(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as theme:
            theme.writestr("templates/base.html", "<html></html>")
            theme.writestr("static/theme.css", "body {}")
            theme.writestr("../outside.txt", "not allowed")

        with self.assertRaises(ThemePackageError):
            install_theme_archive(self.app, archive.getvalue(), "unsafe.zip")

        self.assertEqual(os.listdir(self.temporary_directory.name), [])

    def test_rejects_windows_style_traversal(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as theme:
            theme.writestr("templates/base.html", "<html></html>")
            theme.writestr("static/theme.css", "body {}")
            theme.writestr("..\\outside.txt", "not allowed")

        with self.assertRaises(ThemePackageError):
            install_theme_archive(self.app, archive.getvalue(), "unsafe.zip")

        self.assertEqual(os.listdir(self.temporary_directory.name), [])

    def test_rejects_reinstall_with_same_filename(self):
        archive = make_theme_archive()
        install_theme_archive(self.app, archive, "same.zip")

        with self.assertRaises(ThemePackageError):
            install_theme_archive(self.app, archive, "same.zip")

    def test_rejects_symbolic_links(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as theme:
            theme.writestr("templates/base.html", "<html></html>")
            theme.writestr("static/theme.css", "body {}")
            link = zipfile.ZipInfo("static/link")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            theme.writestr(link, "../templates/base.html")

        with self.assertRaises(ThemePackageError):
            install_theme_archive(self.app, archive.getvalue(), "linked.zip")

    def test_rejects_duplicate_paths(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as theme:
            theme.writestr("templates/base.html", "<html></html>")
            theme.writestr("static/theme.css", "first")
            theme.writestr("static/theme.css", "second")

        with self.assertRaises(ThemePackageError):
            install_theme_archive(self.app, archive.getvalue(), "duplicate.zip")


if __name__ == "__main__":
    unittest.main()

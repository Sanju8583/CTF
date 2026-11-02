import os
import re
import stat
import shutil
import tempfile
import zipfile
from io import BytesIO
from pathlib import PurePosixPath

from flask import abort, current_app, request, send_file
from jinja2 import ChoiceLoader, PrefixLoader
from werkzeug.utils import safe_join, secure_filename

MAX_ARCHIVE_SIZE = 10 * 1024 * 1024
MAX_UNPACKED_SIZE = 50 * 1024 * 1024
MAX_ARCHIVE_FILES = 500
THEME_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,47}$")
_ORIGINAL_GET_THEMES = None
_ORIGINAL_ASSET_MANIFEST = None


class ThemePackageError(ValueError):
    pass


def theme_directory(app):
    return app.config["CTF_PLATFORM_THEME_DIR"]


def installed_themes(app):
    root = theme_directory(app)
    if not os.path.isdir(root):
        return []
    return sorted(
        name
        for name in os.listdir(root)
        if THEME_NAME_PATTERN.fullmatch(name)
        and not os.path.islink(os.path.join(root, name))
        and os.path.isdir(os.path.join(root, name))
    )


def _package_files(archive):
    if len(archive.infolist()) > MAX_ARCHIVE_FILES:
        raise ThemePackageError("Theme archive contains too many files.")

    files = []
    unpacked_size = 0
    for member in archive.infolist():
        name = member.filename.replace("\\", "/")
        if "\x00" in name:
            raise ThemePackageError("Theme archive contains an invalid path.")
        path = PurePosixPath(name)
        if not path.parts or path.is_absolute() or any(
            part in ("", ".", "..") for part in path.parts
        ):
            raise ThemePackageError("Theme archive contains an unsafe path.")
        if ":" in path.parts[0]:
            raise ThemePackageError("Theme archive contains an invalid path.")

        mode = member.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise ThemePackageError("Symbolic links are not allowed in themes.")

        if member.is_dir():
            continue
        if not path.parts or path.parts[0] not in ("templates", "static"):
            files.append((member, path, False))
        else:
            files.append((member, path, True))
        unpacked_size += member.file_size

    if unpacked_size > MAX_UNPACKED_SIZE:
        raise ThemePackageError("Theme archive expands beyond the 50 MB limit.")

    content_files = [path for _, path, _ in files]
    if not content_files:
        raise ThemePackageError("Theme archive is empty.")

    first_parts = {path.parts[0] for path in content_files}
    if len(first_parts) == 1 and next(iter(first_parts)) not in (
        "templates",
        "static",
    ):
        if all(len(path.parts) > 1 for path in content_files):
            files = [
                (member, PurePosixPath(*path.parts[1:]), allowed)
                for member, path, allowed in files
            ]

    cleaned = []
    seen_paths = set()
    for member, path, _ in files:
        if path.parts[0] not in ("templates", "static"):
            if path.name.lower() == "readme.md" and len(path.parts) == 1:
                continue
            raise ThemePackageError(
                "Theme archives may contain only templates/ and static/ files."
            )
        normalized = str(path)
        if normalized in seen_paths:
            raise ThemePackageError("Theme archive contains duplicate file paths.")
        seen_paths.add(normalized)
        cleaned.append((member, path))

    paths = {str(path) for _, path in cleaned}
    for path in paths:
        parts = PurePosixPath(path).parts
        if any("/".join(parts[:index]) in paths for index in range(1, len(parts))):
            raise ThemePackageError("Theme archive contains conflicting file paths.")
    if "templates/base.html" not in paths:
        raise ThemePackageError("Theme archive must include templates/base.html.")
    if not any(path.parts[0] == "static" for _, path in cleaned):
        raise ThemePackageError("Theme archive must include static assets.")

    return cleaned


def install_theme_archive(app, archive_bytes, upload_filename):
    if len(archive_bytes) > MAX_ARCHIVE_SIZE:
        raise ThemePackageError("Theme archive must be 10 MB or smaller.")

    stem = secure_filename(os.path.splitext(upload_filename)[0]).lower()
    stem = re.sub(r"[^a-z0-9_-]+", "-", stem).strip("-_")[:40]
    theme_name = "custom-" + (stem or "theme")
    root = theme_directory(app)
    os.makedirs(root, exist_ok=True)
    destination = os.path.join(root, theme_name)
    if os.path.lexists(destination):
        raise ThemePackageError(
            "A theme with this upload name is already installed."
        )

    try:
        with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
            files = _package_files(archive)
            stage = tempfile.mkdtemp(prefix=".theme-install-", dir=root)
            try:
                extracted_size = 0
                for member, relative_path in files:
                    target = os.path.join(stage, *relative_path.parts)
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with archive.open(member) as source, open(
                        target, "xb"
                    ) as output:
                        while True:
                            chunk = source.read(64 * 1024)
                            if not chunk:
                                break
                            extracted_size += len(chunk)
                            if extracted_size > MAX_UNPACKED_SIZE:
                                raise ThemePackageError(
                                    "Theme archive expands beyond the 50 MB limit."
                                )
                            output.write(chunk)
                os.replace(stage, destination)
            except Exception:
                shutil.rmtree(stage, ignore_errors=True)
                raise
    except zipfile.BadZipFile as error:
        raise ThemePackageError("The uploaded file is not a valid ZIP archive.") from error
    except (NotImplementedError, RuntimeError) as error:
        raise ThemePackageError(
            "The theme ZIP uses an unsupported or encrypted file format."
        ) from error

    return theme_name


def configure_theme_loader(app):
    root = theme_directory(app)
    os.makedirs(root, exist_ok=True)

    from CTFd import ThemeLoader
    from CTFd.constants.assets import Assets
    from CTFd.utils import get_asset_json
    from CTFd.utils import config as ctfd_config

    global _ORIGINAL_ASSET_MANIFEST
    global _ORIGINAL_GET_THEMES
    if _ORIGINAL_GET_THEMES is None:
        _ORIGINAL_GET_THEMES = ctfd_config.get_themes
    if _ORIGINAL_ASSET_MANIFEST is None:
        _ORIGINAL_ASSET_MANIFEST = Assets.manifest

    def get_themes():
        current = current_app._get_current_object()
        return sorted(set(_ORIGINAL_GET_THEMES() + installed_themes(current)))

    def manifest(theme=None, _return_none_on_load_failure=False):
        current = current_app._get_current_object()
        root = theme_directory(current)
        if theme in installed_themes(current):
            manifest_path = os.path.join(
                root, theme, "static", "manifest.json"
            )
            if os.path.isfile(manifest_path):
                return get_asset_json(manifest_path)
        return _ORIGINAL_ASSET_MANIFEST(
            theme=theme,
            _return_none_on_load_failure=_return_none_on_load_failure,
        )

    ctfd_config.get_themes = get_themes
    Assets.manifest = manifest

    def visit(loader):
        if isinstance(loader, ThemeLoader):
            if root not in loader.searchpath:
                loader.searchpath.append(root)
        elif isinstance(loader, ChoiceLoader):
            for child in loader.loaders:
                visit(child)
        elif isinstance(loader, PrefixLoader):
            if "core" in loader.mapping:
                for name in installed_themes(app):
                    register_theme_prefix(loader, name, root, ThemeLoader)

    visit(app.jinja_loader)
    app.extensions["ctf_platform_theme_loader"] = (
        app.jinja_loader,
        root,
        ThemeLoader,
    )

    @app.before_request
    def serve_uploaded_theme_assets():
        themes = installed_themes(app)
        for name in themes:
            register_installed_theme(app, name)

        if request.endpoint not in ("views.themes", "views.themes_beta"):
            return None

        theme = (request.view_args or {}).get("theme")
        if theme not in themes:
            return None

        path = (request.view_args or {}).get("path", "")
        filename = safe_join(root, theme, "static", path)
        if filename is None or not os.path.isfile(filename):
            abort(404)
        return send_file(filename, max_age=3600)


def register_installed_theme(app, theme_name):
    loader, root, theme_loader = app.extensions["ctf_platform_theme_loader"]

    def visit(current_loader):
        if isinstance(current_loader, ChoiceLoader):
            for child in current_loader.loaders:
                visit(child)
        elif isinstance(current_loader, PrefixLoader) and "core" in current_loader.mapping:
            register_theme_prefix(
                current_loader, theme_name, root, theme_loader
            )

    visit(loader)


def register_theme_prefix(loader, name, root, theme_loader):
    loader.mapping.setdefault(
        name, theme_loader(searchpath=root, theme_name=name)
    )


def uninstall_theme(app, theme_name):
    if not THEME_NAME_PATTERN.fullmatch(theme_name):
        abort(404)
    path = os.path.join(theme_directory(app), theme_name)
    if theme_name not in installed_themes(app):
        abort(404)
    shutil.rmtree(path)

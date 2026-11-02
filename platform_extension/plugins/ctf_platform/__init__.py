"""
CTF Platform Plugin - Custom extension for CTFd.

This plugin adds platform-specific functionality on top of the stock CTFd
installation.  It is loaded automatically by CTFd's plugin discovery mechanism
(CTFd/plugins/__init__.py → init_plugins) because it exposes a ``load(app)``
function.

The plugin source lives *outside* the CTFd repository and is bind-mounted into
the container via docker-compose.override.yml so that the upstream CTFd
codebase stays completely unmodified.

Architecture Notes
------------------
* All custom routes are registered under a Flask Blueprint with the URL
  prefix ``/platform``.
* Plugin static assets (CSS / JS) are served via CTFd's built-in
  ``register_plugin_assets_directory`` helper.
* An admin-side menu link is added so administrators can reach the
  platform dashboard from the CTFd admin panel.
"""

import os

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from CTFd.plugins import (
    register_plugin_assets_directory,
    register_admin_plugin_menu_bar,
)
from CTFd.utils import get_config
from CTFd.utils.decorators import admins_only
from CTFd.models import Users, db
from CTFd.plugins.migrations import upgrade

from .theme_manager import (
    MAX_ARCHIVE_SIZE,
    ThemePackageError,
    configure_theme_loader,
    install_theme_archive,
    installed_themes,
    register_installed_theme,
    uninstall_theme,
)
from .hoster import hoster_bp
from .models import PlatformRole
from .roles import platform_admins_only

# ---------------------------------------------------------------------------
# Plugin metadata
# ---------------------------------------------------------------------------
PLUGIN_NAME = "ctf_platform"
PLUGIN_VERSION = "0.1.0"

# ---------------------------------------------------------------------------
# Blueprint
# ---------------------------------------------------------------------------
platform_bp = Blueprint(
    "ctf_platform",
    __name__,
    static_folder="assets",
    url_prefix="/platform",
)


# ---------------------------------------------------------------------------
# Health / status endpoint — useful for smoke-testing the plugin
# ---------------------------------------------------------------------------
@platform_bp.route("/status")
def platform_status():
    """Return a simple JSON health-check so we can verify the plugin loaded."""
    return jsonify(
        {
            "success": True,
            "data": {
                "plugin": PLUGIN_NAME,
                "version": PLUGIN_VERSION,
                "status": "healthy",
            },
        }
    )


@platform_bp.route("/admin/dashboard")
@admins_only
def admin_dashboard():
    """Manage trusted, administrator-uploaded CTFd themes."""
    return render_template(
        "plugins/ctf_platform/themes.html",
        themes=installed_themes(current_app),
        active_theme=get_config("ctf_theme"),
    )


@platform_bp.route("/admin/themes/upload", methods=["POST"])
@admins_only
def upload_theme():
    if request.content_length is None:
        abort(411)
    if request.content_length > MAX_ARCHIVE_SIZE + 1024 * 1024:
        abort(413)

    upload = request.files.get("theme")
    if upload is None or not upload.filename:
        flash("Choose a theme ZIP file to upload.", "danger")
        return redirect(url_for("ctf_platform.admin_dashboard"))

    archive_bytes = upload.stream.read(MAX_ARCHIVE_SIZE + 1)
    if len(archive_bytes) > MAX_ARCHIVE_SIZE:
        flash("Theme archive must be 10 MB or smaller.", "danger")
        return redirect(url_for("ctf_platform.admin_dashboard"))

    try:
        theme_name = install_theme_archive(
            current_app, archive_bytes, upload.filename
        )
    except ThemePackageError as error:
        flash(str(error), "danger")
        return redirect(url_for("ctf_platform.admin_dashboard"))

    register_installed_theme(current_app, theme_name)
    flash(
        f"Installed {theme_name}. Select it in Admin Panel → Config → Theme.",
        "success",
    )
    return redirect(url_for("ctf_platform.admin_dashboard"))


@platform_bp.route("/admin/themes/<theme_name>/delete", methods=["POST"])
@admins_only
def delete_theme(theme_name):
    if theme_name == get_config("ctf_theme"):
        flash("Switch to another theme before removing the active theme.", "danger")
    else:
        uninstall_theme(current_app, theme_name)
        flash(f"Removed {theme_name}.", "success")
    return redirect(url_for("ctf_platform.admin_dashboard"))


@platform_bp.route("/admin/roles", methods=["GET"])
@platform_admins_only
def manage_roles():
    hosters = (
        Users.query.join(PlatformRole, PlatformRole.user_id == Users.id)
        .filter(PlatformRole.role == "hoster")
        .order_by(Users.name.asc())
        .all()
    )
    participants = (
        Users.query.filter_by(type="user")
        .filter(~Users.id.in_([user.id for user in hosters]))
        .order_by(Users.name.asc())
        .all()
    )
    return render_template(
        "plugins/ctf_platform/roles.html",
        hosters=hosters,
        participants=participants,
    )


@platform_bp.route("/admin/roles/hosters", methods=["POST"])
@platform_admins_only
def grant_hoster():
    user_id = request.form.get("user_id", type=int)
    user = Users.query.filter_by(id=user_id, type="user").first()
    if user is None:
        abort(404)

    role = PlatformRole.query.filter_by(user_id=user.id).first()
    if role is None:
        from CTFd.utils.user import get_current_user

        actor = get_current_user()
        db.session.add(
            PlatformRole(
                user_id=user.id,
                role="hoster",
                granted_by=actor.id if actor else None,
            )
        )
        db.session.commit()
    flash(f"{user.name} is now a Hoster.", "success")
    return redirect(url_for("ctf_platform.manage_roles"))


@platform_bp.route("/admin/roles/hosters/<int:user_id>/revoke", methods=["POST"])
@platform_admins_only
def revoke_hoster(user_id):
    role = PlatformRole.query.filter_by(user_id=user_id, role="hoster").first_or_404()
    db.session.delete(role)
    db.session.commit()
    flash("Hoster access revoked.", "success")
    return redirect(url_for("ctf_platform.manage_roles"))


# ---------------------------------------------------------------------------
# Plugin entry point — called by CTFd's init_plugins()
# ---------------------------------------------------------------------------
def load(app):
    """
    Called by CTFd during application startup.

    1. Registers the plugin Blueprint.
    2. Serves static assets under /plugins/ctf_platform/assets/.
    3. Adds an "Platform" link to the admin sidebar.
    """
    # Register the Blueprint so Flask knows about /platform/* routes
    app.register_blueprint(platform_bp)
    app.register_blueprint(hoster_bp)
    upgrade(plugin_name="ctf_platform")
    app.config.setdefault(
        "CTF_PLATFORM_THEME_DIR",
        os.path.join(
            app.config.get("UPLOAD_FOLDER") or "/var/uploads",
            "platform-themes",
        ),
    )
    configure_theme_loader(app)

    # Serve CSS / JS assets at /plugins/ctf_platform/assets/<path>
    register_plugin_assets_directory(
        app, base_path="/plugins/ctf_platform/assets/"
    )

    # Add a link in the CTFd admin panel sidebar
    register_admin_plugin_menu_bar(
        title="Platform",
        route="/platform/admin/dashboard",
    )

    print(f" * CTF Platform plugin v{PLUGIN_VERSION} loaded successfully")

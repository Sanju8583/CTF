# Platform themes

The bundled `platform_theme/` is an example theme and is not forced on the
site. CTFd keeps its existing theme active until an administrator changes it.

## Install a theme from the web UI

1. Package the theme as a ZIP with `templates/base.html` and files under
   `static/`. An enclosing folder is optional. Theme templates can inherit
   CTFd's core templates when `THEME_FALLBACK` is enabled.
2. Sign in as a CTFd administrator, open **Platform** in the admin navbar,
   and upload the ZIP on the Platform Themes page (maximum 10 MB).
3. Open **Admin Panel → Config → Theme**, choose the newly installed theme,
   and save. Its ID is based on the uploaded ZIP filename (for example,
   `neon.zip` becomes `custom-neon`).

Uploaded files are extracted to CTFd's persistent upload volume, outside the
upstream source tree. No restart is required to install or select a theme.
CTFd's theme setting is site-wide, so the selected theme applies to everyone
using that CTFd instance.

Only upload themes from sources you trust. Templates and JavaScript execute
as code in the application and visitors' browsers. The upload handler rejects
unsafe archive paths, symbolic links, duplicate files, and oversized packages.

For operator-managed themes, a directory can still be mounted read-only into
`/opt/CTFd/CTFd/themes/<theme-name>` using `CTFd/docker-compose.override.yml`.

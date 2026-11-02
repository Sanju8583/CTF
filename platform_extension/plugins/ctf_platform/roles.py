import functools

from flask import abort, redirect, request, url_for

from CTFd.utils.user import authed, get_current_user, is_admin

from .models import PlatformRole


def is_hoster():
    user = get_current_user()
    if user is None or user.type != "user":
        return False
    return (
        PlatformRole.query.filter_by(user_id=user.id, role="hoster").first()
        is not None
    )


def platform_admins_only(function):
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        if is_admin():
            return function(*args, **kwargs)
        if request.is_json:
            abort(403)
        if authed():
            abort(403)
        return redirect(url_for("auth.login", next=request.full_path))

    return wrapped


def hosters_or_admins_only(function):
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        if is_admin() or is_hoster():
            return function(*args, **kwargs)
        if request.is_json:
            abort(403)
        if not authed():
            return redirect(url_for("auth.login", next=request.full_path))
        abort(403)

    return wrapped

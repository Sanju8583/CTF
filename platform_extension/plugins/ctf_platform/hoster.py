from types import SimpleNamespace

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from CTFd.cache import clear_challenges, clear_pages
from CTFd.exceptions.challenges import (
    ChallengeCreateException,
    ChallengeUpdateException,
)
from CTFd.models import ChallengeFiles, Challenges, Flags, Pages, db
from CTFd.plugins.challenges import get_chal_class
from CTFd.schemas.challenges import ChallengeSchema
from CTFd.schemas.pages import PageSchema
from CTFd.utils import uploads

from .roles import hosters_or_admins_only

hoster_bp = Blueprint("ctf_platform_hoster", __name__, url_prefix="/platform/hoster")


def _static_flag_values(challenge):
    return "\n".join(
        flag.content
        for flag in Flags.query.filter_by(
            challenge_id=challenge.id, type="static"
        ).all()
    )


def _save_static_flags(challenge, flag_text):
    Flags.query.filter_by(challenge_id=challenge.id, type="static").delete()
    for content in flag_text.splitlines():
        content = content.strip()
        if content:
            db.session.add(
                Flags(
                    challenge_id=challenge.id,
                    type="static",
                    content=content,
                    data="case_sensitive",
                )
            )
    db.session.commit()


def _challenge_request():
    form = request.form.copy()
    form.pop("hoster_flags", None)
    form.pop("nonce", None)
    return SimpleNamespace(form=form, get_json=lambda: {})


@hoster_bp.route("/")
@hosters_or_admins_only
def dashboard():
    return render_template(
        "plugins/ctf_platform/hoster_dashboard.html",
        challenges=Challenges.query.order_by(Challenges.id.desc()).all(),
        pages=Pages.query.order_by(Pages.id.desc()).all(),
    )


@hoster_bp.route("/challenges/new", methods=["GET", "POST"])
@hosters_or_admins_only
def challenge_new():
    if request.method == "POST":
        data = request.form.to_dict()
        data["type"] = "standard"
        response = ChallengeSchema().load(data)
        if response.errors:
            flash(str(response.errors), "danger")
            return render_template(
                "plugins/ctf_platform/hoster_challenge_form.html", challenge=None
            )
        try:
            challenge = get_chal_class("standard").create(_challenge_request())
        except ChallengeCreateException as error:
            flash(str(error), "danger")
            return render_template(
                "plugins/ctf_platform/hoster_challenge_form.html", challenge=None
            )
        _save_static_flags(challenge, request.form.get("hoster_flags", ""))
        clear_challenges()
        flash("Challenge created.", "success")
        return redirect(url_for("ctf_platform_hoster.dashboard"))

    return render_template(
        "plugins/ctf_platform/hoster_challenge_form.html", challenge=None
    )


@hoster_bp.route("/challenges/<int:challenge_id>", methods=["GET", "POST"])
@hosters_or_admins_only
def challenge_edit(challenge_id):
    challenge = Challenges.query.filter_by(id=challenge_id).first_or_404()
    if challenge.type != "standard":
        abort(
            403,
            description="Hoster editing is currently limited to standard challenges.",
        )
    if request.method == "POST":
        data = request.form.to_dict()
        response = ChallengeSchema().load(data)
        if response.errors:
            flash(str(response.errors), "danger")
            return render_template(
                "plugins/ctf_platform/hoster_challenge_form.html",
                challenge=challenge,
                flags=_static_flag_values(challenge),
            )
        try:
            get_chal_class(challenge.type).update(challenge, _challenge_request())
        except ChallengeUpdateException as error:
            flash(str(error), "danger")
            return render_template(
                "plugins/ctf_platform/hoster_challenge_form.html",
                challenge=challenge,
                flags=_static_flag_values(challenge),
            )
        _save_static_flags(challenge, request.form.get("hoster_flags", ""))
        clear_challenges()
        flash("Challenge updated.", "success")
        return redirect(url_for("ctf_platform_hoster.dashboard"))

    return render_template(
        "plugins/ctf_platform/hoster_challenge_form.html",
        challenge=challenge,
        flags=_static_flag_values(challenge),
    )


@hoster_bp.route("/challenges/<int:challenge_id>/files", methods=["POST"])
@hosters_or_admins_only
def challenge_file_upload(challenge_id):
    Challenges.query.filter_by(id=challenge_id).first_or_404()
    file_obj = request.files.get("file")
    if file_obj is None or not file_obj.filename:
        flash("Choose a challenge file to upload.", "danger")
    else:
        uploads.upload_file(file=file_obj, challenge_id=challenge_id, type="challenge")
        flash("Challenge file uploaded.", "success")
    return redirect(
        url_for("ctf_platform_hoster.challenge_edit", challenge_id=challenge_id)
    )


@hoster_bp.route(
    "/challenges/<int:challenge_id>/files/<int:file_id>/delete", methods=["POST"]
)
@hosters_or_admins_only
def challenge_file_delete(challenge_id, file_id):
    file_record = ChallengeFiles.query.filter_by(
        id=file_id, challenge_id=challenge_id
    ).first_or_404()
    uploads.delete_file(file_record.id)
    flash("Challenge file removed.", "success")
    return redirect(
        url_for("ctf_platform_hoster.challenge_edit", challenge_id=challenge_id)
    )


@hoster_bp.route("/pages/new", methods=["GET", "POST"])
@hosters_or_admins_only
def page_new():
    if request.method == "POST":
        response = PageSchema().load(request.form.to_dict())
        if response.errors:
            flash(str(response.errors), "danger")
            return render_template(
                "plugins/ctf_platform/hoster_page_form.html", page=None
            )
        if Pages.query.filter_by(route=response.data.route).first():
            flash("A page already uses this route.", "danger")
            return render_template(
                "plugins/ctf_platform/hoster_page_form.html", page=None
            )
        db.session.add(response.data)
        db.session.commit()
        db.session.close()
        clear_pages()
        flash("Page created.", "success")
        return redirect(url_for("ctf_platform_hoster.dashboard"))

    return render_template("plugins/ctf_platform/hoster_page_form.html", page=None)


@hoster_bp.route("/pages/<int:page_id>", methods=["GET", "POST"])
@hosters_or_admins_only
def page_edit(page_id):
    page = Pages.query.filter_by(id=page_id).first_or_404()
    if request.method == "POST":
        response = PageSchema(partial=True).load(
            request.form.to_dict(), instance=page, partial=True
        )
        if response.errors:
            flash(str(response.errors), "danger")
            return render_template(
                "plugins/ctf_platform/hoster_page_form.html", page=page
            )
        if Pages.query.filter(
            Pages.route == response.data.route, Pages.id != page.id
        ).first():
            flash("A page already uses this route.", "danger")
            return render_template(
                "plugins/ctf_platform/hoster_page_form.html", page=page
            )
        db.session.commit()
        db.session.close()
        clear_pages()
        flash("Page updated.", "success")
        return redirect(url_for("ctf_platform_hoster.dashboard"))

    return render_template("plugins/ctf_platform/hoster_page_form.html", page=page)

from CTFd.models import db


class PlatformRole(db.Model):
    __tablename__ = "ctf_platform_roles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    role = db.Column(db.String(32), nullable=False, default="hoster")
    granted_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

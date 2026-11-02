import sqlalchemy as sa

from CTFd.plugins.migrations import get_all_tables

revision = "c4a91d2b7e30"
down_revision = None
branch_labels = None
depends_on = None


def upgrade(op=None):
    if "ctf_platform_roles" not in get_all_tables(op=op):
        op.create_table(
            "ctf_platform_roles",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column(
                "role", sa.String(length=32), nullable=False, server_default="hoster"
            ),
            sa.Column("granted_by", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(
                ["user_id"], ["users.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["granted_by"], ["users.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id"),
        )


def downgrade(op=None):
    if "ctf_platform_roles" in get_all_tables(op=op):
        op.drop_table("ctf_platform_roles")

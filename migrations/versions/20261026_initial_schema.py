"""Create initial LocalBiz Manager schema.

Revision ID: 20261026_initial
Revises:
"""
from alembic import op

from app import db
from app import models  # noqa: F401

revision = "20261026_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    db.metadata.create_all(bind=op.get_bind())


def downgrade():
    db.metadata.drop_all(bind=op.get_bind())

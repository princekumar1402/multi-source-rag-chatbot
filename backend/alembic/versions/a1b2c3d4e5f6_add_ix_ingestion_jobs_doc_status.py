"""add_ix_ingestion_jobs_doc_status

Revision ID: a1b2c3d4e5f6
Revises: 0c055b1c7da5
Create Date: 2026-10-05 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '0c055b1c7da5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Use if_not_exists logic or safe creation
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_indexes = [idx["name"] for idx in inspector.get_indexes("ingestion_jobs")]
    if "ix_ingestion_jobs_doc_status" not in existing_indexes:
        op.create_index(
            "ix_ingestion_jobs_doc_status",
            "ingestion_jobs",
            ["document_id", "status"],
            unique=False
        )

def downgrade() -> None:
    op.drop_index("ix_ingestion_jobs_doc_status", table_name="ingestion_jobs")

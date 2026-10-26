"""Edges per index generation, so a refresh builds a candidate next to the serving edges.

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE kb_edges ADD COLUMN generation text NOT NULL DEFAULT '';
        ALTER TABLE kb_edges ALTER COLUMN generation DROP DEFAULT;
        ALTER TABLE kb_edges DROP CONSTRAINT kb_edges_pkey;
        ALTER TABLE kb_edges ADD PRIMARY KEY (generation, src_id, rel, dst_id, origin);
        """
    )


def downgrade() -> None:
    """Keeps only the newest generation's edges; run `make index` afterwards."""
    op.execute(
        """
        DELETE FROM kb_edges WHERE generation <> (SELECT max(generation) FROM kb_edges);
        ALTER TABLE kb_edges DROP CONSTRAINT kb_edges_pkey;
        ALTER TABLE kb_edges DROP COLUMN generation;
        ALTER TABLE kb_edges ADD PRIMARY KEY (src_id, rel, dst_id, origin);
        """
    )

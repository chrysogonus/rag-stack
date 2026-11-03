"""Edges per knowledge base (the index alias, QDRANT_COLLECTION), so packs sharing one Postgres
keep their own: a refresh's cleanup of old generations deletes only its own knowledge base's.
And edges in the order they were written (`seq`): the retriever caps a unit's neighbors in that
order, which a query without ORDER BY left to the plan Postgres picked.

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision = "0003"
down_revision = "0002"


def upgrade() -> None:
    # Every edge so far is the cybersecurity pack's, served as kb_chunks. Adding `seq` rewrites
    # the table in its physical order, which is the order the edges were written in.
    op.execute(
        """
        ALTER TABLE kb_edges ADD COLUMN kb text NOT NULL DEFAULT 'kb_chunks';
        ALTER TABLE kb_edges ALTER COLUMN kb DROP DEFAULT;
        ALTER TABLE kb_edges ADD COLUMN seq bigint GENERATED ALWAYS AS IDENTITY;
        ALTER TABLE kb_edges DROP CONSTRAINT kb_edges_pkey;
        ALTER TABLE kb_edges ADD PRIMARY KEY (kb, generation, src_id, rel, dst_id, origin);
        """
    )


def downgrade() -> None:
    """Keeps only kb_chunks's edges; other knowledge bases need `make index` afterwards."""
    op.execute(
        """
        DELETE FROM kb_edges WHERE kb <> 'kb_chunks';
        ALTER TABLE kb_edges DROP CONSTRAINT kb_edges_pkey;
        ALTER TABLE kb_edges DROP COLUMN seq;
        ALTER TABLE kb_edges DROP COLUMN kb;
        ALTER TABLE kb_edges ADD PRIMARY KEY (generation, src_id, rel, dst_id, origin);
        """
    )

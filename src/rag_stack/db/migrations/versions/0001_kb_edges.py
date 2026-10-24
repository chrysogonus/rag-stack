"""Knowledge-base relationships between native IDs (ATLAS, OWASP mappings, CVE -> CWE).

Revision ID: 0001
Revises:
"""

from alembic import op

revision = "0001"
down_revision = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE kb_edges (
            src_id text NOT NULL,
            rel text NOT NULL,
            dst_id text NOT NULL,
            origin text NOT NULL,
            PRIMARY KEY (src_id, rel, dst_id, origin)
        );
        CREATE INDEX kb_edges_dst_id ON kb_edges (dst_id);
        CREATE INDEX kb_edges_origin ON kb_edges (origin);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE kb_edges")

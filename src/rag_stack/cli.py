"""Command line: ingest, index, refresh, ask, eval. Run `uv run python -m rag_stack.cli --help`."""

import argparse
import asyncio
import logging
import sys

from rag_stack.config import Settings
from rag_stack.ingestion.pipeline import MODULES


def ingest(settings: Settings, source: str) -> list[str]:
    """Ingest one source or all; returns the sources that failed."""
    from rag_stack.ingestion.pipeline import ingest, make_fetcher

    fetcher = make_fetcher(settings)
    failed = []
    for source_id in MODULES if source == "all" else [source]:
        try:
            print(ingest(source_id, settings, fetcher), flush=True)
        except Exception as error:  # one unreachable source must not stop the others
            logging.exception("ingest %s failed", source_id)
            print(f"{source_id}: FAILED ({error})", flush=True)
            failed.append(source_id)
    return failed


def refresh(settings: Settings, command: str, force: bool) -> int:
    from qdrant_client import QdrantClient

    from rag_stack import refresh as kb
    from rag_stack.llm.factory import create_embedder, create_reranker, create_sparse_embedder

    def load_models():
        return (
            create_embedder(settings.embedding_model),
            create_sparse_embedder(settings.sparse_model),
            create_reranker(settings.reranker_model),
        )

    client = QdrantClient(url=settings.qdrant_url)
    try:
        with kb.locked(settings):
            if command == "rollback":
                code, line = kb.rollback(settings, client)
            else:
                failed = ingest(settings, "all")
                code, line = asyncio.run(kb.refresh(settings, client, failed, load_models, force))
    except BlockingIOError:
        print("another refresh or index is running", file=sys.stderr)
        return 1
    print(line)
    return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rag-stack")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest_cmd = commands.add_parser("ingest", help="fetch, snapshot and chunk sources")
    ingest_cmd.add_argument("source", choices=[*MODULES, "all"])
    index_cmd = commands.add_parser("index", help="embed processed chunks into Qdrant")
    index_cmd.add_argument("source", nargs="?", default="all", choices=[*MODULES, "all"])
    refresh_cmd = commands.add_parser(
        "refresh", help="ingest all sources, check and score a new index, promote it if it passes"
    )
    refresh_cmd.add_argument(
        "--force", action="store_true", help="build even if a source shrank by more than 10%%"
    )
    commands.add_parser("rollback", help="serve the previous index generation again")
    ask_cmd = commands.add_parser("ask", help="answer one question from the knowledge base")
    ask_cmd.add_argument("question")
    run_eval = commands.add_parser(
        "eval", help="run the golden set (RAG vs. baseline), write the report"
    )
    run_eval.add_argument(
        "--retrieval-only",
        action="store_true",
        help="only score retrieval (recall@10, MRR, time): no LLM calls, nothing written",
    )
    run_eval.add_argument(
        "--split",
        choices=["dev", "test", "all"],
        default="dev",
        help="golden-set split for --retrieval-only: tune on dev, confirm on test",
    )
    draft_cmd = commands.add_parser(
        "eval-draft", help="draft test questions from unasked units into drafts.jsonl for review"
    )
    draft_cmd.add_argument("source", choices=list(MODULES))
    draft_cmd.add_argument(
        "category", choices=["id-exact", "freshness", "german-legal", "cve", "cross-source"]
    )
    draft_cmd.add_argument("-n", type=int, default=5, help="how many drafts (default 5)")
    draft_cmd.add_argument("--seed", type=int, default=0, help="which units are sampled")
    commands.add_parser("eval-labels", help="sample answers into judge_labels.jsonl to label")
    commands.add_parser(
        "eval-agreement", help="judge the labeled answers again and compare with the labels"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    settings = Settings()
    from rag_stack import observability

    observability.configure(settings)
    if args.command == "ingest":
        return 1 if ingest(settings, args.source) else 0
    if args.command in ("refresh", "rollback"):
        return refresh(settings, args.command, getattr(args, "force", False))
    if args.command == "index":
        from rag_stack.refresh import locked
        from rag_stack.retrieval.index import index_all

        try:
            with locked(settings):
                for line in index_all(settings, args.source):
                    print(line, flush=True)
        except BlockingIOError:
            print("another refresh or index is running", file=sys.stderr)
            return 1
        return 0
    if args.command == "ask":
        from rag_stack.agent.ask import ask

        return asyncio.run(ask(settings, args.question))
    if args.command in ("eval-labels", "eval-agreement"):
        from rag_stack.evals import calibration

        if args.command == "eval-labels":
            return asyncio.run(calibration.write_sheet(settings))
        return asyncio.run(calibration.agreement(settings))
    if args.command == "eval-draft":
        from rag_stack.evals import draft

        return asyncio.run(draft.main(settings, args.source, args.category, args.n, args.seed))
    from rag_stack.evals import harness

    if args.retrieval_only:
        return asyncio.run(harness.retrieval_only(settings, split=args.split))
    return asyncio.run(harness.main(settings))


if __name__ == "__main__":
    sys.exit(main())

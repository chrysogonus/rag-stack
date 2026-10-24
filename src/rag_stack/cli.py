"""Command line: ingest, index, ask, eval. Run `uv run python -m rag_stack.cli --help`."""

import argparse
import asyncio
import logging
import sys

from rag_stack.config import Settings
from rag_stack.ingestion.pipeline import MODULES


def ingest(settings: Settings, source: str) -> int:
    from rag_stack.ingestion.pipeline import ingest, make_fetcher

    fetcher = make_fetcher(settings)
    failed = 0
    for source_id in MODULES if source == "all" else [source]:
        try:
            print(ingest(source_id, settings, fetcher), flush=True)
        except Exception as error:  # one unreachable source must not stop the others
            logging.exception("ingest %s failed", source_id)
            print(f"{source_id}: FAILED ({error})", flush=True)
            failed += 1
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rag-stack")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest_cmd = commands.add_parser("ingest", help="fetch, snapshot and chunk sources")
    ingest_cmd.add_argument("source", choices=[*MODULES, "all"])
    index_cmd = commands.add_parser("index", help="embed processed chunks into Qdrant")
    index_cmd.add_argument("source", nargs="?", default="all", choices=[*MODULES, "all"])
    ask_cmd = commands.add_parser("ask", help="answer one question from the knowledge base")
    ask_cmd.add_argument("question")
    commands.add_parser("eval", help="run the golden set (RAG vs. baseline), write the report")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    settings = Settings()
    if args.command == "ingest":
        return ingest(settings, args.source)
    if args.command == "index":
        from rag_stack.retrieval.index import index_all

        for line in index_all(settings, args.source):
            print(line, flush=True)
        return 0
    if args.command == "ask":
        from rag_stack.agent.ask import ask

        return asyncio.run(ask(settings, args.question))
    from rag_stack.evals.harness import main as run_eval

    return asyncio.run(run_eval(settings))


if __name__ == "__main__":
    sys.exit(main())

import argparse
import os
import sys
from typing import Any, Iterable

from sqlalchemy import func, select

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.internhunter.common.logging import configure_logging, get_logger
from src.internhunter.embeddings.embedder import embedder
from src.internhunter.search.repository import SearchRepository
from src.internhunter.storage.models import CleanJobDB
from src.internhunter.storage.session import SessionLocal

logger = get_logger(__name__)

QUERY_DEFAULT = "data scientist python machine learning"
EMBEDDING_DIMENSION = 768


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Semantic search smoke test for clean_jobs.")
    parser.add_argument(
        "--query",
        default=QUERY_DEFAULT,
        help=f"Semantic search query text (default: {QUERY_DEFAULT!r})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum number of results to print.",
    )
    return parser.parse_args()


def _embedding_dimension(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return len(value)
    except TypeError:
        return None


def _print_results(results: Iterable[dict[str, Any]]) -> None:
    for idx, row in enumerate(results, start=1):
        title = row.get("title", "Unknown")
        company = row.get("company", "Unknown")
        cities = row.get("cities") or []
        url = row.get("url", "#")
        score = row.get("match_score", "n/a")
        print(f"{idx}. {title}")
        print(f"   company: {company}")
        print(f"   cities: {', '.join(map(str, cities)) if cities else '[]'}")
        print(f"   url: {url}")
        print(f"   match_score: {score}")


def main() -> int:
    configure_logging()
    args = _parse_args()

    with SessionLocal() as session:
        total_clean_jobs = session.execute(select(func.count()).select_from(CleanJobDB)).scalar_one()
        if total_clean_jobs == 0:
            print("No clean_jobs rows found. Run the ETL pipeline first.", file=sys.stderr)
            return 1

        total_with_embeddings = session.execute(
            select(func.count()).select_from(CleanJobDB).where(CleanJobDB.embedding.isnot(None))
        ).scalar_one()
        if total_with_embeddings == 0:
            print("No clean_jobs rows with embeddings found. Run the embedding stage first.", file=sys.stderr)
            return 1

        sample_embedding = session.execute(
            select(CleanJobDB.embedding).where(CleanJobDB.embedding.isnot(None)).limit(1)
        ).scalar_one_or_none()
        stored_dim = _embedding_dimension(sample_embedding)
        if stored_dim is None:
            print("Unable to inspect stored embedding dimensionality.", file=sys.stderr)
            return 1
        if stored_dim != EMBEDDING_DIMENSION:
            print(
                f"Stored embedding dimension mismatch: expected {EMBEDDING_DIMENSION}, got {stored_dim}.",
                file=sys.stderr,
            )
            return 1

    try:
        query_embedding = embedder.generate_embedding(args.query)
    except Exception as exc:
        print(f"Embedding generation failed: {exc}", file=sys.stderr)
        return 1

    query_dim = _embedding_dimension(query_embedding)
    if query_dim != EMBEDDING_DIMENSION:
        print(
            f"Query embedding dimension mismatch: expected {EMBEDDING_DIMENSION}, got {query_dim}.",
            file=sys.stderr,
        )
        return 1

    if query_dim != stored_dim:
        print(
            f"Vector dimension mismatch between query and stored embeddings: query={query_dim}, stored={stored_dim}.",
            file=sys.stderr,
        )
        return 1

    repo = SearchRepository()
    try:
        results = repo.search_jobs_by_similarity(query_embedding, limit=args.limit)
    except Exception as exc:
        print(f"Semantic search failed: {exc}", file=sys.stderr)
        return 1

    if not results:
        print("Semantic search returned no results.", file=sys.stderr)
        return 1

    print(f"Query: {args.query}")
    print(f"Results: {len(results)}")
    _print_results(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

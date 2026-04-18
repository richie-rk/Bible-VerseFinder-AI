"""
Create BM25 index for New Testament Bible verses.

This script:
1. Loads verses from verse_metadata.json (created by create_faiss_index.py)
2. Tokenizes and stems text using Porter stemmer
3. Creates BM25 index using bm25s
4. Saves index to vector_store/bm25_index.bm25s
"""

import json
from pathlib import Path

import bm25s
import Stemmer

from stopwords import BIBLICAL_STOPWORDS
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

# Paths
SCRIPT_DIR = Path(__file__).parent
VECTOR_STORE_DIR = SCRIPT_DIR / "vector_store"
METADATA_PATH = VECTOR_STORE_DIR / "verse_metadata.json"
BM25_INDEX_PATH = VECTOR_STORE_DIR / "bm25_index.bm25s"

console = Console()


def load_metadata() -> list[dict]:
    """Load verse metadata from JSON."""
    if not METADATA_PATH.exists():
        raise FileNotFoundError(
            f"Metadata file not found: {METADATA_PATH}\n"
            "Run create_faiss_index.py first to generate verse_metadata.json"
        )

    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def create_bm25_index(verses: list[dict]) -> bm25s.BM25:
    """Create BM25 index from verses with Porter stemming."""

    console.print("\n[bold cyan]Tokenizing and stemming verses...[/bold cyan]")

    # Extract texts
    texts = [v["text"] for v in verses]

    # Tokenize with Porter stemmer
    # bm25s.tokenize handles: lowercase, split, stemming
    stemmer = Stemmer.Stemmer("english")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Tokenizing", total=1)

        corpus_tokens = bm25s.tokenize(
            texts,
            stemmer=stemmer,
            stopwords=BIBLICAL_STOPWORDS,
            show_progress=False,
        )
        progress.update(task, advance=1)

    console.print(f"[green]Tokenized {len(texts)} verses[/green]")

    # Create and index BM25
    console.print("\n[bold cyan]Building BM25 index...[/bold cyan]")

    bm25 = bm25s.BM25()
    bm25.index(corpus_tokens, show_progress=False)

    console.print(f"[green]BM25 index created with {len(texts)} documents[/green]")

    return bm25


def main():
    console.print("[bold green]" + "=" * 60)
    console.print("[bold green]  Bible Verse Finder AI - BM25 Index Creator")
    console.print("[bold green]" + "=" * 60)

    # Load metadata
    console.print("\n[bold cyan]Loading verse metadata...[/bold cyan]")
    verses = load_metadata()
    console.print(f"[green]Loaded {len(verses)} verses from metadata[/green]")

    # Show sample
    console.print("\n[dim]Sample verse:[/dim]")
    console.print(f"[dim]  {verses[0]['verse_id']}: {verses[0]['text'][:60]}...[/dim]")

    # Create index
    bm25 = create_bm25_index(verses)

    # Save index
    console.print(f"\n[bold cyan]Saving BM25 index to {BM25_INDEX_PATH}...[/bold cyan]")
    bm25.save(str(BM25_INDEX_PATH))

    # Calculate size
    index_size = sum(f.stat().st_size for f in BM25_INDEX_PATH.rglob("*") if f.is_file())
    console.print(f"[green]BM25 index saved: {index_size / 1024:.2f} KB[/green]")

    # Summary
    console.print("\n[bold green]" + "=" * 60)
    console.print("[bold green]  COMPLETE!")
    console.print("[bold green]" + "=" * 60)
    console.print(f"\n[white]Total verses indexed: {len(verses)}[/white]")
    console.print(f"[white]Stemmer: Porter (English)[/white]")
    console.print(f"[white]Stopwords: Biblical custom list ({len(BIBLICAL_STOPWORDS)} words)[/white]")
    console.print(f"\n[white]Index saved to: {BM25_INDEX_PATH}[/white]")


if __name__ == "__main__":
    main()

"""
Create FAISS index for New Testament Bible verses using OpenAI embeddings.

This script:
1. Loads NT verses from web.csv (Book Numbers 40-66)
2. Embeds verses in batches using text-embedding-3-small
3. Creates a FAISS IndexFlatIP index
4. Saves index and metadata to vector_store/
"""

import csv
import json
import os
import time
from pathlib import Path

import faiss
import numpy as np
from openai import OpenAI
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

# Constants
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
BATCH_SIZE = 1000
MAX_RETRIES = 5
RETRY_DELAY = 2  # seconds (doubles on each retry)

# Paths
SCRIPT_DIR = Path(__file__).parent
DATA_PATH = SCRIPT_DIR / "data" / "web.csv"
OUTPUT_DIR = SCRIPT_DIR / "vector_store"
INDEX_PATH = OUTPUT_DIR / "bible_index.faiss"
METADATA_PATH = OUTPUT_DIR / "verse_metadata.json"
ERROR_LOG_PATH = OUTPUT_DIR / "embedding_errors.log"

# NT book numbers (Matthew=40 through Revelation=66)
NT_BOOK_RANGE = range(40, 67)

console = Console()


def load_nt_verses() -> list[dict]:
    """Load New Testament verses from CSV, skipping empty verses."""
    verses = []
    skipped = []

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        # Skip header lines (first 6 lines, header is on line 6)
        for _ in range(5):
            next(f)

        reader = csv.DictReader(f)
        for row in reader:
            book_num = int(row["Book Number"])
            if book_num in NT_BOOK_RANGE:
                text = row["Text"].strip()
                book_name = row["Book Name"]
                chapter = row["Chapter"]
                verse_num = row["Verse"]

                # Skip empty verses (textual variants not in this translation)
                if not text:
                    skipped.append(f"{book_name} {chapter}:{verse_num}")
                    continue

                # Format book name for verse_id (replace spaces with underscores)
                book_id = book_name.replace(" ", "_")

                verses.append({
                    "verse_id": f"{book_id}_{chapter}:{verse_num}",
                    "book": book_name,
                    "chapter": int(chapter),
                    "verse_num": int(verse_num),
                    "text": text,
                })

    if skipped:
        console.print(f"[yellow]Skipped {len(skipped)} empty verses (textual variants):[/yellow]")
        for v in skipped:
            console.print(f"[yellow]  - {v}[/yellow]")

    return verses


def embed_batch_with_retry(
    client: OpenAI,
    texts: list[str],
    batch_num: int
) -> np.ndarray | None:
    """Embed a batch of texts with exponential backoff retry."""
    delay = RETRY_DELAY

    for attempt in range(MAX_RETRIES):
        try:
            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=texts
            )
            embeddings = [item.embedding for item in response.data]
            return np.array(embeddings, dtype=np.float32)

        except Exception as e:
            error_msg = f"Batch {batch_num}, Attempt {attempt + 1}/{MAX_RETRIES}: {type(e).__name__}: {e}"
            console.print(f"[yellow]Retry: {error_msg}[/yellow]")

            # Log error
            with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {error_msg}\n")

            if attempt < MAX_RETRIES - 1:
                time.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                console.print(f"[red]Failed after {MAX_RETRIES} attempts for batch {batch_num}[/red]")
                return None

    return None


def create_index(verses: list[dict]) -> tuple[faiss.IndexFlatIP, list[dict]]:
    """Create FAISS index and metadata from verses."""
    client = OpenAI()  # Uses OPENAI_API_KEY from environment

    all_embeddings = []
    metadata = []
    failed_batches = []
    current_index_id = 0  # Track actual FAISS index position

    total_batches = (len(verses) + BATCH_SIZE - 1) // BATCH_SIZE

    console.print(f"\n[bold cyan]Embedding {len(verses)} verses in {total_batches} batches...[/bold cyan]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Embedding batches", total=total_batches)

        for batch_num in range(total_batches):
            start_idx = batch_num * BATCH_SIZE
            end_idx = min(start_idx + BATCH_SIZE, len(verses))
            batch_verses = verses[start_idx:end_idx]

            texts = [v["text"] for v in batch_verses]
            embeddings = embed_batch_with_retry(client, texts, batch_num + 1)

            if embeddings is not None:
                all_embeddings.append(embeddings)

                # Build metadata for this batch (index_id = actual FAISS position)
                for verse in batch_verses:
                    metadata.append({
                        "index_id": current_index_id,
                        "verse_id": verse["verse_id"],
                        "book": verse["book"],
                        "chapter": verse["chapter"],
                        "verse_num": verse["verse_num"],
                        "text": verse["text"],
                    })
                    current_index_id += 1
            else:
                failed_batches.append((batch_num, start_idx, end_idx))
                console.print(f"[red]Batch {batch_num + 1} failed permanently. Verses {start_idx}-{end_idx} skipped.[/red]")

            progress.update(task, advance=1)

            # Small delay between batches to respect rate limits
            if batch_num < total_batches - 1:
                time.sleep(0.3)

    if failed_batches:
        console.print(f"\n[red]WARNING: {len(failed_batches)} batches failed. Check {ERROR_LOG_PATH}[/red]")
        console.print("[red]Failed verse ranges:[/red]")
        for batch_num, start, end in failed_batches:
            console.print(f"  - Batch {batch_num + 1}: verses {start}-{end}")

    # Combine all embeddings
    if not all_embeddings:
        raise RuntimeError("No embeddings were created. Check your API key and network connection.")

    embeddings_matrix = np.vstack(all_embeddings)

    # Create FAISS index
    console.print(f"\n[bold cyan]Creating FAISS IndexFlatIP with {EMBEDDING_DIM} dimensions...[/bold cyan]")
    index = faiss.IndexFlatIP(EMBEDDING_DIM)

    # Normalize embeddings for cosine similarity (OpenAI embeddings are already normalized, but let's ensure)
    faiss.normalize_L2(embeddings_matrix)
    index.add(embeddings_matrix)

    return index, metadata


def main():
    console.print("[bold green]=" * 60)
    console.print("[bold green]  VerseFinder AI - FAISS Index Creator")
    console.print("[bold green]=" * 60)

    # Check API key
    if not os.environ.get("OPENAI_API_KEY"):
        console.print("[red]Error: OPENAI_API_KEY environment variable not set[/red]")
        return

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Clear previous error log
    if ERROR_LOG_PATH.exists():
        ERROR_LOG_PATH.unlink()

    # Load verses
    console.print("\n[bold cyan]Loading New Testament verses...[/bold cyan]")
    verses = load_nt_verses()
    console.print(f"[green]Loaded {len(verses)} NT verses[/green]")

    # Show sample
    console.print("\n[dim]Sample verse:[/dim]")
    console.print(f"[dim]  {verses[0]}[/dim]")

    # Create index
    index, metadata = create_index(verses)

    # Save index
    console.print(f"\n[bold cyan]Saving index to {INDEX_PATH}...[/bold cyan]")
    faiss.write_index(index, str(INDEX_PATH))
    index_size = INDEX_PATH.stat().st_size / (1024 * 1024)
    console.print(f"[green]Index saved: {index_size:.2f} MB[/green]")

    # Save metadata
    console.print(f"\n[bold cyan]Saving metadata to {METADATA_PATH}...[/bold cyan]")
    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    metadata_size = METADATA_PATH.stat().st_size / (1024 * 1024)
    console.print(f"[green]Metadata saved: {metadata_size:.2f} MB[/green]")

    # Summary
    console.print("\n[bold green]" + "=" * 60)
    console.print("[bold green]  COMPLETE!")
    console.print("[bold green]" + "=" * 60)
    console.print(f"\n[white]Total verses indexed: {len(metadata)}[/white]")
    console.print(f"[white]Index dimensions: {EMBEDDING_DIM}[/white]")
    console.print(f"[white]Index type: IndexFlatIP (cosine similarity)[/white]")
    console.print(f"\n[white]Files created:[/white]")
    console.print(f"[white]  - {INDEX_PATH}[/white]")
    console.print(f"[white]  - {METADATA_PATH}[/white]")


if __name__ == "__main__":
    main()

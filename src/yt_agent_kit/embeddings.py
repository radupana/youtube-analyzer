"""Vector store and embeddings for semantic search over transcripts."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb
from sentence_transformers import SentenceTransformer

INDEX_DIR = Path(".index")
DEFAULT_MODEL = "all-MiniLM-L6-v2"
DEFAULT_CHUNK_SIZE = 1200
DEFAULT_CHUNK_OVERLAP = 200


@dataclass
class Chunk:
    content: str
    video_id: str
    video_title: str
    chunk_index: int


def chunk_transcript(
    text: str,
    video_id: str,
    video_title: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Chunk]:
    if not text:
        return []

    chunks: list[Chunk] = []
    start = 0
    chunk_index = 0

    while start < len(text):
        end = start + chunk_size
        chunk_text = text[start:end]

        if chunk_text.strip():
            chunks.append(
                Chunk(
                    content=chunk_text,
                    video_id=video_id,
                    video_title=video_title,
                    chunk_index=chunk_index,
                )
            )
            chunk_index += 1

        start = end - chunk_overlap
        if start >= len(text) - chunk_overlap:
            break

    return chunks


def _get_collection_path(channel_id: str) -> Path:
    return INDEX_DIR / channel_id


def _get_client(channel_id: str) -> Any:
    path = _get_collection_path(channel_id)
    path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(path))


def build_index(
    channel_id: str,
    transcripts: dict[str, tuple[str, str]],
    model_name: str = DEFAULT_MODEL,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> int:
    if not transcripts:
        return 0

    client = _get_client(channel_id)
    collection = client.get_or_create_collection(name="transcripts")

    existing_ids = set()
    if collection.count() > 0:
        existing_metadata = collection.get()
        for meta in existing_metadata.get("metadatas", []) or []:
            if meta and "video_id" in meta:
                existing_ids.add(meta["video_id"])

    new_transcripts = {
        vid: data for vid, data in transcripts.items() if vid not in existing_ids
    }

    if not new_transcripts:
        return 0

    model = SentenceTransformer(model_name)

    all_chunks: list[Chunk] = []
    for video_id, (title, text) in new_transcripts.items():
        chunks = chunk_transcript(text, video_id, title, chunk_size, chunk_overlap)
        all_chunks.extend(chunks)

    if not all_chunks:
        return 0

    texts = [c.content for c in all_chunks]
    embeddings = model.encode(texts, show_progress_bar=False).tolist()

    ids = [f"{c.video_id}_{c.chunk_index}" for c in all_chunks]
    metadatas = [
        {
            "video_id": c.video_id,
            "video_title": c.video_title,
            "chunk_index": c.chunk_index,
        }
        for c in all_chunks
    ]

    collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)

    return len(new_transcripts)


def search(
    channel_id: str,
    query: str,
    k: int = 8,
    model_name: str = DEFAULT_MODEL,
) -> list[Chunk]:
    path = _get_collection_path(channel_id)
    if not path.exists():
        return []

    client = _get_client(channel_id)

    try:
        collection = client.get_collection(name="transcripts")
    except ValueError:
        return []

    if collection.count() == 0:
        return []

    model = SentenceTransformer(model_name)
    query_embedding = model.encode([query], show_progress_bar=False).tolist()

    results = collection.query(query_embeddings=query_embedding, n_results=k)

    chunks: list[Chunk] = []
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    for doc, meta in zip(documents, metadatas, strict=True):
        if doc and meta:
            chunks.append(
                Chunk(
                    content=doc,
                    video_id=meta.get("video_id", ""),
                    video_title=meta.get("video_title", ""),
                    chunk_index=meta.get("chunk_index", 0),
                )
            )

    return chunks


def get_index_stats(channel_id: str) -> dict[str, int | float]:
    path = _get_collection_path(channel_id)
    if not path.exists():
        return {"total_chunks": 0, "total_videos": 0, "index_size_mb": 0.0}

    client = _get_client(channel_id)

    try:
        collection = client.get_collection(name="transcripts")
    except ValueError:
        return {"total_chunks": 0, "total_videos": 0, "index_size_mb": 0.0}

    total_chunks = collection.count()

    video_ids: set[str] = set()
    if total_chunks > 0:
        all_metadata = collection.get()
        for meta in all_metadata.get("metadatas", []) or []:
            if meta and "video_id" in meta:
                video_ids.add(meta["video_id"])

    size_bytes = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    size_mb = round(size_bytes / (1024 * 1024), 2)

    return {
        "total_chunks": total_chunks,
        "total_videos": len(video_ids),
        "index_size_mb": size_mb,
    }


def delete_videos(channel_id: str, video_ids: set[str]) -> int:
    """Delete videos from the index that are no longer in the transcript set."""
    if not video_ids:
        return 0

    path = _get_collection_path(channel_id)
    if not path.exists():
        return 0

    client = _get_client(channel_id)

    try:
        collection = client.get_collection(name="transcripts")
    except ValueError:
        return 0

    if collection.count() == 0:
        return 0

    all_data = collection.get()
    ids_to_delete: list[str] = []

    for i, meta in enumerate(all_data.get("metadatas", []) or []):
        if meta and meta.get("video_id") in video_ids:
            chunk_id = all_data.get("ids", [])[i]
            ids_to_delete.append(chunk_id)

    if ids_to_delete:
        collection.delete(ids=ids_to_delete)

    return len(video_ids)


def sync_index(
    channel_id: str,
    transcripts: dict[str, tuple[str, str]],
    model_name: str = DEFAULT_MODEL,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> tuple[int, int]:
    """
    Sync the index with the current transcript set.

    Adds new videos and removes videos no longer in the transcript set.

    Returns:
        Tuple of (videos_added, videos_removed)
    """
    path = _get_collection_path(channel_id)

    indexed_video_ids: set[str] = set()
    if path.exists():
        client = _get_client(channel_id)
        try:
            collection = client.get_collection(name="transcripts")
            if collection.count() > 0:
                all_metadata = collection.get()
                for meta in all_metadata.get("metadatas", []) or []:
                    if meta and "video_id" in meta:
                        indexed_video_ids.add(meta["video_id"])
        except ValueError:
            pass

    current_video_ids = set(transcripts.keys())
    videos_to_remove = indexed_video_ids - current_video_ids

    removed = delete_videos(channel_id, videos_to_remove)
    added = build_index(channel_id, transcripts, model_name, chunk_size, chunk_overlap)

    return added, removed

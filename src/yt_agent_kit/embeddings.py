"""Vector store and embeddings for semantic search over transcripts."""

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import chromadb
from sentence_transformers import SentenceTransformer

INDEX_DIR = Path(".index")
DEFAULT_MODEL = "all-MiniLM-L6-v2"
DEFAULT_CHUNK_SIZE = 1200
DEFAULT_CHUNK_OVERLAP = 200
BATCH_SIZE = 1000

COLLECTION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


@dataclass
class Chunk:
    content: str
    video_id: str
    video_title: str
    chunk_index: int


@lru_cache(maxsize=4)
def _get_model(model_name: str) -> SentenceTransformer:
    return SentenceTransformer(model_name)


def _validate_collection_id(collection_id: str) -> None:
    if not collection_id or not COLLECTION_ID_PATTERN.match(collection_id):
        raise ValueError(f"Invalid collection_id: {collection_id}")


def chunk_transcript(
    text: str,
    video_id: str,
    video_title: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Chunk]:
    if not text:
        return []

    if chunk_overlap >= chunk_size:
        raise ValueError(
            f"chunk_overlap ({chunk_overlap}) must be less than chunk_size ({chunk_size})"
        )

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


def _get_collection_path(collection_id: str) -> Path:
    _validate_collection_id(collection_id)
    return INDEX_DIR / collection_id


def _get_client(collection_id: str) -> Any:
    path = _get_collection_path(collection_id)
    path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(path))


def build_index(
    collection_id: str,
    transcripts: dict[str, tuple[str, str]],
    model_name: str = DEFAULT_MODEL,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> int:
    _validate_collection_id(collection_id)

    if not transcripts:
        return 0

    client = _get_client(collection_id)
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

    model = _get_model(model_name)

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

    # ChromaDB has a max batch size limit (~5461), so batch the adds
    batch_size = 5000
    for i in range(0, len(ids), batch_size):
        end = i + batch_size
        collection.add(
            ids=ids[i:end],
            embeddings=embeddings[i:end],
            documents=texts[i:end],
            metadatas=metadatas[i:end],
        )

    return len(new_transcripts)


def search(
    collection_id: str,
    query: str,
    k: int = 8,
    model_name: str = DEFAULT_MODEL,
) -> list[Chunk]:
    path = _get_collection_path(collection_id)
    if not path.exists():
        return []

    client = _get_client(collection_id)

    try:
        collection = client.get_collection(name="transcripts")
    except ValueError:
        return []

    if collection.count() == 0:
        return []

    model = _get_model(model_name)
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


def get_index_stats(collection_id: str) -> dict[str, int | float]:
    path = _get_collection_path(collection_id)
    if not path.exists():
        return {"total_chunks": 0, "total_videos": 0, "index_size_mb": 0.0}

    client = _get_client(collection_id)

    try:
        collection = client.get_collection(name="transcripts")
    except ValueError:
        return {"total_chunks": 0, "total_videos": 0, "index_size_mb": 0.0}

    total_chunks = collection.count()

    video_ids: set[str] = set()
    offset = 0
    while offset < total_chunks:
        batch = collection.get(limit=BATCH_SIZE, offset=offset)
        for meta in batch.get("metadatas", []) or []:
            if meta and "video_id" in meta:
                video_ids.add(meta["video_id"])
        offset += BATCH_SIZE

    size_bytes = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    size_mb = round(size_bytes / (1024 * 1024), 2)

    return {
        "total_chunks": total_chunks,
        "total_videos": len(video_ids),
        "index_size_mb": size_mb,
    }


def delete_videos(collection_id: str, video_ids: set[str]) -> int:
    if not video_ids:
        return 0

    path = _get_collection_path(collection_id)
    if not path.exists():
        return 0

    client = _get_client(collection_id)

    try:
        collection = client.get_collection(name="transcripts")
    except ValueError:
        return 0

    total_count = collection.count()
    if total_count == 0:
        return 0

    ids_to_delete: list[str] = []
    deleted_video_ids: set[str] = set()
    offset = 0

    while offset < total_count:
        batch = collection.get(limit=BATCH_SIZE, offset=offset)
        batch_ids = batch.get("ids", [])
        batch_metadatas = batch.get("metadatas", [])

        for chunk_id, meta in zip(batch_ids, batch_metadatas, strict=True):
            if meta and meta.get("video_id") in video_ids:
                ids_to_delete.append(chunk_id)
                deleted_video_ids.add(meta["video_id"])

        offset += BATCH_SIZE

    if ids_to_delete:
        collection.delete(ids=ids_to_delete)

    return len(deleted_video_ids)


def _get_indexed_video_ids(collection_id: str) -> set[str]:
    path = _get_collection_path(collection_id)
    if not path.exists():
        return set()

    client = _get_client(collection_id)
    try:
        collection = client.get_collection(name="transcripts")
    except ValueError:
        return set()

    total_count = collection.count()
    if total_count == 0:
        return set()

    video_ids: set[str] = set()
    offset = 0
    while offset < total_count:
        batch = collection.get(limit=BATCH_SIZE, offset=offset)
        for meta in batch.get("metadatas", []) or []:
            if meta and "video_id" in meta:
                video_ids.add(meta["video_id"])
        offset += BATCH_SIZE

    return video_ids


def sync_index(
    collection_id: str,
    transcripts: dict[str, tuple[str, str]],
    model_name: str = DEFAULT_MODEL,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> tuple[int, int]:
    indexed_video_ids = _get_indexed_video_ids(collection_id)
    current_video_ids = set(transcripts.keys())
    videos_to_remove = indexed_video_ids - current_video_ids

    removed = delete_videos(collection_id, videos_to_remove)
    added = build_index(
        collection_id, transcripts, model_name, chunk_size, chunk_overlap
    )

    return added, removed

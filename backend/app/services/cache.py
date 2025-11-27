"""Cache service for persistent storage of video metadata and transcripts."""

import json
import logging
import os
from datetime import datetime
from typing import Any

import numpy as np

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class CacheService:
    def __init__(self):
        self.settings = get_settings()
        self.cache_dir = os.environ.get("CACHE_DIR", ".cache")
        self.videos_cache_dir = os.path.join(self.cache_dir, "videos")
        self.transcripts_cache_dir = os.path.join(self.cache_dir, "transcripts")
        self.chunks_cache_dir = os.path.join(self.cache_dir, "chunks")

        os.makedirs(self.videos_cache_dir, exist_ok=True)
        os.makedirs(self.transcripts_cache_dir, exist_ok=True)
        os.makedirs(self.chunks_cache_dir, exist_ok=True)

        logger.info(f"Cache initialized at {self.cache_dir}")

    def _get_video_cache_path(self, video_id: str) -> str:
        """Get the cache file path for a video."""
        return os.path.join(self.videos_cache_dir, f"{video_id}.json")

    def _get_transcript_cache_path(self, video_id: str) -> str:
        """Get the cache file path for a transcript."""
        return os.path.join(self.transcripts_cache_dir, f"{video_id}.json")

    def _get_chunks_cache_path(self, video_id: str) -> str:
        """Get the cache file path for chunks metadata."""
        return os.path.join(self.chunks_cache_dir, f"{video_id}.json")

    def _get_embeddings_cache_path(self, video_id: str) -> str:
        """Get the cache file path for embeddings (numpy binary)."""
        return os.path.join(self.chunks_cache_dir, f"{video_id}.npy")

    def save_video(self, video_data: dict[str, Any]) -> bool:
        """Save video metadata and transcript to cache."""
        try:
            video_id = video_data.get("id")
            if not video_id:
                return False

            # Separate transcript from metadata
            transcript_data = {
                "transcript": video_data.get("transcript", ""),
                "transcript_source": video_data.get("transcript_source", "none"),
                "cached_at": datetime.now().isoformat(),
            }

            # Video metadata (without transcript to keep files smaller)
            metadata = {k: v for k, v in video_data.items() if k not in ["transcript"]}
            metadata["cached_at"] = datetime.now().isoformat()

            # Save metadata
            video_cache_path = self._get_video_cache_path(video_id)
            with open(video_cache_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2, default=str)

            # Save transcript separately if it exists
            if transcript_data["transcript"]:
                transcript_cache_path = self._get_transcript_cache_path(video_id)
                with open(transcript_cache_path, "w", encoding="utf-8") as f:
                    json.dump(transcript_data, f, ensure_ascii=False, indent=2)

            logger.info(
                f"Cached video {video_id}: {metadata.get('title', 'Unknown')[:50]}"
            )
            return True

        except Exception as e:
            logger.error(f"Error caching video {video_id}: {e}")
            return False

    def load_video(self, video_id: str) -> dict[str, Any] | None:
        """Load video metadata and transcript from cache."""
        try:
            video_cache_path = self._get_video_cache_path(video_id)
            transcript_cache_path = self._get_transcript_cache_path(video_id)

            if not os.path.exists(video_cache_path):
                return None

            # Load metadata
            with open(video_cache_path, encoding="utf-8") as f:
                video_data = json.load(f)

            # Load transcript if exists
            if os.path.exists(transcript_cache_path):
                with open(transcript_cache_path, encoding="utf-8") as f:
                    transcript_data = json.load(f)
                    video_data["transcript"] = transcript_data.get("transcript", "")
                    video_data["transcript_source"] = transcript_data.get(
                        "transcript_source", "none"
                    )
            else:
                video_data["transcript"] = ""
                video_data["transcript_source"] = "none"

            logger.info(f"Loaded video from cache: {video_id}")
            return video_data

        except Exception as e:
            logger.error(f"Error loading video {video_id} from cache: {e}")
            return None

    def has_video(self, video_id: str) -> bool:
        """Check if video exists in cache."""
        video_cache_path = self._get_video_cache_path(video_id)
        return os.path.exists(video_cache_path)

    def has_transcript(self, video_id: str) -> bool:
        """Check if transcript exists in cache."""
        transcript_cache_path = self._get_transcript_cache_path(video_id)
        return os.path.exists(transcript_cache_path)

    def save_chunks(
        self,
        video_id: str,
        chunks: list[dict[str, Any]],
        embeddings: np.ndarray,
    ) -> bool:
        """Save chunks metadata and embeddings to cache."""
        try:
            chunks_path = self._get_chunks_cache_path(video_id)
            embeddings_path = self._get_embeddings_cache_path(video_id)

            with open(chunks_path, "w", encoding="utf-8") as f:
                json.dump(chunks, f, ensure_ascii=False)

            np.save(embeddings_path, embeddings)

            logger.info(f"Cached {len(chunks)} chunks for video {video_id}")
            return True

        except Exception as e:
            logger.error(f"Error caching chunks for {video_id}: {e}")
            return False

    def load_chunks(
        self, video_id: str
    ) -> tuple[list[dict[str, Any]], np.ndarray] | None:
        """Load chunks metadata and embeddings from cache."""
        try:
            chunks_path = self._get_chunks_cache_path(video_id)
            embeddings_path = self._get_embeddings_cache_path(video_id)

            if not os.path.exists(chunks_path) or not os.path.exists(embeddings_path):
                return None

            with open(chunks_path, encoding="utf-8") as f:
                chunks = json.load(f)

            embeddings = np.load(embeddings_path)

            logger.info(f"Loaded {len(chunks)} chunks for video {video_id}")
            return chunks, embeddings

        except Exception as e:
            logger.error(f"Error loading chunks for {video_id}: {e}")
            return None

    def has_chunks(self, video_id: str) -> bool:
        """Check if chunks exist in cache."""
        chunks_path = self._get_chunks_cache_path(video_id)
        embeddings_path = self._get_embeddings_cache_path(video_id)
        return os.path.exists(chunks_path) and os.path.exists(embeddings_path)

    def list_cached_videos(self) -> list[str]:
        """List all cached video IDs."""
        try:
            files = os.listdir(self.videos_cache_dir)
            return [f.replace(".json", "") for f in files if f.endswith(".json")]
        except Exception as e:
            logger.error(f"Error listing cached videos: {e}")
            return []

    def clear_cache(self) -> int:
        """Clear all cached videos, transcripts, and chunks."""
        count = 0
        try:
            for file in os.listdir(self.videos_cache_dir):
                if file.endswith(".json"):
                    os.remove(os.path.join(self.videos_cache_dir, file))
                    count += 1

            for file in os.listdir(self.transcripts_cache_dir):
                if file.endswith(".json"):
                    os.remove(os.path.join(self.transcripts_cache_dir, file))

            for file in os.listdir(self.chunks_cache_dir):
                if file.endswith((".json", ".npy")):
                    os.remove(os.path.join(self.chunks_cache_dir, file))

            logger.info(f"Cleared {count} videos from cache")
            return count

        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return count

    def get_cache_size(self) -> dict[str, Any]:
        """Get cache statistics."""
        try:
            video_count = len(self.list_cached_videos())

            # Calculate total size
            total_size = 0
            for root, _dirs, files in os.walk(self.cache_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)

            return {
                "video_count": video_count,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "cache_dir": self.cache_dir,
            }

        except Exception as e:
            logger.error(f"Error getting cache size: {e}")
            return {"video_count": 0, "total_size_mb": 0, "error": str(e)}


# Singleton instance
_cache_service = None


def get_cache_service() -> CacheService:
    """Get or create the cache service singleton."""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service

"""Chat session for conversational RAG over YouTube content."""

from dataclasses import dataclass, field

from .config import EmbeddingsConfig, LLMConfig, SearchConfig
from .embeddings import Chunk, build_index, search
from .llm import Message, call_llm

SYSTEM_PROMPT = """You are a helpful AI assistant with knowledge from YouTube videos.
Answer questions based ONLY on the provided video transcript context.
Always cite the video title(s) you used in your answer.
If you cannot find relevant information in the provided context, say so."""

MAX_HISTORY_MESSAGES = 20
CONTEXT_BUFFER_RATIO = 0.6


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 characters per token."""
    return len(text) // 4


@dataclass
class ChatSession:
    collection_id: str
    llm_config: LLMConfig
    transcripts: dict[str, str]
    video_titles: dict[str, str]
    context_limit: int
    search_config: SearchConfig = field(default_factory=SearchConfig)
    embeddings_config: EmbeddingsConfig = field(default_factory=EmbeddingsConfig)
    history: list[Message] = field(default_factory=list)
    _embeddings_ready: bool = field(default=False, init=False)
    _full_context_mode: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        total_chars = sum(len(t) for t in self.transcripts.values())
        estimated_tokens = total_chars // 4  # ~4 chars per token
        usable_limit = int(self.context_limit * CONTEXT_BUFFER_RATIO)
        self._full_context_mode = estimated_tokens < usable_limit

    def _ensure_embeddings_ready(self) -> None:
        """Lazily initialize embeddings index when first needed."""
        if self._embeddings_ready:
            return
        # Combine transcripts and titles into format expected by build_index
        transcripts_with_titles = {
            vid: (self.video_titles.get(vid, vid), content)
            for vid, content in self.transcripts.items()
        }
        build_index(
            self.collection_id,
            transcripts_with_titles,
            chunk_size=self.embeddings_config.chunk_size,
            chunk_overlap=self.embeddings_config.chunk_overlap,
        )
        self._embeddings_ready = True

    def _format_all_transcripts(self) -> str:
        """Format all transcripts for full-context mode."""
        parts: list[str] = []
        for video_id, transcript in self.transcripts.items():
            title = self.video_titles.get(video_id, video_id)
            parts.append(f'=== Video: "{title}" ===\n{transcript}')
        return "\n\n".join(parts)

    def _format_chunks(self, chunks: list[Chunk]) -> str:
        if not chunks:
            return "No relevant context found."
        formatted_parts: list[str] = []
        for chunk in chunks:
            formatted_parts.append(f'[Video: "{chunk.video_title}"]\n"{chunk.content}"')
        return "\n---\n".join(formatted_parts)

    def _build_messages(self, user_content: str) -> list[Message]:
        messages: list[Message] = [Message(role="system", content=SYSTEM_PROMPT)]
        history_slice = (
            self.history[-MAX_HISTORY_MESSAGES:]
            if len(self.history) > MAX_HISTORY_MESSAGES
            else self.history
        )
        for msg in history_slice:
            messages.append(msg)
        messages.append(Message(role="user", content=user_content))
        return messages

    def _get_context(self, question: str) -> str:
        """Get context using full-context or RAG mode."""
        if self._full_context_mode:
            context = self._format_all_transcripts()
            history_text = "".join(m.content for m in self.history)
            total_tokens = estimate_tokens(context + history_text + question)
            if total_tokens < self.context_limit * 0.9:
                return context
            self._full_context_mode = False

        self._ensure_embeddings_ready()
        chunks = search(self.collection_id, question, k=self.search_config.top_k)
        return self._format_chunks(chunks)

    def ask(self, question: str) -> str:
        context = self._get_context(question)
        user_content = (
            f"Context from videos:\n---\n{context}\n---\n\nQuestion: {question}"
        )
        messages = self._build_messages(user_content)
        response = call_llm(messages, self.llm_config)
        self.history.append(Message(role="user", content=user_content))
        self.history.append(Message(role="assistant", content=response))
        return response

    def clear_history(self) -> None:
        self.history.clear()

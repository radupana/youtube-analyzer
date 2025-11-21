"""Chat session for conversational RAG over YouTube content."""

from dataclasses import dataclass, field

from .config import LLMConfig, SearchConfig
from .embeddings import Chunk, search
from .llm import Message, call_llm

SYSTEM_PROMPT = """You are a helpful AI assistant with knowledge from YouTube videos.
Answer questions based ONLY on the provided video transcript context.
Always cite the video title(s) you used in your answer.
If you cannot find relevant information in the provided context, say so."""

MAX_HISTORY_MESSAGES = 20


@dataclass
class ChatSession:
    collection_id: str
    llm_config: LLMConfig
    search_config: SearchConfig = field(default_factory=SearchConfig)
    history: list[Message] = field(default_factory=list)

    def _format_context(self, chunks: list[Chunk]) -> str:
        if not chunks:
            return "No relevant context found."

        formatted_parts: list[str] = []
        for chunk in chunks:
            formatted_parts.append(f'[Video: "{chunk.video_title}"]\n"{chunk.content}"')
        return "\n---\n".join(formatted_parts)

    def _build_messages(self, user_content: str) -> list[Message]:
        messages: list[Message] = [Message(role="system", content=SYSTEM_PROMPT)]

        # Avoid allocating new list if history is short
        history_slice = (
            self.history[-MAX_HISTORY_MESSAGES:]
            if len(self.history) > MAX_HISTORY_MESSAGES
            else self.history
        )
        for msg in history_slice:
            messages.append(msg)

        messages.append(Message(role="user", content=user_content))

        return messages

    def ask(self, question: str) -> str:
        chunks = search(
            self.collection_id,
            question,
            k=self.search_config.top_k,
        )

        context = self._format_context(chunks)
        # Include context in the user message that gets stored in history
        # This ensures multi-turn conversations have consistent context
        user_content = (
            f"Context from videos:\n---\n{context}\n---\n\nQuestion: {question}"
        )
        messages = self._build_messages(user_content)

        response = call_llm(messages, self.llm_config)

        # Store the full context-augmented message so history is consistent
        self.history.append(Message(role="user", content=user_content))
        self.history.append(Message(role="assistant", content=response))

        return response

    def clear_history(self) -> None:
        self.history.clear()

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

    def _build_messages(self, question: str, context: str) -> list[Message]:
        messages: list[Message] = [Message(role="system", content=SYSTEM_PROMPT)]

        for msg in self.history[-MAX_HISTORY_MESSAGES:]:
            messages.append(msg)

        user_content = (
            f"Context from videos:\n---\n{context}\n---\n\nQuestion: {question}"
        )
        messages.append(Message(role="user", content=user_content))

        return messages

    def ask(self, question: str) -> str:
        chunks = search(
            self.collection_id,
            question,
            k=self.search_config.top_k,
        )

        context = self._format_context(chunks)
        messages = self._build_messages(question, context)

        response = call_llm(messages, self.llm_config)

        self.history.append(Message(role="user", content=question))
        self.history.append(Message(role="assistant", content=response))

        return response

    def clear_history(self) -> None:
        self.history.clear()

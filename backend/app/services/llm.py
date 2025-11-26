"""LLM service for chat functionality using Gemini."""

from typing import Any

import google.generativeai as genai

from app.core.config import get_settings


class LLMService:
    def __init__(self):
        self.settings = get_settings()
        genai.configure(api_key=self.settings.gemini_api_key)
        self.model = genai.GenerativeModel(self.settings.llm_model)

    def chat_with_context(
        self, message: str, video_transcripts: list[dict[str, Any]]
    ) -> str:
        """Process a chat message with video context."""

        # Build context from loaded videos
        if not video_transcripts:
            context = "No videos have been loaded yet."
        else:
            context = "You have access to the following video transcripts:\n\n"
            for video in video_transcripts:
                context += f"**{video['title']}** by {video['channel_title']}\n"
                if video.get("transcript"):
                    # Truncate very long transcripts for context
                    transcript = video["transcript"]
                    if len(transcript) > 5000:
                        transcript = transcript[:5000] + "... (truncated)"
                    context += f"Transcript: {transcript}\n\n"
                else:
                    context += "Transcript: Not available\n\n"

        # Create prompt
        prompt = f"""You are an AI assistant analyzing YouTube video content.
You have been given transcripts of videos that the user has loaded.

Context of loaded videos:
{context}

User question: {message}

Please provide a helpful response based on the video content available.
If the question cannot be answered from the available videos, say so clearly."""

        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error generating response: {str(e)}"

#!/usr/bin/env python3
"""
YouTube Analyzer CLI entry point.
"""
import argparse
import logging
import sys
from pathlib import Path

from .config import load_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def mask_sensitive(value: str | None) -> str:
    """Mask sensitive data like API keys for logging."""
    return "<SET>" if value else "<NOT SET>"


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze YouTube channel transcripts with LLMs (Conversational Agent)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # Start conversational agent
  %(prog)s --config custom.yaml        # Use different config file
  %(prog)s --max-videos 10             # Limit videos processed
  %(prog)s --output results.json       # Override output file
        """,
    )

    parser.add_argument(
        "--config", type=Path, help="Path to config file (default: config.yaml)"
    )
    parser.add_argument(
        "--max-videos", type=int, help="Maximum videos to process (overrides config)"
    )
    parser.add_argument("--output", help="Output file path (overrides config)")

    args = parser.parse_args()

    try:
        # Load configuration
        logger.debug("Loading configuration from %s", args.config or "config.yaml")
        config = load_config(args.config)

        # Apply command-line overrides using model_copy to ensure validation
        overrides = {}
        if args.max_videos:
            overrides["max_videos"] = args.max_videos
            logger.debug("Max videos overridden to: %d", args.max_videos)
        if args.output:
            overrides["output_file"] = args.output
            logger.debug("Output file overridden to: %s", args.output)

        if overrides:
            config = config.model_copy(update=overrides)

        logger.info("Configuration loaded successfully")
        logger.debug(
            "Config: llm=%s/%s (api_key=%s), youtube_key=%s, max_videos=%d, output=%s",
            config.llm.provider,
            config.llm.model,
            mask_sensitive(config.llm.api_key),
            mask_sensitive(config.youtube_api_key),
            config.max_videos,
            config.output_file,
        )

        from .agent import ask_source, parse_video_count
        from .chat import ChatSession
        from .llm import get_context_limit
        from .transcript import get_transcripts_batch_with_fallback
        from .youtube import InputType, get_videos_batch, list_videos

        logger.info("Starting conversational agent")

        input_type, collection_id, title, video_ids = ask_source(config)

        # video_titles maps video_id -> title for index building
        video_titles: dict[str, str] = {}

        if input_type == InputType.CHANNEL:
            print("\nHow many videos should I analyze?")
            count_input = input("Videos [50]: ").strip()
            max_videos = parse_video_count(count_input, config.max_videos)

            channel_id = collection_id.removeprefix("channel_")
            videos = list_videos(channel_id, config.youtube_api_key, max_videos)
            video_ids = [v.id for v in videos]
            video_titles = {v.id: v.title for v in videos}
            print(f"Found {len(video_ids)} videos")
        else:
            # For videos/playlists, batch fetch titles (more efficient)
            video_infos = get_videos_batch(video_ids, config.youtube_api_key)
            for vid in video_ids:
                if vid in video_infos:
                    video_titles[vid] = video_infos[vid].title
                else:
                    video_titles[vid] = vid  # Fallback to ID if fetch fails

        print(f"\nFetching transcripts for {len(video_ids)} videos...")
        if config.transcription.fallback_enabled:
            print(
                f"(Whisper fallback enabled with '{config.transcription.whisper_model}' model)"
            )

        def show_progress(current: int, total: int, video_id: str, status: str) -> None:
            percentage = int((current / total) * 100) if total > 0 else 0
            status_str = f" [{status}]" if status != "success" else ""
            print(
                f"Progress: {current}/{total} ({percentage}%) - {video_id}{status_str}"
            )

        transcripts = get_transcripts_batch_with_fallback(
            video_ids,
            progress_callback=show_progress,
            fallback_enabled=config.transcription.fallback_enabled,
            whisper_model=config.transcription.whisper_model,
            cleanup_audio=config.transcription.cleanup_audio,
        )

        skipped = len(video_ids) - len(transcripts)
        print(
            f"\n✅ Fetched {len(transcripts)}/{len(video_ids)} transcripts"
            + (f" ({skipped} skipped)" if skipped > 0 else "")
        )

        if not transcripts:
            raise ValueError("No transcripts available for the selected content")

        context_limit = get_context_limit(config.llm)
        total_chars = sum(len(t) for t in transcripts.values())
        logger.info(
            "Transcripts: %d chars (~%d tokens), context_limit: %d tokens",
            total_chars,
            total_chars // 4,
            context_limit,
        )

        print("\n" + "=" * 60)
        print(f"Ready to chat about: {title}")
        print("=" * 60)
        print("Ask questions about the content.")
        print("Type 'quit' or 'exit' to end the session.")
        print("=" * 60)

        session = ChatSession(
            collection_id=collection_id,
            llm_config=config.llm,
            transcripts=transcripts,
            video_titles=video_titles,
            context_limit=context_limit,
            search_config=config.search,
            embeddings_config=config.embeddings,
        )

        while True:
            try:
                print()
                question = input("You: ").strip()
                if not question:
                    continue
                if question.lower() in ("quit", "exit", "q"):
                    print("\nGoodbye!")
                    break

                print()
                response = session.ask(question)
                print(f"Assistant: {response}")

            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break

        return 0

    except FileNotFoundError as e:
        logger.error("Configuration file not found: %s", e)
        logger.info("To get started:")
        logger.info("1. Copy config.example.yaml to config.yaml")
        logger.info("2. Set your API keys")
        return 1
    except ValueError as e:
        logger.error(str(e))
        return 1
    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user")
        return 130
    except Exception:
        logger.exception("Unexpected error occurred")
        return 1


if __name__ == "__main__":
    sys.exit(main())

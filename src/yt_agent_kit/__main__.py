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

        from .agent import ask_source
        from .chat import ChatSession
        from .embeddings import build_index, get_index_stats
        from .transcript import get_transcripts_batch
        from .youtube import InputType, get_videos_batch, list_videos

        logger.info("Starting conversational agent")

        input_type, collection_id, title, video_ids = ask_source(config)

        # video_titles maps video_id -> title for index building
        video_titles: dict[str, str] = {}

        if input_type == InputType.CHANNEL:
            print("\nHow many videos should I analyze?")
            count_input = input("Videos [50]: ").strip() or "50"
            try:
                max_videos = int(count_input)
                if max_videos < 1:
                    print("Must be at least 1, using 50")
                    max_videos = 50
                else:
                    max_videos = min(max_videos, config.max_videos)
            except ValueError:
                max_videos = 50

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

        def show_progress(current: int, total: int, video_id: str) -> None:
            percentage = int((current / total) * 100) if total > 0 else 0
            print(f"Progress: {current}/{total} ({percentage}%) - {video_id}")

        transcripts = get_transcripts_batch(video_ids, progress_callback=show_progress)

        skipped = len(video_ids) - len(transcripts)
        print(
            f"\n✅ Fetched {len(transcripts)}/{len(video_ids)} transcripts"
            + (f" ({skipped} skipped)" if skipped > 0 else "")
        )

        if not transcripts:
            raise ValueError("No transcripts available for the selected content")

        print("\nBuilding search index...")
        transcripts_for_index = {
            vid: (video_titles.get(vid, vid), text) for vid, text in transcripts.items()
        }
        added = build_index(collection_id, transcripts_for_index)
        stats = get_index_stats(collection_id)
        logger.info(
            "Index built: added=%d, total_chunks=%d, total_videos=%d",
            added,
            stats["total_chunks"],
            stats["total_videos"],
        )
        print(
            f"Indexed {stats['total_videos']} videos ({stats['total_chunks']} chunks)"
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
            search_config=config.search,
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

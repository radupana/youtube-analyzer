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

        from .agent import run_conversation

        logger.info("Starting conversational agent")
        state = run_conversation(config)

        if not state.channel:
            raise ValueError("No channel was selected")

        logger.info(
            "Conversation completed: channel=%s, intent=%s, format=%s",
            state.channel.title,
            state.intent,
            state.output_format,
        )

        print("\n" + "=" * 60)
        print("Phase 2 Complete: Conversational Agent Foundation")
        print("=" * 60)
        print(f"Channel: {state.channel.title} ({state.channel.id})")
        print(f"Intent: {state.intent}")
        print(f"Output Format: {state.output_format}")
        print(f"Videos to Process: {min(config.max_videos, state.channel.video_count)}")
        print("=" * 60)
        print("\nNext: Phase 3 will implement transcript extraction and LLM analysis.")

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

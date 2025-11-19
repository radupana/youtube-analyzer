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
    if not value:
        return "None"
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze YouTube channel transcripts with LLMs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # Use config.yaml
  %(prog)s --channel "Ben Johnson"     # Override channel
  %(prog)s --max-videos 10             # Limit videos processed
  %(prog)s --config custom.yaml        # Use different config file
        """,
    )

    parser.add_argument(
        "--config", type=Path, help="Path to config file (default: config.yaml)"
    )
    parser.add_argument(
        "--channel", help="YouTube channel name/handle/URL (overrides config)"
    )
    parser.add_argument(
        "--max-videos", type=int, help="Maximum videos to process (overrides config)"
    )
    parser.add_argument("--output", help="Output file path (overrides config)")
    parser.add_argument(
        "--extractor", help="Extractor template to use (overrides config)"
    )

    args = parser.parse_args()

    try:
        # Load configuration
        logger.debug("Loading configuration from %s", args.config or "config.yaml")
        config = load_config(args.config)

        # Apply command-line overrides
        if args.channel:
            config.channel = args.channel
            logger.debug("Channel overridden to: %s", args.channel)
        if args.max_videos:
            config.max_videos = args.max_videos
            logger.debug("Max videos overridden to: %d", args.max_videos)
        if args.output:
            config.output_file = args.output
            logger.debug("Output file overridden to: %s", args.output)
        if args.extractor:
            config.extractor = args.extractor
            logger.debug("Extractor overridden to: %s", args.extractor)

        logger.info("Configuration loaded successfully")
        logger.debug(
            "Config: channel=%s, llm=%s/%s (api_key=%s), youtube_key=%s, max_videos=%d, output=%s",
            config.channel,
            config.llm.provider,
            config.llm.model,
            mask_sensitive(config.llm.api_key),
            mask_sensitive(config.youtube_api_key),
            config.max_videos,
            config.output_file,
        )

        # Configuration is valid and ready to use
        # Implementation will be added when YouTube integration is ready
        raise NotImplementedError("YouTube channel analysis not yet implemented.")

    except FileNotFoundError as e:
        logger.error("Configuration file not found: %s", e)
        logger.info("To get started:")
        logger.info("1. Copy config.example.yaml to config.yaml")
        logger.info("2. Set your API keys")
        return 1
    except (ValueError, NotImplementedError) as e:
        logger.error(str(e))
        return 1
    except Exception:
        logger.exception("Unexpected error occurred")
        return 1


if __name__ == "__main__":
    sys.exit(main())

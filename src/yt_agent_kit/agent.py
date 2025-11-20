"""Conversational agent for YouTube channel analysis."""

from dataclasses import dataclass

from .config import Config
from .youtube import ChannelInfo, find_channel_id

# Input validation limits
MAX_INPUT_LENGTH = 1000
DESCRIPTION_PREVIEW_LENGTH = 150


@dataclass
class ConversationState:
    """State of the conversational agent."""

    channel: ChannelInfo | None = None
    intent: str | None = None
    output_format: str = "human"


def ask_channel(config: Config) -> ChannelInfo:
    """
    Ask user for YouTube channel with conversational flow.

    Returns:
        ChannelInfo with channel metadata

    Raises:
        ValueError: If channel not found or invalid
    """
    print("\nHi! What YouTube channel are we analyzing today?")
    print("(You can provide a channel name, @handle, URL, or channel ID)")
    print()

    query = input("Channel: ").strip()

    if not query:
        raise ValueError("Channel cannot be empty")
    if len(query) > MAX_INPUT_LENGTH:
        raise ValueError(f"Input too long (max {MAX_INPUT_LENGTH} characters)")

    print(f"\nSearching for '{query}'...")

    channel = find_channel_id(query, config.youtube_api_key)

    print("\nGreat! I found the channel:")
    print(f"  Title: {channel.title}")
    print(f"  Subscribers: {channel.subscriber_count:,}")
    print(f"  Total Videos: {channel.video_count:,}")
    if channel.custom_url:
        print(f"  Handle: {channel.custom_url}")
    if channel.description:
        description_preview = (
            channel.description[:DESCRIPTION_PREVIEW_LENGTH] + "..."
            if len(channel.description) > DESCRIPTION_PREVIEW_LENGTH
            else channel.description
        )
        print(f"  Description: {description_preview}")

    return channel


def ask_intent() -> str:
    """
    Ask user what they want to analyze.

    Returns:
        User's intent description
    """
    print("\nWhat are you looking to get out of the analysis?")
    print("(Examples: 'summarize key advice', '4-week strength training block', etc.)")
    print()

    intent = input("Intent: ").strip()

    if not intent:
        raise ValueError("Intent cannot be empty")
    if len(intent) > MAX_INPUT_LENGTH:
        raise ValueError(f"Input too long (max {MAX_INPUT_LENGTH} characters)")

    return intent


def ask_output_format() -> str:
    """
    Ask user for desired output format.

    Returns:
        Output format preference ('human', 'json', or 'markdown')
    """
    print("\nHow would you like the results?")
    print("  1. Human-readable (default)")
    print("  2. JSON")
    print("  3. Markdown")
    print()

    choice = input("Choice [1]: ").strip() or "1"

    format_map = {"1": "human", "2": "json", "3": "markdown"}

    return format_map.get(choice, "human")


def run_conversation(config: Config) -> ConversationState:
    """
    Run the complete conversational flow.

    Args:
        config: Application configuration

    Returns:
        ConversationState with collected information

    Raises:
        ValueError: If user input is invalid
    """
    state = ConversationState()

    state.channel = ask_channel(config)
    state.intent = ask_intent()
    state.output_format = ask_output_format()

    print("\nPerfect! I have all the information I need.")
    print(f"  Channel: {state.channel.title}")
    print(f"  Intent: {state.intent}")
    print(f"  Output: {state.output_format}")

    return state

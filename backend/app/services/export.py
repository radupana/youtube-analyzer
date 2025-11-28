"""Transcript export formatters."""

from app.db.models import Chunk, Video


def format_timestamp_srt(seconds: float) -> str:
    """Convert seconds to SRT timestamp format: HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def export_txt(video: Video) -> str:
    """Export as plain text with metadata header."""
    lines = [
        f"Title: {video.title}",
        f"Channel: {video.channel_title}",
        f"URL: https://youtube.com/watch?v={video.id}",
        f"Published: {video.published_at.strftime('%Y-%m-%d')}",
        "",
        "---",
        "",
        video.transcript or "(No transcript available)",
    ]
    return "\n".join(lines)


def export_markdown(video: Video) -> str:
    """Export as Markdown with metadata header."""
    lines = [
        f"# {video.title}",
        "",
        f"**Channel:** {video.channel_title}  ",
        f"**URL:** https://youtube.com/watch?v={video.id}  ",
        f"**Published:** {video.published_at.strftime('%Y-%m-%d')}  ",
        f"**Duration:** {video.duration}",
        "",
        "---",
        "",
        "## Transcript",
        "",
        video.transcript or "*No transcript available*",
    ]
    return "\n".join(lines)


def export_srt(chunks: list[Chunk]) -> str:
    """Export as SRT subtitle format (requires chunks with timestamps)."""
    if not chunks:
        return ""

    lines: list[str] = []
    for i, chunk in enumerate(chunks, 1):
        start = format_timestamp_srt(chunk.start_time)
        end = format_timestamp_srt(chunk.end_time)
        lines.extend(
            [
                str(i),
                f"{start} --> {end}",
                chunk.text.strip(),
                "",
            ]
        )
    return "\n".join(lines)


def export_json(video: Video, chunks: list[Chunk] | None = None) -> dict:
    """Export as structured JSON."""
    result: dict = {
        "video_id": video.id,
        "title": video.title,
        "channel": video.channel_title,
        "url": f"https://youtube.com/watch?v={video.id}",
        "published_at": video.published_at.isoformat(),
        "duration": video.duration,
        "transcript_source": video.transcript_source,
        "full_text": video.transcript,
    }

    if chunks:
        result["segments"] = [
            {
                "start": chunk.start_time,
                "end": chunk.end_time,
                "text": chunk.text,
            }
            for chunk in chunks
        ]

    return result

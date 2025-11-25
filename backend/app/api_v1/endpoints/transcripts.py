from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/{video_id}")
async def get_transcript(video_id: str):
    mock_transcripts = {
        "dQw4w9WgXcQ": {
            "video_id": "dQw4w9WgXcQ",
            "transcript": "Never gonna give you up, never gonna let you down...",
            "duration": 213,
        },
        "9bZkp7q19f0": {
            "video_id": "9bZkp7q19f0",
            "transcript": "Oppa Gangnam Style...",
            "duration": 253,
        },
    }

    if video_id in mock_transcripts:
        return mock_transcripts[video_id]

    raise HTTPException(status_code=404, detail="Transcript not found")

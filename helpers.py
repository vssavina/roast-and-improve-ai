from pathlib import Path
from typing import List, Dict, Any
import json


def ensure_data_dir_exists() -> Path:
    """
    Ensure that a 'data' directory exists, create one if it doesn't and return its path

    Returns:
        Path: The absolute path to the 'data' directory
    """
    root = Path(__file__).resolve().parent
    data_dir = root / "data"
    data_dir.mkdir(exist_ok=True)
    return data_dir


def save_videos_to_json(videos: List[Dict[str, Any]], path: Path) -> None:
    """
    Save a list of video metadata dictionaries to a JSON file.

    Args:
        videos: A list of dictionaries containing video information
        path: Filesystem path where the JSON file should be written

    The JSON is written with UTF-8 encoding, non-ASCII characters preserved,
    and pretty-printed with an indentation of 2 spaces
    """
    with path.open("w", encoding="utf-8") as file:
        json.dump(videos, file, ensure_ascii=False, indent=2)

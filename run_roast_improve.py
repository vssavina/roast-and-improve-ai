import os
from pathlib import Path
from typing import List, Dict, Any, Optional

import requests
from dotenv import load_dotenv

from helpers import ensure_data_dir_exists, save_videos_to_json


YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
load_dotenv()


class YouTubeAPIError(Exception):
    """
    Custom exception raised when a YouTube Data API request fails or is misconfigured 
    """
    pass


def youtube_get_data_by_url(endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Perform a GET request to the YouTube Data API and return the parsed JSON response

    Args:
        endpoint: The YouTube API endpoint to call (e.g. 'channels', 'videos', 'search')
        params: A dictionary of query parameters to include in the request

    Returns:
        Dict[str, Any]: The parsed JSON response from the YouTube API

    Raises:
        YouTubeAPIError: If the YOUTUBE_API_KEY environment variable is not set or if the HTTP request fails
    """

    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise YouTubeAPIError(
            "YOUTUBE_API_KEY is not set. Export it in your shell or environment."
        )

    params = dict(params)
    params["key"] = api_key

    url = f"{YOUTUBE_API_BASE}/{endpoint}"
    print("URL to scrap from: ", url)
    resp = requests.get(url, params=params, timeout=15)
    if not resp.ok:
        raise YouTubeAPIError(
            f"Request to {endpoint} failed with status {resp.status_code}: {resp.text}"
        )
    save_videos_to_json(resp.json(), Path(f"./data/youtube_get_{endpoint}.json"))
    return resp.json()


def get_uploads_by_playlist_id(channel_id: str) -> str:
    """
    Get the uploads playlist ID for a given YouTube channel

    Args:
        channel_id: The YouTube channel ID (the 'UC...' style ID, not @username!)

    Returns:
        The ID of the channel's uploads playlist

    Raises:
        YouTubeAPIError: If no channel is found for the given ID
    """
    data = youtube_get_data_by_url(
        "channels",
        {
            "part": "contentDetails",
            "id": channel_id,
        },
    )

    items = data.get("items", [])
    if not items:
        raise YouTubeAPIError(
            f"No channel found for id={channel_id}. "
            "Make sure you used the 'UC...' channel ID, not @username."
        )

    uploads_playlist_id = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    return uploads_playlist_id


def get_all_video_ids_from_playlist(
    playlist_id: str, max_videos_num: Optional[int] = None
) -> List[str]:
    """
    Get all video IDs from a given YouTube playlist

    Args:
        playlist_id: The ID of the YouTube playlist to read from
        max_videos: Optional limit on how many video IDs to collect. If None,
            all available video IDs in the playlist are returned

    Returns:
        A list of 'max_videos_num' video IDs contained in the playlist
    """
    video_ids: List[str] = []
    page_token: Optional[str] = None

    while True:
        params: Dict[str, Any] = {
            "part": "contentDetails",
            "playlistId": playlist_id,
            "maxResults": 50,
        }
        if page_token:
            params["pageToken"] = page_token

        data = youtube_get_data_by_url("playlistItems", params)

        for item in data.get("items", []):
            vid = item["contentDetails"]["videoId"]
            video_ids.append(vid)
            if max_videos_num is not None and len(video_ids) >= max_videos_num:
                return video_ids

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return video_ids


def chunked(lst: List[Any], size: int) -> List[List[Any]]:
    """
    Split a list into chunks of a given size

    Args:
        lst: The list to be split into chunks
        size: The maximum number of elements per chunk

    Returns:
        A list of sublists, where each sublist contains 'size' elements
    """
    return [lst[i : i + size] for i in range(0, len(lst), size)]


def get_video_details(video_ids: List[str]) -> List[Dict[str, Any]]:
    """
    Fetch detailed metadata for a list of YouTube video IDs

    Args:
        video_ids: A list of YouTube video IDs to get details for

    Returns:
        A list of dictionaries, each containing details for a single video
    """
    all_videos: List[Dict[str, Any]] = []

    for chunk in chunked(video_ids, 50):
        params = {
            "part": "snippet,contentDetails,statistics",
            "id": ",".join(chunk),
            "maxResults": 50,
        }
        data = youtube_get_data_by_url("videos", params)

        for item in data.get("items", []):
            vid = {
                "id": item["id"],
                "title": item["snippet"].get("title"),
                "description": item["snippet"].get("description"),
                "publishedAt": item["snippet"].get("publishedAt"),
                "channelId": item["snippet"].get("channelId"),
                "channelTitle": item["snippet"].get("channelTitle"),
                "tags": item["snippet"].get("tags", []),
                "categoryId": item["snippet"].get("categoryId"),
                "thumbnails": item["snippet"].get("thumbnails", {}),
                "duration": item["contentDetails"].get("duration"),
                "definition": item["contentDetails"].get("definition"),
                "caption": item["contentDetails"].get("caption"),
                "viewCount": int(item["statistics"].get("viewCount", 0)),
                "likeCount": int(item["statistics"].get("likeCount", 0)),
                "commentCount": int(item["statistics"].get("commentCount", 0)),
            }
            all_videos.append(vid)

    return all_videos


def main() -> None:

    data_dir = ensure_data_dir_exists()
    channel_id = os.getenv("YT_CHANNEL_ID")

    if not channel_id:
        raise SystemExit("You must set YT_CHANNEL_ID env var.")
    print(f"🎬 Using channel ID: {channel_id}")

    try:
        uploads_playlist_id = get_uploads_by_playlist_id(channel_id)
        print(f"📁 Uploads playlist ID: {uploads_playlist_id}")

        video_ids = get_all_video_ids_from_playlist(
            uploads_playlist_id,
        )

        print(f"✅ Found {len(video_ids)} video IDs.")
        print(f"✅ Found videos: {video_ids}.")

        if not video_ids:
            raise SystemExit("No videos found for this channel.")

        print("📥 Fetching details & statistics...")
        videos = get_video_details(video_ids)
        print(f"✅ Retrieved details for {len(videos)} videos.")

        save_videos_to_json(videos, data_dir / "videos_raw.json")
        print(f"💾 Saved videos data to {(data_dir / 'videos_raw.json').resolve()}")

        print("This JSON file will be the input for v1 (LLM analysis).")

    except YouTubeAPIError as e:
        print(f"❌ YouTube API error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    main()

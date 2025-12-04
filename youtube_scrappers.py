import os
from pathlib import Path
from typing import List, Dict, Any, Optional

import requests

from helpers import save_videos_to_json

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


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
        YouTubeAPIError: If the YOUTUBE_API_KEY environment variable
        is not set or if the HTTP request fails
    """

    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise YouTubeAPIError(
            "YOUTUBE_API_KEY is not set. Export it in your shell or environment."
        )

    params = dict(params)
    params["key"] = api_key

    url = f"{YOUTUBE_API_BASE}/{endpoint}"
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

    all_videos: List[Dict[str, Any]] = []

    for chunk in chunked(video_ids, 50):
        params = {
            "part": "snippet,contentDetails,statistics",
            "id": ",".join(chunk),
            "maxResults": 50,
        }
        data = youtube_get_data_by_url("videos", params)

        for item in data.get("items", []):
            print(f'📥 Fetching detail for video {item["snippet"].get("title")}')

            video = {
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
            try:
                comments = get_comments_by_video_id(item["id"])
            except YouTubeAPIError:
                comments = []

            video["comments"] = comments
            all_videos.append(video)

    return all_videos


def get_comments_by_video_id(
    video_id: str, max_topLevelComments: int = 20, max_replies: int = 2
) -> List[Dict[str, Any]]:
    """
    Get max_topLevelComments top-level comments and a limited number
    of replies for a given YouTube video

    Args:
        video_id: The YouTube video ID for which to get comments
        max_topLevelComments: Maximum number of top-level comments
            (comment threads) to retrieve
        max_replies: Maximum number of replies to include for each
            top-level comment

    Returns:
        A list of dictionaries, each representing a comment thread with:
        - "topLevelComment": metadata about the top-level comment
        - "replies": a list of reply dictionaries (may be empty)
    """

    comments: List[Dict[str, Any]] = []

    params = {
        "part": "snippet,replies",
        "video_id": video_id,
        "maxResults": max_topLevelComments,
        "textFormat": "plainText",
    }

    data = youtube_get_data_by_url("commentThreads", params)

    for item in data.get("items", []):
        print(f"📥 Fetching comments for video {video_id}")
        topLevelCommentSnippet = item["snippet"]["topLevelComment"]["snippet"]
        text = (
            topLevelCommentSnippet.get("textDisplay")
            or topLevelCommentSnippet.get("textOriginal")
            or ""
        )
        topLevelComment = {
            "text": text,
            "likeCount": topLevelCommentSnippet.get("likeCount"),
            "publishedAt": topLevelCommentSnippet.get("publishedAt"),
        }

        relies_data = item.get("replies", {}).get("comments", [])
        replies_list: List[Dict[str, Any]] = []
        for reply_ in relies_data[:max_replies]:
            replySnippet = reply_["snippet"]
            text = (
                replySnippet.get("textDisplay")
                or replySnippet.get("textOriginal")
                or ""
            )
            reply = {
                "text": text,
                "likeCount": replySnippet.get("likeCount"),
                "publishedAt": replySnippet.get("publishedAt"),
            }
            replies_list.append(reply)

        comments.append({"topLevelComment": topLevelComment, "replies": replies_list})
    return comments

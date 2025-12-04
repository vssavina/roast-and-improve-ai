import os

from dotenv import load_dotenv

from helpers import ensure_data_dir_exists, save_videos_to_json
from youtube_scrappers import (
    get_uploads_by_playlist_id,
    get_all_video_ids_from_playlist,
    get_video_details,
    YouTubeAPIError,
)

load_dotenv()


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

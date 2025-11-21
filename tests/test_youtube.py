from unittest.mock import Mock, patch

import pytest

from yt_agent_kit.youtube import (
    InputType,
    detect_input_type,
    find_channel_id,
    get_playlist_info,
    get_playlist_video_ids,
    get_video_info,
    list_videos,
)


class TestFindChannelId:
    def test_find_by_channel_id_direct(self):
        mock_youtube = Mock()
        mock_channels = Mock()
        mock_youtube.channels.return_value = mock_channels
        mock_request = Mock()
        mock_channels.list.return_value = mock_request
        mock_request.execute.return_value = {
            "items": [
                {
                    "id": "UC1234567890123456789012",
                    "snippet": {
                        "title": "Test Channel",
                        "description": "Test Description",
                        "customUrl": "@testchannel",
                    },
                    "statistics": {
                        "subscriberCount": "1000000",
                        "videoCount": "500",
                    },
                }
            ]
        }

        with patch("yt_agent_kit.youtube.build", return_value=mock_youtube):
            result = find_channel_id("UC1234567890123456789012", "test-api-key")

        assert result.id == "UC1234567890123456789012"
        assert result.title == "Test Channel"
        assert result.description == "Test Description"
        assert result.subscriber_count == 1000000
        assert result.video_count == 500
        assert result.custom_url == "@testchannel"

    def test_find_by_channel_url(self):
        mock_youtube = Mock()
        mock_channels = Mock()
        mock_youtube.channels.return_value = mock_channels
        mock_request = Mock()
        mock_channels.list.return_value = mock_request
        mock_request.execute.return_value = {
            "items": [
                {
                    "id": "UCabcdefghijklmnopqrstuv",
                    "snippet": {
                        "title": "URL Channel",
                        "description": "Found by URL",
                        "customUrl": "@urlchannel",
                    },
                    "statistics": {
                        "subscriberCount": "500000",
                        "videoCount": "250",
                    },
                }
            ]
        }

        with patch("yt_agent_kit.youtube.build", return_value=mock_youtube):
            result = find_channel_id(
                "https://youtube.com/channel/UCabcdefghijklmnopqrstuv", "test-api-key"
            )

        assert result.id == "UCabcdefghijklmnopqrstuv"
        assert result.title == "URL Channel"

    def test_find_by_name(self):
        mock_youtube = Mock()
        mock_search = Mock()
        mock_channels = Mock()
        mock_youtube.search.return_value = mock_search
        mock_youtube.channels.return_value = mock_channels

        mock_search_request = Mock()
        mock_search.list.return_value = mock_search_request
        mock_search_request.execute.return_value = {
            "items": [{"id": {"channelId": "UCsearchresult123456789"}}]
        }

        mock_channel_request = Mock()
        mock_channels.list.return_value = mock_channel_request
        mock_channel_request.execute.return_value = {
            "items": [
                {
                    "id": "UCsearchresult123456789",
                    "snippet": {
                        "title": "Search Result Channel",
                        "description": "Found by search",
                    },
                    "statistics": {
                        "subscriberCount": "250000",
                        "videoCount": "100",
                    },
                }
            ]
        }

        with patch("yt_agent_kit.youtube.build", return_value=mock_youtube):
            result = find_channel_id("Test Channel Name", "test-api-key")

        assert result.id == "UCsearchresult123456789"
        assert result.title == "Search Result Channel"
        assert result.subscriber_count == 250000

    def test_find_by_handle(self):
        mock_youtube = Mock()
        mock_search = Mock()
        mock_channels = Mock()
        mock_youtube.search.return_value = mock_search
        mock_youtube.channels.return_value = mock_channels

        mock_search_request = Mock()
        mock_search.list.return_value = mock_search_request
        mock_search_request.execute.return_value = {
            "items": [{"id": {"channelId": "UChandleresult123456789"}}]
        }

        mock_channel_request = Mock()
        mock_channels.list.return_value = mock_channel_request
        mock_channel_request.execute.return_value = {
            "items": [
                {
                    "id": "UChandleresult123456789",
                    "snippet": {
                        "title": "Handle Channel",
                        "description": "Found by handle",
                        "customUrl": "@testhandle",
                    },
                    "statistics": {
                        "subscriberCount": "750000",
                        "videoCount": "300",
                    },
                }
            ]
        }

        with patch("yt_agent_kit.youtube.build", return_value=mock_youtube):
            result = find_channel_id("@testhandle", "test-api-key")

        assert result.id == "UChandleresult123456789"
        assert result.title == "Handle Channel"
        assert result.custom_url == "@testhandle"

    def test_channel_not_found(self):
        mock_youtube = Mock()
        mock_search = Mock()
        mock_youtube.search.return_value = mock_search

        mock_search_request = Mock()
        mock_search.list.return_value = mock_search_request
        mock_search_request.execute.return_value = {"items": []}

        with patch("yt_agent_kit.youtube.build", return_value=mock_youtube):
            with pytest.raises(ValueError, match="Channel not found"):
                find_channel_id("NonexistentChannel", "test-api-key")

    def test_caching(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        mock_youtube = Mock()
        mock_channels = Mock()
        mock_youtube.channels.return_value = mock_channels
        mock_request = Mock()
        mock_channels.list.return_value = mock_request
        mock_request.execute.return_value = {
            "items": [
                {
                    "id": "UCcache12345678901234567",
                    "snippet": {
                        "title": "Cache Test",
                        "description": "Testing cache",
                    },
                    "statistics": {
                        "subscriberCount": "100000",
                        "videoCount": "50",
                    },
                }
            ]
        }

        with patch("yt_agent_kit.youtube.build", return_value=mock_youtube):
            result1 = find_channel_id("UCcache12345678901234567", "test-api-key")
            result2 = find_channel_id("UCcache12345678901234567", "test-api-key")

        assert result1.id == result2.id
        assert result1.title == result2.title
        mock_request.execute.assert_called_once()

    def test_channel_with_missing_statistics(self):
        """Test channel with missing subscriber count (private stats)."""
        mock_youtube = Mock()
        mock_channels = Mock()
        mock_youtube.channels.return_value = mock_channels
        mock_request = Mock()
        mock_channels.list.return_value = mock_request
        mock_request.execute.return_value = {
            "items": [
                {
                    "id": "UCprivate123456789012345",
                    "snippet": {
                        "title": "Private Stats Channel",
                        "description": "Stats hidden",
                    },
                    "statistics": {},  # No subscriber/video counts
                }
            ]
        }

        with patch("yt_agent_kit.youtube.build", return_value=mock_youtube):
            result = find_channel_id("UCprivate123456789012345", "test-api-key")

        assert result.id == "UCprivate123456789012345"
        assert result.subscriber_count == 0
        assert result.video_count == 0


class TestListVideos:
    def test_list_videos_basic(self):
        mock_youtube = Mock()
        mock_search = Mock()
        mock_videos = Mock()
        mock_youtube.search.return_value = mock_search
        mock_youtube.videos.return_value = mock_videos

        mock_search_request = Mock()
        mock_search.list.return_value = mock_search_request
        mock_search.list_next.return_value = None
        mock_search_request.execute.return_value = {
            "items": [
                {"id": {"videoId": "vid123"}},
                {"id": {"videoId": "vid456"}},
            ]
        }

        mock_video_request = Mock()
        mock_videos.list.return_value = mock_video_request
        mock_video_request.execute.return_value = {
            "items": [
                {
                    "id": "vid123",
                    "snippet": {
                        "title": "Video 1",
                        "description": "First video",
                        "publishedAt": "2024-01-01T00:00:00Z",
                    },
                    "contentDetails": {"duration": "PT10M30S"},
                },
                {
                    "id": "vid456",
                    "snippet": {
                        "title": "Video 2",
                        "description": "Second video",
                        "publishedAt": "2024-01-02T00:00:00Z",
                    },
                    "contentDetails": {"duration": "PT15M45S"},
                },
            ]
        }

        with patch("yt_agent_kit.youtube.build", return_value=mock_youtube):
            result = list_videos(
                "UCtest123456789012345678", "test-api-key", max_results=2
            )

        assert len(result) == 2
        assert result[0].id == "vid123"
        assert result[0].title == "Video 1"
        assert result[0].duration == "PT10M30S"
        assert result[1].id == "vid456"
        assert result[1].title == "Video 2"

    def test_pagination(self):
        mock_youtube = Mock()
        mock_search = Mock()
        mock_videos = Mock()
        mock_youtube.search.return_value = mock_search
        mock_youtube.videos.return_value = mock_videos

        mock_search_request1 = Mock()
        mock_search_request2 = Mock()
        mock_search.list.return_value = mock_search_request1

        mock_search_request1.execute.return_value = {
            "items": [{"id": {"videoId": f"vid{i}"}} for i in range(50)]
        }

        mock_search_request2.execute.return_value = {
            "items": [{"id": {"videoId": f"vid{i}"}} for i in range(50, 75)]
        }

        mock_search.list_next.side_effect = [mock_search_request2, None]

        # Mock videos.list to return items matching the requested batch
        def mock_video_list(**kwargs):
            video_ids = kwargs.get("id", "").split(",")
            mock_request = Mock()
            mock_request.execute.return_value = {
                "items": [
                    {
                        "id": vid_id,
                        "snippet": {
                            "title": f"Video {vid_id}",
                            "description": f"Description {vid_id}",
                            "publishedAt": "2024-01-01T00:00:00Z",
                        },
                        "contentDetails": {"duration": "PT10M"},
                    }
                    for vid_id in video_ids
                ]
            }
            return mock_request

        mock_videos.list.side_effect = mock_video_list

        with patch("yt_agent_kit.youtube.build", return_value=mock_youtube):
            result = list_videos(
                "UCtest123456789012345678", "test-api-key", max_results=75
            )

        assert len(result) == 75

    def test_caching(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        mock_youtube = Mock()
        mock_search = Mock()
        mock_videos = Mock()
        mock_youtube.search.return_value = mock_search
        mock_youtube.videos.return_value = mock_videos

        mock_search_request = Mock()
        mock_search.list.return_value = mock_search_request
        mock_search.list_next.return_value = None
        mock_search_request.execute.return_value = {
            "items": [{"id": {"videoId": "cachevid1"}}]
        }

        mock_video_request = Mock()
        mock_videos.list.return_value = mock_video_request
        mock_video_request.execute.return_value = {
            "items": [
                {
                    "id": "cachevid1",
                    "snippet": {
                        "title": "Cache Video",
                        "description": "Cached",
                        "publishedAt": "2024-01-01T00:00:00Z",
                    },
                    "contentDetails": {"duration": "PT5M"},
                }
            ]
        }

        with patch("yt_agent_kit.youtube.build", return_value=mock_youtube):
            result1 = list_videos(
                "UCcache123456789012345678", "test-api-key", max_results=1
            )
            result2 = list_videos(
                "UCcache123456789012345678", "test-api-key", max_results=1
            )

        assert len(result1) == 1
        assert len(result2) == 1
        assert result1[0].id == result2[0].id
        mock_search_request.execute.assert_called_once()

    def test_channel_with_zero_videos(self):
        mock_youtube = Mock()
        mock_search = Mock()
        mock_youtube.search.return_value = mock_search

        mock_search_request = Mock()
        mock_search.list.return_value = mock_search_request
        mock_search.list_next.return_value = None
        mock_search_request.execute.return_value = {"items": []}

        with patch("yt_agent_kit.youtube.build", return_value=mock_youtube):
            result = list_videos("UCempty12345678901234567", "test-api-key")

        assert len(result) == 0


class TestDetectInputType:
    def test_video_url_watch(self):
        input_type, vid = detect_input_type("https://youtube.com/watch?v=dQw4w9WgXcQ")
        assert input_type == InputType.VIDEO
        assert vid == "dQw4w9WgXcQ"

    def test_video_url_short(self):
        input_type, vid = detect_input_type("https://youtu.be/dQw4w9WgXcQ")
        assert input_type == InputType.VIDEO
        assert vid == "dQw4w9WgXcQ"

    def test_video_url_embed(self):
        input_type, vid = detect_input_type("https://youtube.com/embed/dQw4w9WgXcQ")
        assert input_type == InputType.VIDEO
        assert vid == "dQw4w9WgXcQ"

    def test_video_id_direct(self):
        input_type, vid = detect_input_type("dQw4w9WgXcQ")
        assert input_type == InputType.VIDEO
        assert vid == "dQw4w9WgXcQ"

    def test_playlist_url(self):
        input_type, pid = detect_input_type(
            "https://youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
        )
        assert input_type == InputType.PLAYLIST
        assert pid == "PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"

    def test_playlist_id_direct(self):
        input_type, pid = detect_input_type("PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf")
        assert input_type == InputType.PLAYLIST
        assert pid == "PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"

    def test_playlist_id_uploads(self):
        """UU prefix is channel uploads playlist."""
        input_type, pid = detect_input_type("UUabcdefghijklmnopqrstuv")
        assert input_type == InputType.PLAYLIST
        assert pid == "UUabcdefghijklmnopqrstuv"

    def test_playlist_id_liked(self):
        """LL prefix is liked videos playlist."""
        input_type, pid = detect_input_type("LLabcdefghijklmnopqrstuv")
        assert input_type == InputType.PLAYLIST
        assert pid == "LLabcdefghijklmnopqrstuv"

    def test_playlist_id_watch_later(self):
        """WL prefix is watch later playlist."""
        input_type, pid = detect_input_type("WLabcdefghijklmnopqrstuv")
        assert input_type == InputType.PLAYLIST
        assert pid == "WLabcdefghijklmnopqrstuv"

    def test_playlist_id_favorites(self):
        """FL prefix is favorites playlist."""
        input_type, pid = detect_input_type("FLabcdefghijklmnopqrstuv")
        assert input_type == InputType.PLAYLIST
        assert pid == "FLabcdefghijklmnopqrstuv"

    def test_playlist_id_radio(self):
        """RD prefix is radio/mix playlist."""
        input_type, pid = detect_input_type("RDabcdefghijklmnopqrstuv")
        assert input_type == InputType.PLAYLIST
        assert pid == "RDabcdefghijklmnopqrstuv"

    def test_channel_url(self):
        input_type, cid = detect_input_type(
            "https://youtube.com/channel/UCabcdefghijklmnopqrstuv"
        )
        assert input_type == InputType.CHANNEL
        assert cid == "UCabcdefghijklmnopqrstuv"

    def test_channel_id_direct(self):
        input_type, cid = detect_input_type("UCabcdefghijklmnopqrstuv")
        assert input_type == InputType.CHANNEL
        assert cid == "UCabcdefghijklmnopqrstuv"

    def test_handle_url(self):
        input_type, handle = detect_input_type("https://youtube.com/@JeffNippard")
        assert input_type == InputType.CHANNEL
        assert handle == "@JeffNippard"

    def test_handle_direct(self):
        input_type, handle = detect_input_type("@JeffNippard")
        assert input_type == InputType.CHANNEL
        assert handle == "@JeffNippard"

    def test_channel_name_fallback(self):
        input_type, name = detect_input_type("Jeff Nippard")
        assert input_type == InputType.CHANNEL
        assert name == "Jeff Nippard"

    def test_strips_whitespace(self):
        input_type, vid = detect_input_type("  dQw4w9WgXcQ  ")
        assert input_type == InputType.VIDEO
        assert vid == "dQw4w9WgXcQ"


class TestGetPlaylistVideoIds:
    def test_fetches_video_ids(self):
        mock_youtube = Mock()
        mock_playlist_items = Mock()
        mock_youtube.playlistItems.return_value = mock_playlist_items

        mock_request = Mock()
        mock_playlist_items.list.return_value = mock_request
        mock_playlist_items.list_next.return_value = None
        mock_request.execute.return_value = {
            "items": [
                {"contentDetails": {"videoId": "vid1"}},
                {"contentDetails": {"videoId": "vid2"}},
                {"contentDetails": {"videoId": "vid3"}},
            ]
        }

        with patch("yt_agent_kit.youtube.build", return_value=mock_youtube):
            result = get_playlist_video_ids("PLtest123", "test-api-key")

        assert result == ["vid1", "vid2", "vid3"]

    def test_respects_max_results(self):
        mock_youtube = Mock()
        mock_playlist_items = Mock()
        mock_youtube.playlistItems.return_value = mock_playlist_items

        mock_request = Mock()
        mock_playlist_items.list.return_value = mock_request
        mock_playlist_items.list_next.return_value = None
        mock_request.execute.return_value = {
            "items": [{"contentDetails": {"videoId": f"vid{i}"}} for i in range(10)]
        }

        with patch("yt_agent_kit.youtube.build", return_value=mock_youtube):
            result = get_playlist_video_ids("PLtest123", "test-api-key", max_results=5)

        assert len(result) == 5

    def test_caching(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        mock_youtube = Mock()
        mock_playlist_items = Mock()
        mock_youtube.playlistItems.return_value = mock_playlist_items

        mock_request = Mock()
        mock_playlist_items.list.return_value = mock_request
        mock_playlist_items.list_next.return_value = None
        mock_request.execute.return_value = {
            "items": [{"contentDetails": {"videoId": "vid1"}}]
        }

        with patch("yt_agent_kit.youtube.build", return_value=mock_youtube):
            result1 = get_playlist_video_ids(
                "PLcache123", "test-api-key", max_results=10
            )
            result2 = get_playlist_video_ids(
                "PLcache123", "test-api-key", max_results=10
            )

        assert result1 == result2
        mock_request.execute.assert_called_once()


class TestGetPlaylistInfo:
    def test_fetches_playlist_info(self):
        mock_youtube = Mock()
        mock_playlists = Mock()
        mock_youtube.playlists.return_value = mock_playlists

        mock_request = Mock()
        mock_playlists.list.return_value = mock_request
        mock_request.execute.return_value = {
            "items": [
                {
                    "id": "PLtest123",
                    "snippet": {
                        "title": "Test Playlist",
                        "description": "A test playlist",
                        "channelTitle": "Test Channel",
                    },
                }
            ]
        }

        with patch("yt_agent_kit.youtube.build", return_value=mock_youtube):
            result = get_playlist_info("PLtest123", "test-api-key")

        assert result["id"] == "PLtest123"
        assert result["title"] == "Test Playlist"
        assert result["description"] == "A test playlist"
        assert result["channel_title"] == "Test Channel"

    def test_playlist_not_found(self):
        mock_youtube = Mock()
        mock_playlists = Mock()
        mock_youtube.playlists.return_value = mock_playlists

        mock_request = Mock()
        mock_playlists.list.return_value = mock_request
        mock_request.execute.return_value = {"items": []}

        with patch("yt_agent_kit.youtube.build", return_value=mock_youtube):
            with pytest.raises(ValueError, match="Playlist not found"):
                get_playlist_info("PLnonexistent", "test-api-key")


class TestGetVideoInfo:
    def test_fetches_video_info(self):
        mock_youtube = Mock()
        mock_videos = Mock()
        mock_youtube.videos.return_value = mock_videos

        mock_request = Mock()
        mock_videos.list.return_value = mock_request
        mock_request.execute.return_value = {
            "items": [
                {
                    "id": "vid123",
                    "snippet": {
                        "title": "Test Video",
                        "description": "A test video",
                        "publishedAt": "2024-01-01T00:00:00Z",
                    },
                    "contentDetails": {"duration": "PT10M30S"},
                }
            ]
        }

        with patch("yt_agent_kit.youtube.build", return_value=mock_youtube):
            result = get_video_info("vid123", "test-api-key")

        assert result.id == "vid123"
        assert result.title == "Test Video"
        assert result.description == "A test video"
        assert result.duration == "PT10M30S"

    def test_video_not_found(self):
        mock_youtube = Mock()
        mock_videos = Mock()
        mock_youtube.videos.return_value = mock_videos

        mock_request = Mock()
        mock_videos.list.return_value = mock_request
        mock_request.execute.return_value = {"items": []}

        with patch("yt_agent_kit.youtube.build", return_value=mock_youtube):
            with pytest.raises(ValueError, match="Video not found"):
                get_video_info("nonexistent", "test-api-key")

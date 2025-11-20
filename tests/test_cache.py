import json
from datetime import datetime, timedelta

from yt_agent_kit.cache import cache_path, get_from_cache, save_to_cache


class TestCachePath:
    def test_creates_cache_directory(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        path = cache_path("test_key")
        assert path.parent.exists()
        assert path.parent.name == ".cache"

    def test_sanitizes_key(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        path = cache_path("key/with:special")
        assert "/" not in path.name
        assert ":" not in path.name
        assert path.name == "key_with_special.json"


class TestSaveToCache:
    def test_saves_dict_with_timestamp(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        data = {"foo": "bar", "num": 42}
        save_to_cache("test_key", data)

        cache_file = cache_path("test_key")
        assert cache_file.exists()

        with open(cache_file, encoding="utf-8") as f:
            cached = json.load(f)

        assert "timestamp" in cached
        assert "data" in cached
        assert cached["data"] == data
        datetime.fromisoformat(cached["timestamp"])

    def test_saves_list(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        data = [1, 2, 3, "test"]
        save_to_cache("list_key", data)

        cached = get_from_cache("list_key")
        assert cached == data

    def test_overwrites_existing_cache(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        save_to_cache("key", {"version": 1})
        save_to_cache("key", {"version": 2})

        cached = get_from_cache("key")
        assert cached == {"version": 2}


class TestGetFromCache:
    def test_returns_none_for_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = get_from_cache("nonexistent")
        assert result is None

    def test_returns_data_within_max_age(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        data = {"test": "data"}
        save_to_cache("fresh_key", data)

        result = get_from_cache("fresh_key", max_age_hours=24)
        assert result == data

    def test_returns_none_for_expired_cache(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cache_file = cache_path("old_key")
        cache_file.parent.mkdir(exist_ok=True)

        old_timestamp = datetime.now() - timedelta(hours=25)
        cache_entry = {"timestamp": old_timestamp.isoformat(), "data": {"old": "data"}}

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_entry, f)

        result = get_from_cache("old_key", max_age_hours=24)
        assert result is None

    def test_returns_none_for_corrupted_json(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cache_file = cache_path("corrupt_key")
        cache_file.parent.mkdir(exist_ok=True)

        with open(cache_file, "w", encoding="utf-8") as f:
            f.write("{invalid json")

        result = get_from_cache("corrupt_key")
        assert result is None

    def test_returns_none_for_missing_timestamp(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cache_file = cache_path("no_timestamp")
        cache_file.parent.mkdir(exist_ok=True)

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"data": "test"}, f)

        result = get_from_cache("no_timestamp")
        assert result is None

    def test_returns_none_for_missing_data(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cache_file = cache_path("no_data")
        cache_file.parent.mkdir(exist_ok=True)

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"timestamp": datetime.now().isoformat()}, f)

        result = get_from_cache("no_data")
        assert result is None

    def test_custom_max_age(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cache_file = cache_path("custom_age")
        cache_file.parent.mkdir(exist_ok=True)

        timestamp = datetime.now() - timedelta(hours=2)
        cache_entry = {"timestamp": timestamp.isoformat(), "data": {"test": "data"}}

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_entry, f)

        result = get_from_cache("custom_age", max_age_hours=1)
        assert result is None

        result = get_from_cache("custom_age", max_age_hours=3)
        assert result == {"test": "data"}

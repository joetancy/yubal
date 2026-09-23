"""Tests for SyncService audio quality propagation."""

from pathlib import Path
from unittest.mock import patch

from yubal import AudioCodec, DownloadConfig
from yubal_api.services.sync_service import SyncService


class TestSyncServiceAudioQuality:
    """Tests for audio_quality flowing from SyncService to DownloadConfig."""

    def test_quality_passed_to_download_config(self, tmp_path: Path) -> None:
        """audio_quality should be forwarded to DownloadConfig.quality."""
        service = SyncService(
            base_path=tmp_path,
            audio_format="opus",
            audio_quality=7,
        )

        with patch(
            "yubal_api.services.sync_service.create_playlist_downloader"
        ) as mock_create:
            mock_create.return_value = None  # We only care about the config

            try:
                service.run(
                    "https://example.com", None, __import__("yubal").CancelToken()
                )
            except Exception:
                pass  # Expected to fail since downloader is None

            config = mock_create.call_args[0][0]
            assert isinstance(config.download, DownloadConfig)
            assert config.download.quality == 7

    def test_quality_defaults_to_zero(self, tmp_path: Path) -> None:
        """audio_quality should default to 0 (best) when not specified."""
        service = SyncService(base_path=tmp_path, audio_format="opus")
        assert service.audio_quality == 0

    def test_quality_with_different_codecs(self, tmp_path: Path) -> None:
        """audio_quality should propagate regardless of codec."""
        for codec in ["opus", "mp3", "m4a"]:
            service = SyncService(
                base_path=tmp_path,
                audio_format=codec,
                audio_quality=3,
            )

            with patch(
                "yubal_api.services.sync_service.create_playlist_downloader"
            ) as mock_create:
                mock_create.return_value = None

                try:
                    service.run(
                        "https://example.com",
                        None,
                        __import__("yubal").CancelToken(),
                    )
                except Exception:
                    pass

                config = mock_create.call_args[0][0]
                assert config.download.quality == 3
                assert config.download.codec == AudioCodec(codec)


class TestSyncServiceReplayGainLoudness:
    """Tests for ReplayGain loudness propagation."""

    def test_replaygain_loudness_defaults_to_minus_14(self, tmp_path: Path) -> None:
        service = SyncService(base_path=tmp_path)
        assert service.replaygain_loudness == -14

    def test_replaygain_loudness_passed_to_download_config(
        self, tmp_path: Path
    ) -> None:
        service = SyncService(
            base_path=tmp_path,
            apply_replaygain=True,
            replaygain_loudness=-16,
        )

        with patch(
            "yubal_api.services.sync_service.create_playlist_downloader"
        ) as mock_create:
            mock_create.return_value = None

            try:
                service.run(
                    "https://example.com",
                    None,
                    __import__("yubal").CancelToken(),
                )
            except Exception:
                pass

            config = mock_create.call_args[0][0]
            assert config.apply_replaygain is True
            assert config.replaygain_loudness == -16

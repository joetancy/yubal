"""ReplayGain tagging service using rsgain."""

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol

from yubal.config import AudioCodec

logger = logging.getLogger(__name__)


class ReplayGainProtocol(Protocol):
    """Protocol for ReplayGain services.

    Enables dependency injection and testing of ReplayGain functionality.
    """

    def is_available(self) -> bool:
        """Check if the ReplayGain backend is available."""
        ...

    def apply_replaygain(
        self,
        files: list[Path],
        codec: AudioCodec,
        *,
        album_mode: bool = True,
        loudness: int = -14,
    ) -> bool:
        """Apply ReplayGain tags to audio files."""
        ...


# Timeout for rsgain execution (5 minutes should be enough for most albums)
RSGAIN_TIMEOUT = 300


def _is_rsgain_available() -> bool:
    """Check if rsgain is available in PATH.

    Not cached since shutil.which is fast (<1ms) and users may install
    rsgain after starting the server.
    """
    return shutil.which("rsgain") is not None


class ReplayGainService:
    """Service for applying ReplayGain/R128 tags using rsgain.

    rsgain is a fast ReplayGain 2.0 scanner that supports all audio formats.
    For Opus files, it writes RFC 7845 compliant R128 tags (R128_TRACK_GAIN,
    R128_ALBUM_GAIN).

    This service is designed for post-processing freshly downloaded tracks.
    All errors are non-fatal - the service logs warnings and returns False
    on failure, allowing the download pipeline to continue.

    Example:
        >>> service = ReplayGainService()
        >>> if service.is_available():
        ...     success = service.apply_replaygain(files, AudioCodec.OPUS)
        ...     if success:
        ...         print("ReplayGain tags applied")
    """

    def is_available(self) -> bool:
        """Check if rsgain is available in PATH.

        Returns:
            True if rsgain is installed and accessible, False otherwise.
        """
        return _is_rsgain_available()

    def apply_replaygain(
        self,
        files: list[Path],
        codec: AudioCodec,
        *,
        album_mode: bool = True,
        loudness: int = -14,
    ) -> bool:
        """Apply ReplayGain tags to audio files using rsgain.

        Runs rsgain to calculate and write loudness normalization tags.
        For Opus files, uses RFC 7845 compliant R128 tags.

        Args:
            files: List of audio file paths to process.
            codec: Audio codec of the files (affects tag format for Opus).
            album_mode: If True, calculate album gain in addition to track gain.
                       Use False for playlists or partial album downloads.
            loudness: Target loudness in LUFS. Defaults to -14.

        Returns:
            True if rsgain completed successfully, False on any error.
            Errors are logged as warnings but do not raise exceptions.
        """
        if not files:
            logger.debug("No files to process for ReplayGain")
            return True

        if not self.is_available():
            logger.warning(
                "rsgain not found in PATH, skipping ReplayGain tagging. "
                "Install rsgain to enable loudness normalization."
            )
            return False

        # Validate files exist (may have been deleted between download and normalize)
        existing_files = [f for f in files if f.exists()]
        if not existing_files:
            logger.warning("No files found for ReplayGain tagging (all files missing)")
            return False

        # If any files missing in album mode, fall back to track-only
        # (album gain calculation would be wrong with partial files)
        if len(existing_files) < len(files) and album_mode:
            logger.warning(
                "Missing %d file(s), using track-only mode for ReplayGain",
                len(files) - len(existing_files),
            )
            album_mode = False

        cmd = self._build_command(
            existing_files,
            codec,
            album_mode=album_mode,
            loudness=loudness,
        )

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=RSGAIN_TIMEOUT,
                check=False,
            )

            if result.returncode != 0:
                logger.warning(
                    "rsgain failed with exit code %d: %s",
                    result.returncode,
                    result.stderr.strip() or result.stdout.strip(),
                )
                return False

            file_count = len(existing_files)
            mode_desc = "album + track" if album_mode else "track only"
            logger.debug(
                "Applied ReplayGain (%s) to %d file(s)",
                mode_desc,
                file_count,
            )
            return True

        except subprocess.TimeoutExpired:
            logger.warning(
                "rsgain timed out after %d seconds",
                RSGAIN_TIMEOUT,
            )
            return False
        except OSError as e:
            logger.warning("Failed to run rsgain: %s", e)
            return False


    def rescan_library(
        self,
        library_path: Path,
        *,
        loudness: int = -14,
        threads: str = "MAX",
        album_mode: bool = True,
    ) -> bool:
        """Recalculate ReplayGain tags for every supported track in a library.

        Uses rsgain easy mode so each album directory is scanned independently.
        Existing ReplayGain tags are not skipped and are recalculated.

        Args:
            library_path: Root directory of the music library.
            loudness: Target loudness in LUFS. Defaults to -14.
            threads: rsgain worker count or "MAX".
            album_mode: Whether to calculate album gain.

        Returns:
            True if the full library scan completed successfully.
        """
        if not self.is_available():
            logger.warning("rsgain not found in PATH, cannot rescan ReplayGain")
            return False

        if not library_path.is_dir():
            logger.warning("ReplayGain library path does not exist: %s", library_path)
            return False

        preset = (
            "[Global]\n"
            "TagMode=i\n"
            f"TargetLoudness={loudness}\n"
            f"Album={'true' if album_mode else 'false'}\n"
            "\n[Opus]\n"
            "OpusMode=r\n"
        )

        preset_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".ini",
                prefix="yubal-rsgain-",
                delete=False,
            ) as preset_file:
                preset_file.write(preset)
                preset_path = Path(preset_file.name)

            cmd = [
                "rsgain",
                "easy",
                "-p",
                str(preset_path),
                "-m",
                threads,
                str(library_path),
            ]
            result = subprocess.run(cmd, check=False)
            if result.returncode != 0:
                logger.warning(
                    "rsgain library rescan failed with exit code %d",
                    result.returncode,
                )
                return False

            logger.info(
                "ReplayGain library rescan complete at %d LUFS: %s",
                loudness,
                library_path,
            )
            return True
        except OSError as e:
            logger.warning("Failed to run rsgain library rescan: %s", e)
            return False
        finally:
            if preset_path is not None:
                preset_path.unlink(missing_ok=True)

    def _build_command(
        self,
        files: list[Path],
        codec: AudioCodec,
        *,
        album_mode: bool,
        loudness: int = -14,
    ) -> list[str]:
        """Build the rsgain command with appropriate flags.

        Args:
            files: List of audio file paths to process.
            codec: Audio codec of the files.
            album_mode: Whether to calculate album gain.
            loudness: Target loudness in LUFS.

        Returns:
            Command list suitable for subprocess.run().
        """
        # Base command: rsgain custom -q -s i (quiet mode, scan and INSERT tags)
        cmd = ["rsgain", "custom", "-q", "-s", "i", "-l", str(loudness)]

        # Add album mode flag
        if album_mode:
            cmd.append("-a")

        # Use RFC 7845 R128 tags for Opus files
        if codec == AudioCodec.OPUS:
            cmd.extend(["-o", "r"])

        # Add file paths
        cmd.extend(str(f) for f in files)

        return cmd

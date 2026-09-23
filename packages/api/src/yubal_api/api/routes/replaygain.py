"""ReplayGain maintenance API endpoints."""

import asyncio
import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from yubal.services.replaygain import ReplayGainService

from yubal_api.api.deps import SettingsDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/replaygain", tags=["replaygain"])

_rescan_task: asyncio.Task[bool] | None = None
_rescan_loudness: int | None = None
_last_success: bool | None = None


class ReplayGainRescanStatus(BaseModel):
    """Current full-library ReplayGain rescan state."""

    running: bool
    loudness: int
    success: bool | None = None


async def _run_rescan(library_path: object, loudness: int) -> bool:
    """Run the blocking rsgain scan outside the event loop."""
    service = ReplayGainService()
    try:
        return await asyncio.to_thread(
            service.rescan_library,
            library_path,
            loudness=loudness,
        )
    except Exception:
        logger.exception("ReplayGain library rescan failed")
        return False


def _task_done(task: asyncio.Task[bool]) -> None:
    """Store the final result when a background rescan finishes."""
    global _last_success
    if task.cancelled():
        _last_success = False
        return
    try:
        _last_success = task.result()
    except Exception:
        logger.exception("ReplayGain library rescan task failed")
        _last_success = False


@router.get("/rescan")
async def get_rescan_status(settings: SettingsDep) -> ReplayGainRescanStatus:
    """Return the current full-library ReplayGain rescan status."""
    running = _rescan_task is not None and not _rescan_task.done()
    return ReplayGainRescanStatus(
        running=running,
        loudness=_rescan_loudness or settings.replaygain_loudness,
        success=None if running else _last_success,
    )


@router.post(
    "/rescan",
    status_code=status.HTTP_202_ACCEPTED,
    responses={409: {"description": "ReplayGain rescan is already running"}},
)
async def start_rescan(settings: SettingsDep) -> ReplayGainRescanStatus:
    """Start a full-library ReplayGain rescan using configured loudness."""
    global _rescan_task, _rescan_loudness, _last_success

    if _rescan_task is not None and not _rescan_task.done():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="ReplayGain rescan is already running",
        )

    _rescan_loudness = settings.replaygain_loudness
    _last_success = None
    _rescan_task = asyncio.create_task(
        _run_rescan(settings.data, settings.replaygain_loudness),
        name="replaygain-library-rescan",
    )
    _rescan_task.add_done_callback(_task_done)

    return ReplayGainRescanStatus(
        running=True,
        loudness=settings.replaygain_loudness,
        success=None,
    )

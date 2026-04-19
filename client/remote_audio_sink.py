"""
RemoteAudioSink — drains a remote aiortc AudioStreamTrack to sounddevice.

One instance runs per remote participant.  It reads decoded av.AudioFrame
objects, converts to int16 PCM, applies per-user volume gain, and writes
to the shared sd.OutputStream.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

log = logging.getLogger("traxus.remote_sink")

if TYPE_CHECKING:
    import sounddevice as sd
    from aiortc import AudioStreamTrack


class RemoteAudioSink:
    """
    Coroutine-based sink: call `await sink.run()` as an asyncio Task.
    Cancel the task or close the track to stop it.
    """

    def __init__(
        self,
        track: "AudioStreamTrack",
        username: str,
        out_stream: "sd.OutputStream",
        volume_dict: dict[str, int],
    ) -> None:
        self._track = track
        self._username = username
        self._out_stream = out_stream
        self._volume_dict = volume_dict

    async def run(self) -> None:
        import numpy as np
        try:
            from aiortc.mediastreams import MediaStreamError
        except ImportError:
            MediaStreamError = Exception  # type: ignore[assignment,misc]

        try:
            while True:
                frame = await self._track.recv()
                # av.AudioFrame → int16 numpy array
                pcm = frame.to_ndarray().flatten().astype(np.int16)

                level = self._volume_dict.get(self._username, 100)
                if level != 100:
                    pcm = np.clip(
                        pcm.astype(np.float32) * (level / 100.0),
                        -32768, 32767,
                    ).astype(np.int16)

                self._out_stream.write(pcm)
        except MediaStreamError:
            pass  # track ended cleanly
        except Exception:
            log.exception("RemoteAudioSink error for %s", self._username)

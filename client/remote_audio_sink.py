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
        out_stream_holder: list,
        volume_dict: dict[str, int],
    ) -> None:
        self._track = track
        self._username = username
        self._out_stream_holder = out_stream_holder
        self._volume_dict = volume_dict

    async def run(self) -> None:
        import asyncio
        import numpy as np
        loop = asyncio.get_running_loop()
        try:
            from aiortc.mediastreams import MediaStreamError
        except ImportError:
            MediaStreamError = Exception  # type: ignore[assignment,misc]

        try:
            while True:
                frame = await self._track.recv()
                # av.AudioFrame → mono int16 PCM at the frame's sample rate.
                # aiortc delivers stereo s16 interleaved: shape (1, n_ch*samples).
                # Reshape to (samples, n_ch) then average channels → mono.
                arr = frame.to_ndarray()
                n_ch = len(frame.layout.channels)
                if n_ch > 1:
                    pcm = arr.flatten().reshape(-1, n_ch).mean(axis=1).astype(np.int16)
                else:
                    pcm = arr.flatten().astype(np.int16)

                level = self._volume_dict.get(self._username, 100)
                if level != 100:
                    pcm = np.clip(
                        pcm.astype(np.float32) * (level / 100.0),
                        -32768, 32767,
                    ).astype(np.int16)

                try:
                    # Capture stream reference before awaiting so a concurrent
                    # holder swap picks up the new stream on the next iteration.
                    stream = self._out_stream_holder[0]
                    await loop.run_in_executor(None, stream.write, pcm)
                except Exception:
                    pass  # stream swapped or stopped; drop this frame
        except MediaStreamError:
            pass  # track ended cleanly
        except Exception:
            log.exception("RemoteAudioSink error for %s", self._username)

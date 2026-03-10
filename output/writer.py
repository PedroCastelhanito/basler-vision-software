import os

import numpy as np
from imageio_ffmpeg import write_frames


class VideoWriter:
    def __init__(self, path, fps, width, height, pixel_format='gray', writer_config=None):
        self.path = path
        self.fps = fps
        self.size = [width + (width % 2), height + (height % 2)]
        self.pixel_format = self._map_pixel_format(pixel_format)

        writer_config = writer_config or {}
        self.gpu_id = writer_config.get('gpu', -1)
        self.ffmpeg_params = self._get_ffmpeg_params(writer_config)

        self.writer = None

    def _map_pixel_format(self, fmt):
        fmt = (fmt or 'gray').lower()
        if 'bayerbg' in fmt:
            return 'bayer_bggr8'
        if 'bayerrg' in fmt:
            return 'bayer_rggb8'
        if 'bayergb' in fmt:
            return 'bayer_gbrg8'
        if 'bayergr' in fmt:
            return 'bayer_grbg8'
        return 'gray' if 'mono8' in fmt else 'rgb24'

    def _get_ffmpeg_params(self, cfg):
        if self.gpu_id < 0:
            return cfg.get('ffmpeg_params_cpu', ['-preset', 'fast', '-crf', '21', '-pix_fmt', 'yuv420p'])

        params = cfg.get('ffmpeg_params_gpu', ['-preset', 'p1', '-tune', 'll', '-rc', 'constqp', '-qp', '21'])
        return params + ['-gpu', str(self.gpu_id)]

    def open(self):
        codec = 'h264_nvenc' if self.gpu_id >= 0 else 'libx264'
        out_dir = os.path.dirname(self.path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        self.writer = write_frames(
            self.path,
            self.size,
            fps=self.fps,
            pix_fmt_in=self.pixel_format,
            codec=codec,
            quality=None,
            output_params=self.ffmpeg_params,
            macro_block_size=1,
        )
        self.writer.send(None)

    def _pad_frame(self, frame):
        expected_w, expected_h = self.size
        frame_h, frame_w = frame.shape[:2]

        if frame_h > expected_h or frame_w > expected_w:
            raise ValueError(
                f'Frame shape {frame.shape[:2]} exceeds configured size {(expected_h, expected_w)}'
            )

        pad_h = expected_h - frame_h
        pad_w = expected_w - frame_w
        if pad_h == 0 and pad_w == 0:
            return frame

        if frame.ndim == 2:
            pad_width = ((0, pad_h), (0, pad_w))
        else:
            pad_width = ((0, pad_h), (0, pad_w), (0, 0))
        return np.pad(frame, pad_width, mode='edge')

    def write(self, frame):
        if self.writer:
            self.writer.send(self._pad_frame(frame))

    def close(self):
        if self.writer:
            self.writer.close()

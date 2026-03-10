import os
import time
import threading

from hardware.basler import BaslerCamera
from output.metadata import MetadataWriter
from output.writer import VideoWriter
from core.subscribers import DisplaySubscriber, VideoSubscriber, preprocess_frame


def camera_stream_process(config, stop_event=None):
    stop_event = stop_event or threading.Event()
    cam = BaslerCamera(config.get('serial'), config.get('settings_path'))
    video_sub = None
    display_sub = None
    metadata = None
    t_pub = None
    publisher_error = []

    try:
        cam.open()

        hw = cam.get_config()
        raw_fmt = hw['pixel_format']
        config.update({'width': hw['width'], 'height': hw['height'], 'pixel_format': raw_fmt})
        fps = config.get('fps', hw['fps'])
        subscribers = []

        v_path = os.path.join(config['out_dir'], config.get('video_filename', f"{config['camera_name']}.mp4"))
        m_path = os.path.join(config['out_dir'], config.get('metadata_filename', f"{config['camera_name']}_metadata.csv"))
        metadata = MetadataWriter(m_path)
        metadata.open(header_info=config)

        input_to_writer = 'rgb24' if 'bayer' in raw_fmt.lower() else raw_fmt

        if config.get('record', True):
            writer = VideoWriter(
                v_path,
                fps,
                config['width'],
                config['height'],
                input_to_writer,
                writer_config=config,
            )
            writer.open()
            video_sub = VideoSubscriber(
                writer,
                stop_event,
                raw_fmt,
                max_queue=config.get('writer_queue_size'),
            )
            subscribers.append(video_sub)

        if config.get('view', True):
            display_sub = DisplaySubscriber(stop_event, config)
            subscribers.append(display_sub)

        def publisher_loop():
            frame_idx = 0
            try:
                cam.start(fps)
                while not stop_event.is_set():
                    frame, timestamp = cam.grab()
                    if frame is None:
                        continue

                    processed_frame = preprocess_frame(frame, raw_fmt)
                    for sub in subscribers:
                        sub.push(processed_frame, timestamp, processed=True)
                    metadata.log_frame(frame_idx, timestamp)
                    frame_idx += 1
            except Exception as exc:
                publisher_error.append(exc)
                stop_event.set()

        t_pub = threading.Thread(target=publisher_loop, daemon=True)
        t_pub.start()

        if video_sub:
            video_sub.start()

        if display_sub is not None:
            display_sub.run_ui_loop()
        else:
            while not stop_event.is_set() and t_pub.is_alive():
                time.sleep(0.1)

        if publisher_error:
            raise publisher_error[0]
    except KeyboardInterrupt:
        stop_event.set()
    finally:
        stop_event.set()
        if t_pub:
            t_pub.join(timeout=2)
        if video_sub:
            video_sub.thread.join(timeout=10)
        cam.close()
        if metadata:
            metadata.close()

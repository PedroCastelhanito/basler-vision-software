import cv2
import threading
from collections import deque


def get_conversion_code(fmt):
    fmt = (fmt or 'gray').lower()
    if 'bayerbg' in fmt:
        return cv2.COLOR_BayerBG2RGB
    if 'bayerrg' in fmt:
        return cv2.COLOR_BayerRG2RGB
    if 'bayergb' in fmt:
        return cv2.COLOR_BayerGB2RGB
    if 'bayergr' in fmt:
        return cv2.COLOR_BayerGR2RGB
    return None


def preprocess_frame(frame, pixel_format):
    conv_code = get_conversion_code(pixel_format)
    if conv_code is None:
        return frame
    return cv2.cvtColor(frame, conv_code)


class FrameSubscriber:
    """Queue-backed frame consumer used by recorder, GUI, and callback helpers."""

    def __init__(self, stop_event, pixel_format='gray', maxlen=10):
        self.stop_event = stop_event
        self.queue = deque(maxlen=maxlen)
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)

        self.pixel_format = (pixel_format or 'gray').lower()
        self.conv_code = get_conversion_code(self.pixel_format)

    def push(self, frame, timestamp, processed=False):
        if not processed and self.conv_code is not None:
            frame = cv2.cvtColor(frame, self.conv_code)

        with self.lock:
            self.queue.append((frame, timestamp))
            self.condition.notify_all()

    def grab(self, timeout=0.1):
        with self.lock:
            stop_requested = getattr(self, '_stop_requested', None)
            if (
                not self.queue
                and not self.stop_event.is_set()
                and not (stop_requested is not None and stop_requested.is_set())
            ):
                self.condition.wait(timeout)
            if self.queue:
                return self.queue.popleft()
            return None, None

    def get_nowait(self):
        with self.lock:
            if self.queue:
                return self.queue.popleft()
            return None, None

    def clear(self):
        with self.lock:
            self.queue.clear()

    def pending_count(self):
        with self.lock:
            return len(self.queue)


class QueueSubscriber(FrameSubscriber):
    """Public queue subscriber for external scripts that want pull-based access."""


class LatestFrameSubscriber(FrameSubscriber):
    """Stores the latest frame so GUI code can poll without draining a queue."""

    def __init__(self, stop_event, pixel_format='gray'):
        super().__init__(stop_event, pixel_format, maxlen=1)
        self._latest = None
        self._latest_lock = threading.Lock()

    def push(self, frame, timestamp, processed=False):
        if not processed and self.conv_code is not None:
            frame = cv2.cvtColor(frame, self.conv_code)
        with self._latest_lock:
            self._latest = (frame, timestamp)
        with self.lock:
            self.queue.clear()
            self.queue.append((frame, timestamp))
            self.condition.notify_all()

    def get_latest(self):
        with self._latest_lock:
            if self._latest is None:
                return None, None
            return self._latest


class ThreadedFrameSubscriber(FrameSubscriber):
    """Base class for subscribers that process frames on a reusable worker thread."""

    def __init__(self, stop_event, pixel_format='gray', maxlen=10, *, thread_name=None):
        super().__init__(stop_event, pixel_format, maxlen=maxlen)
        self.thread = None
        self._thread_name = thread_name or type(self).__name__
        self._stop_requested = threading.Event()

    def _create_thread(self):
        return threading.Thread(target=self._process, name=self._thread_name, daemon=True)

    def start(self):
        thread = self.thread
        if thread is not None and thread.is_alive():
            return
        self._stop_requested.clear()
        self.thread = self._create_thread()
        self.thread.start()

    def stop(self):
        self._stop_requested.set()
        with self.lock:
            self.condition.notify_all()

    def join(self, timeout=None):
        thread = self.thread
        if thread is not None:
            thread.join(timeout=timeout)
            if not thread.is_alive():
                self.thread = None

    def should_run(self):
        return (
            not self.stop_event.is_set() and not self._stop_requested.is_set()
        ) or self.pending_count() > 0

    def _process(self):
        raise NotImplementedError


class VideoSubscriber(ThreadedFrameSubscriber):
    """Subscribes to the stream to encode and save video."""

    def __init__(self, writer, stop_event, pixel_format='gray', max_queue=None):
        super().__init__(stop_event, pixel_format, maxlen=max_queue, thread_name="VideoSubscriber")
        self.writer = writer

    def _process(self):
        while self.should_run():
            frame, _ = self.grab()
            if frame is not None:
                self.writer.write(frame)
        self.writer.close()


class CallbackSubscriber(ThreadedFrameSubscriber):
    """Dispatches frames to a callback on a worker thread."""

    def __init__(self, callback, stop_event, pixel_format='gray', max_queue=10):
        super().__init__(stop_event, pixel_format, maxlen=max_queue, thread_name="CallbackSubscriber")
        self.callback = callback

    def _process(self):
        while self.should_run():
            frame, timestamp = self.grab()
            if frame is not None:
                self.callback(frame, timestamp)


class DisplaySubscriber(FrameSubscriber):
    """Subscribes to the stream to provide a live preview."""

    def __init__(self, stop_event, config):
        super().__init__(stop_event, config.get('pixel_format', 'gray'), maxlen=1)
        self.window_name = config['camera_name']
        self.pos = config.get('window_pos', (100, 100))
        self.scale = config.get('display_scale', 0.25)

    def render_frame(self, frame):
        h, w = frame.shape[:2]
        disp = cv2.resize(frame, (int(w * self.scale), int(h * self.scale)))
        cv2.imshow(self.window_name, disp)
        return disp

    def run_ui_loop(self):
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.moveWindow(self.window_name, self.pos[0], self.pos[1])

        while not self.stop_event.is_set():
            frame, _ = self.grab()
            if frame is not None:
                self.render_frame(frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    self.stop_event.set()
        cv2.destroyWindow(self.window_name)

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
            if not self.queue and not self.stop_event.is_set():
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


class VideoSubscriber(FrameSubscriber):
    """Subscribes to the stream to encode and save video."""

    def __init__(self, writer, stop_event, pixel_format='gray', max_queue=None):
        super().__init__(stop_event, pixel_format, maxlen=max_queue)
        self.writer = writer
        self.thread = threading.Thread(target=self._process, daemon=True)

    def start(self):
        self.thread.start()

    def join(self, timeout=None):
        self.thread.join(timeout=timeout)

    def _process(self):
        while not self.stop_event.is_set() or self.pending_count() > 0:
            frame, _ = self.grab()
            if frame is not None:
                self.writer.write(frame)
        self.writer.close()


class CallbackSubscriber(FrameSubscriber):
    """Dispatches frames to a callback on a worker thread."""

    def __init__(self, callback, stop_event, pixel_format='gray', max_queue=10):
        super().__init__(stop_event, pixel_format, maxlen=max_queue)
        self.callback = callback
        self.thread = threading.Thread(target=self._process, daemon=True)

    def start(self):
        self.thread.start()

    def join(self, timeout=None):
        self.thread.join(timeout=timeout)

    def _process(self):
        while not self.stop_event.is_set() or self.pending_count() > 0:
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

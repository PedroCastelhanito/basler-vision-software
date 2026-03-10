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
    """
    Broadcast-capable subscriber that handles frame queueing and pre-processing.
    Automatically detects if a frame needs debayering or if it is monochrome.
    """

    def __init__(self, stop_event, pixel_format='gray', maxlen=10):
        self.stop_event = stop_event
        self.queue = deque(maxlen=maxlen)
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)

        self.pixel_format = (pixel_format or 'gray').lower()
        self.conv_code = get_conversion_code(self.pixel_format)

    def push(self, frame, timestamp, processed=False):
        """
        Processes the frame (debayer if color, pass-through if mono)
        and adds it to the subscriber's queue.
        """
        if not processed and self.conv_code is not None:
            frame = cv2.cvtColor(frame, self.conv_code)

        with self.lock:
            self.queue.append((frame, timestamp))
            self.condition.notify_all()

    def grab(self, timeout=0.1):
        """Blocks until a processed frame is available or timeout occurs."""
        with self.lock:
            if not self.queue and not self.stop_event.is_set():
                self.condition.wait(timeout)
            if self.queue:
                return self.queue.popleft()
            return None, None


class VideoSubscriber(FrameSubscriber):
    """Subscribes to the stream to encode and save video."""

    def __init__(self, writer, stop_event, pixel_format='gray', max_queue=None):
        super().__init__(stop_event, pixel_format, maxlen=max_queue)
        self.writer = writer
        self.thread = threading.Thread(target=self._process, daemon=True)

    def start(self):
        self.thread.start()

    def _process(self):
        while not self.stop_event.is_set() or len(self.queue) > 0:
            frame, _ = self.grab()
            if frame is not None:
                self.writer.write(frame)
        self.writer.close()


class DisplaySubscriber(FrameSubscriber):
    """Subscribes to the stream to provide a live preview."""

    def __init__(self, stop_event, config):
        super().__init__(stop_event, config.get('pixel_format', 'gray'), maxlen=1)
        self.window_name = config['camera_name']
        self.pos = config.get('window_pos', (100, 100))
        self.scale = config.get('display_scale', 0.25)

    def run_ui_loop(self):
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.moveWindow(self.window_name, self.pos[0], self.pos[1])

        while not self.stop_event.is_set():
            frame, _ = self.grab()
            if frame is not None:
                h, w = frame.shape[:2]
                disp = cv2.resize(frame, (int(w * self.scale), int(h * self.scale)))
                cv2.imshow(self.window_name, disp)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    self.stop_event.set()
        cv2.destroyAllWindows()

import queue
import threading
from collections import deque

class StreamBuffer:
    def __init__(self):
        """
        Thread-safe buffer system. Uses a deque for the writer to ensure 
        every frame is captured without silent drops.
        """
        self.write_queue = deque()
        self.display_queue = deque(maxlen=1)
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)

    def push(self, frame, timestamp):
        """Add a frame and its hardware timestamp to buffers."""
        with self.lock:
            self.write_queue.append((frame, timestamp))
            self.display_queue.append(frame)
            self.condition.notify()

    def pop_write(self, timeout=0.01):
        """Get next frame and timestamp for the video writer.
        Waits for a frame to be available or until timeout."""
        with self.lock:
            if not self.write_queue:
                self.condition.wait(timeout)
            if self.write_queue:
                return self.write_queue.popleft()
            return None, None

    def get_latest(self):
        try:
            return self.display_queue[-1]
        except IndexError:
            return None
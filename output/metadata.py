import csv
import os

from core.logging_utils import log_step


class MetadataWriter:
    def __init__(self, path, log_config=None):
        self.path = path
        self.log_config = log_config
        self.file = None
        self.writer = None
        self.start_timestamp = None

    def open(self):
        """Initialize the CSV file with frame timing columns."""
        out_dir = os.path.dirname(self.path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        self.file = open(self.path, 'w', newline='', encoding='utf-8')
        self.writer = csv.writer(self.file)
        self.writer.writerow(['Index', 'TimeStamp(s)'])
        log_step('MetadataWriter.open', f'Metadata writer ready at {self.path}.', self.log_config)

    def log_frame(self, index, timestamp):
        """Log frame index and elapsed recording time."""
        if self.writer:
            if self.start_timestamp is None:
                self.start_timestamp = timestamp
            elapsed = timestamp - self.start_timestamp
            self.writer.writerow([index, elapsed])

    def close(self):
        if self.file:
            self.file.flush()
            self.file.close()
            log_step('MetadataWriter.close', f'Metadata file closed for {self.path}.', self.log_config)

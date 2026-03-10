import csv
import os
import time


class MetadataWriter:
    def __init__(self, path, camera_name=None):
        self.path = os.path.join(path, f'{camera_name}_metadata.csv') if camera_name else path
        self.file = None
        self.writer = None

    def open(self, header_info=None):
        """Initialize the CSV file and write experiment headers."""
        out_dir = os.path.dirname(self.path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        self.file = open(self.path, 'w', newline='', encoding='utf-8')
        self.writer = csv.writer(self.file)

        if header_info:
            for key, value in header_info.items():
                self.writer.writerow([f'# {key}', value])

        self.writer.writerow(['FrameIndex', 'Timestamp', 'SystemTime'])

    def log_frame(self, index, timestamp):
        """Log individual frame data."""
        if self.writer:
            self.writer.writerow([index, timestamp, time.time()])

    def close(self):
        if self.file:
            self.file.flush()
            self.file.close()

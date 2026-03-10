import multiprocessing as mp
import signal

from core.publisher import camera_stream_process


def _run_stream(cfg, stop_event):
    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    except ValueError:
        pass

    camera_stream_process(cfg, stop_event=stop_event)


class ExperimentEngine:
    def __init__(self, camera_configs):
        self.configs = camera_configs
        self.processes = []
        self.ctx = mp.get_context("spawn")
        self.stop_event = self.ctx.Event()

    def start(self):
        for cfg in self.configs:
            p = self.ctx.Process(target=_run_stream, args=(cfg, self.stop_event))
            p.start()
            self.processes.append(p)

    def stop(self):
        print("Signaling all streams to stop...")
        self.stop_event.set()

        for p in self.processes:
            p.join(timeout=15)

        for p in self.processes:
            if p.is_alive():
                p.terminate()
                p.join(timeout=5)

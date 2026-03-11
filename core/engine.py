import multiprocessing as mp
import signal

from core.logging_utils import log_step
from core.process import camera_stream_process


def _run_stream(cfg, stop_event):
    camera_name = cfg.get('camera_name', 'camera')
    log_step('_run_stream', f'Starting stream worker for {camera_name}.', cfg, always=True)

    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    except ValueError:
        pass

    camera_stream_process(cfg, stop_event=stop_event)
    log_step('_run_stream', f'Stream worker finished for {camera_name}.', cfg)


class ExperimentEngine:
    def __init__(self, camera_configs):
        self.configs = camera_configs
        self.processes = []
        self.ctx = mp.get_context('spawn')
        self.stop_event = self.ctx.Event()

    def start(self):
        log_step('ExperimentEngine.start', f'Starting {len(self.configs)} camera process(es).', self.configs, always=True)
        for cfg in self.configs:
            camera_name = cfg.get('camera_name', 'camera')
            p = self.ctx.Process(target=_run_stream, args=(cfg, self.stop_event))
            p.start()
            self.processes.append(p)
            log_step('ExperimentEngine.start', f'Process {p.pid} launched for {camera_name}.', cfg)

    def stop(self):
        log_step('ExperimentEngine.stop', 'Signaling all streams to stop...', self.configs, always=True)
        self.stop_event.set()

        for p in self.processes:
            p.join(timeout=15)
            log_step('ExperimentEngine.stop', f'Join completed for process {p.pid}.', self.configs)

        for p in self.processes:
            if p.is_alive():
                log_step('ExperimentEngine.stop', f'Process {p.pid} still alive, terminating.', self.configs, always=True)
                p.terminate()
                p.join(timeout=5)

import argparse
import os
import time

from basler_vision import get_default_config_path, load_runtime_config
from basler_vision.core.engine import ExperimentEngine
from basler_vision.core.logging_utils import log_step


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a basic Basler camera smoke test.")
    parser.add_argument("--config", default=None, help="Path to a runtime JSON config.")
    parser.add_argument("--duration", type=float, default=10.0, help="How long to run the smoke test in seconds.")
    parser.add_argument("--serial", default=None, help="Optional camera serial number override.")
    parser.add_argument("--camera-name", default="DebugCam", help="Logical camera name to report in logs.")
    parser.add_argument("--out-dir", default="output", help="Output directory for video and metadata.")
    parser.add_argument("--view", action="store_true", help="Enable OpenCV preview window.")
    parser.add_argument("--record", action="store_true", help="Enable video recording.")
    return parser


def run_test(config_path=None, overrides=None, duration=10.0):
    config_path = config_path or str(get_default_config_path())
    config = load_runtime_config(config_path, overrides=overrides, default_camera_name="DebugCam")
    os.makedirs(config["out_dir"], exist_ok=True)

    log_step("run_test", f"Starting test for {config['camera_name']}.", config, always=True)
    log_step(
        "run_test",
        f"Recording={config['record']} | Viewing={config['view']} | Duration={duration}s",
        config,
        always=True,
    )

    engine = ExperimentEngine([config])
    engine.start()

    start_time = time.time()
    try:
        while any(process.is_alive() for process in engine.processes):
            if time.time() - start_time > duration:
                log_step("run_test", "Duration reached.", config, always=True)
                break
            time.sleep(0.1)
    except KeyboardInterrupt:
        log_step("run_test", "Test interrupted by user.", config, always=True)
    finally:
        engine.stop()

    log_step("run_test", "Test complete. Shutting down...", config, always=True)


def main():
    args = build_parser().parse_args()
    overrides = {
        "camera_name": args.camera_name,
        "out_dir": args.out_dir,
        "record": args.record,
        "serial": args.serial,
        "view": args.view,
    }
    run_test(config_path=args.config, overrides=overrides, duration=args.duration)


if __name__ == "__main__":
    main()

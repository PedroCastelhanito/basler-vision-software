from core.controller import CameraStreamController
from core.logging_utils import log_step


def camera_stream_process(config, stop_event=None):
    controller = CameraStreamController(config, stop_event=stop_event)
    camera_name = controller.config.get('camera_name', 'camera')
    log_step('camera_stream_process', f'Initializing stream for {camera_name}.', controller.config, always=True)

    try:
        controller.start()
        if controller.display_subscriber is not None:
            controller.run_preview_loop()
        else:
            controller.wait()
        controller.raise_if_failed()
    except KeyboardInterrupt:
        log_step('camera_stream_process', 'Keyboard interrupt received.', controller.config, always=True)
        controller.stop()
    finally:
        log_step('camera_stream_process', f'Cleaning up stream for {camera_name}.', controller.config, always=True)
        controller.cleanup()

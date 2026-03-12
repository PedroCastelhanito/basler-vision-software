def is_debug_enabled(config):
    if isinstance(config, dict):
        return bool(config.get('debug', config.get('verbose', False)))

    if isinstance(config, (list, tuple)):
        return any(is_debug_enabled(item) for item in config)

    return bool(config)


def log_step(source, message, config=None, always=False):
    if is_debug_enabled(config):
        print(f'[{source}] {message}')
    elif always:
        print(f'[status] - {message}')

"""Read only the notes API key; never export file contents to child processes."""
from pathlib import Path


def file_key(path: Path) -> str:
    try:
        with path.open(encoding='utf-8-sig') as config:
            for line in config:
                name, sep, value = line.partition('=')
                if sep and name.strip() == 'VN_AI_KEY':
                    value = value.strip()
                    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                        value = value[1:-1]
                    return value.strip()
    except FileNotFoundError:
        pass
    return ''

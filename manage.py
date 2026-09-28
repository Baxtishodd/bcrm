#!/usr/bin/env python
import os
import sys


def main():
    from config.settings import get_settings_module

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", get_settings_module(default="local"))
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError("Django topilmadi. Avval loyiha paketlarini o'rnating.") from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()

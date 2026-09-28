import os

from django.core.asgi import get_asgi_application

from config.settings import get_settings_module

os.environ.setdefault("DJANGO_SETTINGS_MODULE", get_settings_module(default="production"))
application = get_asgi_application()

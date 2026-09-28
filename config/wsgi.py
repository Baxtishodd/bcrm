import os

from django.core.wsgi import get_wsgi_application

from config.settings import get_settings_module

os.environ.setdefault("DJANGO_SETTINGS_MODULE", get_settings_module(default="production"))
application = get_wsgi_application()

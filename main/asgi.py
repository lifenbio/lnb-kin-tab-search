import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
#from notification.urls import urlpatterns

os.environ.setdefault("DJANGO_SETTINGS_MODULE",
                      "main.settings.prod")

'''
application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            urlpatterns
        )
    ),
})
'''
application = get_asgi_application()
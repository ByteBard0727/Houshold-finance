import os
import django
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from dashboard import routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expenses_site.settings')
django.setup()
# need to make sure django has loaded fully before moving to getting the application


application = ProtocolTypeRouter({
    "http": get_asgi_application(),  
    "websocket": AuthMiddlewareStack(
        URLRouter(
            routing.websocket_urlpatterns
        )
    ),
})

import os
import django
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from dashboard import routing  # Import your WebSocket routes

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expenses_site.settings')
django.setup()
# Ensure Django is fully loaded


application = ProtocolTypeRouter({
    "http": get_asgi_application(),  # Handles regular HTTP requests
    "websocket": AuthMiddlewareStack(  # Handles WebSocket connections
        URLRouter(
            routing.websocket_urlpatterns
        )
    ),
})

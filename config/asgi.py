import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.asgi import get_asgi_application

from topology.ssh_gateway import ssh_websocket_application
from topology.status_gateway import status_websocket_application

django_asgi_app = get_asgi_application()


async def application(scope, receive, send):
    if scope["type"] == "websocket":
        if scope.get("path") == "/ws/status/":
            await status_websocket_application(scope, receive, send)
            return
        await ssh_websocket_application(scope, receive, send)
        return

    await django_asgi_app(scope, receive, send)

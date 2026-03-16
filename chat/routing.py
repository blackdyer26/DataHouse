from django.urls import re_path
from .consumers import ChatMiddlewareConsumer

websocket_urlpatterns = [
    re_path(r'ws/chat/middleware/$', ChatMiddlewareConsumer.as_asgi()),
]
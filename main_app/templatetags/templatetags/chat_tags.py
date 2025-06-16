from django import template
from models import ChatMessage

register = template.Library()

@register.filter
def unread_count(room, user):
    return ChatMessage.objects.filter(
        room=room,
        read=False
    ).exclude(sender=user).count()
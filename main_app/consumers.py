import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import ChatRoom, ChatMessage
from django.contrib.auth import get_user_model

User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'
        
        # Verify user is in the room
        user = self.scope['user']
        if user.is_anonymous:
            await self.close()
            return
            
        if await self.is_user_in_room(user.id, self.room_id):
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            await self.accept()
        else:
            await self.close()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        
        if 'typing' in text_data_json:
            # Handle typing notification
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'typing_notification',
                    'typing': text_data_json['typing'],
                    'sender_id': text_data_json['sender_id'],
                    'sender_name': (await self.get_user(text_data_json['sender_id'])).get_full_name()
                }
            )
        else:
            # Handle regular message
            message = text_data_json['message']
            sender_id = text_data_json['sender_id']
            
            # Save message to database
            room = await self.get_room(self.room_id)
            sender = await self.get_user(sender_id)
            message_obj = await self.create_message(room, sender, message)
            
            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'sender_id': sender_id,
                    'sender_name': sender.get_full_name(),
                    'timestamp': message_obj.timestamp.strftime("%b %d, %Y %I:%M %p"),
                    'message_id': message_obj.id
                }
            )

    async def typing_notification(self, event):
        await self.send(text_data=json.dumps({
            'typing': event['typing'],
            'sender_id': event['sender_id'],
            'sender_name': event['sender_name']
        }))

        async def chat_message(self, event):
            await self.send(text_data=json.dumps({
                'message': event['message'],
                'sender_id': event['sender_id'],
                'sender_name': event['sender_name'],
                'timestamp': event['timestamp'],
                'message_id': event['message_id']
            }))
    
    @database_sync_to_async
    def is_user_in_room(self, user_id, room_id):
        return ChatRoom.objects.filter(id=room_id, participants__id=user_id).exists()
    
    @database_sync_to_async
    def get_room(self, room_id):
        return ChatRoom.objects.get(id=room_id)
    
    @database_sync_to_async
    def get_user(self, user_id):
        return User.objects.get(id=user_id)
    
    @database_sync_to_async
    def create_message(self, room, sender, message):
        return ChatMessage.objects.create(
            room=room,
            sender=sender,
            message=message
        )
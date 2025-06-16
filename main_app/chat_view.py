from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q
from django.contrib.auth import get_user_model
from .models import ChatRoom, ChatMessage
from django.contrib import messages
from django.core.paginator import Paginator

User = get_user_model()

@login_required   
def chat_home(request):
    chat_rooms = ChatRoom.objects.filter(participants=request.user).order_by('-last_activity')
    
    # Add unread counts to each room
    for room in chat_rooms:
        room.unread_count = ChatMessage.objects.filter(
            room=room, 
            read=False
        ).exclude(sender=request.user).count()
    
    context = {
        'chat_rooms': chat_rooms,
        'page_title': "Chat",
    }
    return render(request, "chat/chat_home.html", context)

@login_required
def chat_room(request, room_id):
    """
    View for a specific chat room
    """
    room = get_object_or_404(ChatRoom, id=room_id, participants=request.user)
    messages = ChatMessage.objects.filter(room=room).order_by('timestamp')
    
    # Mark messages as read when viewing
    unread_messages = messages.filter(read=False).exclude(sender=request.user)
    unread_messages.update(read=True)
    def get_unread_count(self, user):
        return ChatMessage.objects.filter(
            room=self,
            read=False
        ).exclude(sender=user).count()

    
    # Pagination
    paginator = Paginator(messages, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'room': room,
        'page_obj': page_obj,
        'other_user': room.get_other_participant(request.user),
        'page_title': f"Chat with {room.get_other_participant(request.user)}" if not room.is_group else room.name,
    }
    return render(request, "chat/chat_room.html", context)

@login_required
def start_chat(request, user_id):
    """
    Start a new 1-on-1 chat with a user
    """
    other_user = get_object_or_404(User, id=user_id)
    
    # Check if a chat room already exists between these two users
    existing_room = ChatRoom.objects.filter(
        participants=request.user,
        is_group=False
    ).filter(participants=other_user).first()
    
    if existing_room:
        return redirect('chat_room', room_id=existing_room.id)
    
    # Create new chat room
    new_room = ChatRoom.objects.create(is_group=False)
    new_room.participants.add(request.user, other_user)
    
    return redirect('chat_room', room_id=new_room.id)

@login_required
def send_message(request, room_id):
    if request.method == 'POST':
        room = get_object_or_404(ChatRoom, id=room_id, participants=request.user)
        message_text = request.POST.get('message', '').strip()
        attachment = request.FILES.get('attachment')
        
        if message_text or attachment:
            message = ChatMessage.objects.create(
                room=room,
                sender=request.user,
                message=message_text,
                attachment=attachment,
                attachment_name=attachment.name if attachment else None
            )
            room.update_last_activity()
            
            return JsonResponse({
                'status': 'success',
                'message': {
                    'id': message.id,
                    'text': message.message,
                    'sender': message.sender.get_full_name(),
                    'timestamp': message.timestamp.strftime("%b %d, %Y %I:%M %p"),
                    'is_sender': True,
                    'attachment': {
                        'url': message.attachment.url if message.attachment else None,
                        'name': message.attachment_name
                    }
                }
            })
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})

@login_required
def get_new_messages(request, room_id, last_message_id):
    """
    API endpoint for getting new messages
    """
    room = get_object_or_404(ChatRoom, id=room_id, participants=request.user)
    new_messages = ChatMessage.objects.filter(
        room=room,
        id__gt=last_message_id
    ).exclude(sender=request.user).order_by('timestamp')
    
    # Mark messages as read when fetched
    new_messages.update(read=True)
    
    messages_data = [{
        'id': msg.id,
        'text': msg.message,
        'sender': msg.sender.get_full_name(),
        'timestamp': msg.timestamp.strftime("%b %d, %Y %I:%M %p"),
        'is_sender': False
    } for msg in new_messages]
    
    return JsonResponse({
        'status': 'success',
        'messages': messages_data
    })

@login_required
def search_users(request):
    """
    Search for users to start a chat with
    """
    query = request.GET.get('q', '')
    if query:
        users = User.objects.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(username__icontains=query)
        ).exclude(id=request.user.id).order_by('first_name')
    else:
        users = User.objects.none()
    
    return render(request, 'chat/user_search_results.html', {'users': users})


@login_required
def mark_messages_read(request, room_id):
    if request.method == 'POST':
        room = get_object_or_404(ChatRoom, id=room_id, participants=request.user)
        ChatMessage.objects.filter(
            room=room,
            read=False
        ).exclude(sender=request.user).update(read=True)
        
        return JsonResponse({'status': 'success'})
    
    return JsonResponse({'status': 'error'}, status=400)



@login_required
def create_group_chat(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        participant_ids = request.POST.getlist('participants')
        
        if not name or not participant_ids:
            messages.error(request, "Please provide a name and select participants")
            return redirect('chat_home')
        
        # Create the group chat
        group_chat = ChatRoom.objects.create(
            is_group=True,
            name=name
        )
        group_chat.participants.add(request.user)
        group_chat.participants.add(*participant_ids)
        
        messages.success(request, "Group chat created successfully")
        return redirect('chat_room', room_id=group_chat.id)
    
    # Get users the current user can chat with
    users = User.objects.exclude(id=request.user.id).order_by('first_name')
    
    return render(request, 'chat/create_group_chat.html', {
        'users': users,
        'page_title': "Create Group Chat"
    })
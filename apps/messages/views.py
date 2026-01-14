from django.views import View
from django.shortcuts import render, get_object_or_404
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.utils import timezone
from .models import Conversation, Message, ConvUser
from .utils import get_or_create_conversation, create_message

User = get_user_model()


class MessagesView(LoginRequiredMixin, View):
    template_name = "messages/messages_page.html"

    def get(self, request, *args, **kwargs):
        context = {
            "page": "Messages",
        }
        return render(request, self.template_name, context=context)


class ConversationsView(LoginRequiredMixin, View):
    template_name = "messages/conversations.html"

    def get(self, request, *args, **kwargs):
        get_or_create_conversation(request.user)
        conversations = Conversation.objects.filter(
            participants=request.user
        ).order_by("-updated_at")

        conversations_extended = []
        for conversation in conversations:
            is_self = conversation.participants.count() == 1
            if is_self:
                receiver = request.user
            else:
                receiver = conversation.participants.exclude(
                    pk=request.user.pk
                ).first()

            my_convuser = ConvUser.objects.filter(
                conversation=conversation, user=request.user
            ).first()

            conversations_extended.append(
                {
                    "conversation": conversation,
                    "receiver": receiver,
                    "is_self": is_self,
                    "my_convuser": my_convuser,
                }
            )

        context = {
            "conversations": conversations_extended,
        }
        return render(request, self.template_name, context=context)


class ChatView(LoginRequiredMixin, View):
    template_name = "messages/chat.html"

    def get(self, request, receiver_id, *args, **kwargs):
        receiver = get_object_or_404(User, id=receiver_id)
        if receiver and receiver != request.user:
            chat = get_or_create_conversation(request.user, receiver)
            is_self = False
        else:
            chat = get_or_create_conversation(request.user)
            is_self = True

        messages = reversed(
            Message.objects.filter(conversation=chat).order_by("-created_at")[
                :100
            ]
        )

        ConvUser.objects.filter(conversation=chat, user=request.user).update(
            unread_count=0, last_seen_at=timezone.now()
        )

        context = {
            "page": "Messages",
            "receiver": receiver,
            "chat": chat,
            "messages": messages,
            "is_self": is_self,
        }
        return render(request, self.template_name, context=context)


class SendMessageView(LoginRequiredMixin, View):
    template_name = "messages/message.html"

    def post(self, request, receiver_id, *args, **kwargs):
        receiver = get_object_or_404(User, id=receiver_id)

        body = request.POST.get("body", "").strip()
        image = request.FILES.get("image")

        if not body and not image:
            return HttpResponse(status=204)

        message = create_message(
            sender=request.user,
            receiver=receiver,
            body=body,
            image=image,
        )

        context = {
            "message": message,
        }
        return render(request, self.template_name, context=context)


class DeleteMessageView(LoginRequiredMixin, View):
    def delete(self, request, message_id, *args, **kwargs):
        message = get_object_or_404(Message, id=message_id)

        if message.sender != request.user:
            return HttpResponse(status=403)

        message.delete()
        return HttpResponse("")

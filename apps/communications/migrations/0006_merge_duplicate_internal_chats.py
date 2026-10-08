from collections import defaultdict

from django.db import migrations


def merge_duplicate_internal_chats(apps, schema_editor):
    Conversation = apps.get_model("communications", "Conversation")
    ConversationParticipant = apps.get_model(
        "communications",
        "ConversationParticipant",
    )
    Message = apps.get_model("communications", "Message")

    groups = defaultdict(list)
    conversations = Conversation.objects.filter(channel="internal").order_by("id")
    for conversation in conversations.iterator():
        user_ids = tuple(
            sorted(
                ConversationParticipant.objects.filter(
                    conversation_id=conversation.id,
                ).values_list("user_id", flat=True)
            )
        )
        if len(user_ids) == 2:
            groups[(conversation.organization_id, user_ids)].append(conversation)

    for (organization_id, user_ids), group in groups.items():
        conversation_ids = [conversation.id for conversation in group]
        Conversation.objects.filter(id__in=conversation_ids).update(
            internal_direct_key=None,
        )
        canonical = group[0]
        latest_message_at = canonical.last_message_at

        for duplicate in group[1:]:
            duplicate_states = ConversationParticipant.objects.filter(
                conversation_id=duplicate.id,
            )
            for state in duplicate_states:
                canonical_state, created = ConversationParticipant.objects.get_or_create(
                    organization_id=organization_id,
                    conversation_id=canonical.id,
                    user_id=state.user_id,
                    defaults={
                        "unread_count": state.unread_count,
                        "last_read_at": state.last_read_at,
                    },
                )
                if not created:
                    canonical_state.unread_count += state.unread_count
                    if state.last_read_at and (
                        canonical_state.last_read_at is None
                        or state.last_read_at > canonical_state.last_read_at
                    ):
                        canonical_state.last_read_at = state.last_read_at
                    canonical_state.save(
                        update_fields=["unread_count", "last_read_at", "updated_at"]
                    )
            Message.objects.filter(conversation_id=duplicate.id).update(
                conversation_id=canonical.id,
            )
            if duplicate.last_message_at and (
                latest_message_at is None
                or duplicate.last_message_at > latest_message_at
            ):
                latest_message_at = duplicate.last_message_at
            duplicate.delete()

        canonical.internal_direct_key = f"{user_ids[0]}:{user_ids[1]}"
        canonical.last_message_at = latest_message_at
        canonical.save(update_fields=["internal_direct_key", "last_message_at", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("communications", "0005_conversationparticipant_and_more"),
    ]

    operations = [
        migrations.RunPython(
            merge_duplicate_internal_chats,
            migrations.RunPython.noop,
        ),
    ]

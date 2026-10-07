def build_communication_timeline(*, activities=(), deliveries=(), messages=()):
    events = []
    for activity in activities:
        events.append(
            {
                "kind": "activity",
                "occurred_at": activity.created_at,
                "activity": activity,
            }
        )
    for delivery in deliveries:
        events.append(
            {
                "kind": "delivery",
                "occurred_at": delivery.sent_at,
                "delivery": delivery,
            }
        )
    for message in messages:
        events.append(
            {
                "kind": "message",
                "occurred_at": message.sent_at,
                "message": message,
            }
        )
    return sorted(events, key=lambda event: event["occurred_at"], reverse=True)

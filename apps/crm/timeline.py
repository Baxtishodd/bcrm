def build_communication_timeline(*, activities=(), deliveries=()):
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
    return sorted(events, key=lambda event: event["occurred_at"], reverse=True)

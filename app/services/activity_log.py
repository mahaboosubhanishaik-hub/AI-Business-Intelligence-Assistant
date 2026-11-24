from app import db
from app.models.activity_log import ActivityLog


def record_activity(user_id, event_type, description, dataset_id=None):
    db.session.add(
        ActivityLog(
            user_id=user_id,
            dataset_id=dataset_id,
            event_type=event_type,
            description=description
        )
    )

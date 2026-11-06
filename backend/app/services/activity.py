import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session

from backend.app.models import ActivityLog


def log_activity(
    db: Session,
    action: str,
    target: str = "",
    user_id: Optional[uuid.UUID] = None,
    project_id: Optional[uuid.UUID] = None,
    **details: Any,
) -> None:
    db.add(ActivityLog(action=action, target=target, user_id=user_id, project_id=project_id, details=details))

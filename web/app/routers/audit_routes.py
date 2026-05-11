from fastapi import APIRouter, Query, Request

from ..auth import authorize_section, render_template
from ..database import fetch_all
from ..utils import build_options


router = APIRouter()


@router.get("/audit")
def audit_page(
    request: Request,
    user_id: int | None = Query(default=None),
    table_name: str | None = Query(default=None),
    action_type: str | None = Query(default=None),
    changed_date: str | None = Query(default=None),
):
    user = authorize_section(request, "audit")
    if not isinstance(user, dict):
        return user

    filters = []
    params = []
    if user_id:
        filters.append("al.user_id = %s")
        params.append(user_id)
    if table_name:
        filters.append("al.table_name = %s")
        params.append(table_name)
    if action_type:
        filters.append("al.action_type = %s")
        params.append(action_type)
    if changed_date:
        filters.append("al.changed_at::DATE = %s")
        params.append(changed_date)

    query = """
        SELECT
            al.audit_id,
            al.changed_at,
            COALESCE(u.username, 'system') AS username,
            al.action_type,
            al.table_name,
            al.record_id,
            al.success
        FROM audit_log AS al
        LEFT JOIN users AS u ON u.user_id = al.user_id
    """
    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY al.changed_at DESC, al.audit_id DESC"
    rows = fetch_all(query, tuple(params))

    users = fetch_all("SELECT user_id, username FROM users ORDER BY username")
    tables = fetch_all("SELECT DISTINCT table_name FROM audit_log ORDER BY table_name")

    return render_template(
        request,
        "audit.html",
        {
            "title": "Журнал аудита",
            "rows": rows,
            "user_id": user_id or "",
            "table_name": table_name or "",
            "action_type": action_type or "",
            "changed_date": changed_date or "",
            "user_options": build_options(users, "user_id", "username", blank_label="Все пользователи"),
            "table_options": build_options(tables, "table_name", "table_name", blank_label="Все таблицы"),
            "action_options": [
                {"value": "", "label": "Все действия"},
                {"value": "INSERT", "label": "INSERT"},
                {"value": "UPDATE", "label": "UPDATE"},
                {"value": "DELETE", "label": "DELETE"},
                {"value": "LOGIN", "label": "LOGIN"},
                {"value": "LOGOUT", "label": "LOGOUT"},
            ],
        },
    )

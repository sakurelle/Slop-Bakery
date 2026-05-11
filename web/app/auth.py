from fastapi import Request
from fastapi.responses import RedirectResponse
from passlib.context import CryptContext

from .database import fetch_one, get_db
from .permissions import can_access, get_primary_role, visible_sections


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SESSION_KEY = "user"
FLASH_KEY = "_flash"


def _load_user(field_name: str, field_value):
    query = f"""
        SELECT
            u.user_id,
            u.username,
            u.password_hash,
            u.full_name,
            u.email,
            u.phone,
            u.status_code,
            u.customer_id,
            u.created_at,
            u.last_login_at,
            COALESCE(
                ARRAY_AGG(r.role_code) FILTER (WHERE r.role_code IS NOT NULL),
                ARRAY[]::VARCHAR[]
            ) AS roles
        FROM users AS u
        LEFT JOIN user_roles AS ur ON ur.user_id = u.user_id
        LEFT JOIN roles AS r ON r.role_id = ur.role_id
        WHERE u.{field_name} = %s
        GROUP BY
            u.user_id,
            u.username,
            u.password_hash,
            u.full_name,
            u.email,
            u.phone,
            u.status_code,
            u.customer_id,
            u.created_at,
            u.last_login_at
    """
    row = fetch_one(query, (field_value,))
    if row:
        row["roles"] = list(row.get("roles", []))
        row["primary_role"] = get_primary_role(row)
    return row


def get_user_by_username(username: str):
    return _load_user("username", username)


def get_user_by_id(user_id: int):
    return _load_user("user_id", user_id)


def authenticate_user(username: str, password: str):
    user = get_user_by_username(username)
    if not user or user["status_code"] != "active":
        return None
    if not pwd_context.verify(password, user["password_hash"]):
        return None
    return user


def get_current_user(request: Request):
    return request.session.get(SESSION_KEY)


def set_flash(request: Request, message: str, category: str = "success") -> None:
    request.session[FLASH_KEY] = {"message": message, "category": category}


def pop_flash(request: Request):
    return request.session.pop(FLASH_KEY, None)


def login_user(request: Request, user: dict) -> None:
    request.session[SESSION_KEY] = {
        "user_id": user["user_id"],
        "username": user["username"],
        "full_name": user["full_name"],
        "email": user["email"],
        "customer_id": user["customer_id"],
        "status_code": user["status_code"],
        "roles": user.get("roles", []),
        "primary_role": get_primary_role(user),
    }


def record_login(user: dict, client_ip: str | None) -> None:
    with get_db(user_id=user["user_id"], user_ip=client_ip) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE user_id = %s",
                (user["user_id"],),
            )
            cur.execute(
                "SELECT log_auth_event(%s, %s, %s, %s)",
                (user["user_id"], "LOGIN", client_ip, True),
            )


def logout_user(request: Request) -> None:
    user = get_current_user(request)
    if user:
        client_ip = request.client.host if request.client else None
        with get_db(user_id=user["user_id"], user_ip=client_ip) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT log_auth_event(%s, %s, %s, %s)",
                    (user["user_id"], "LOGOUT", client_ip, True),
                )
    request.session.clear()


def render_template(request: Request, template_name: str, context=None, status_code: int = 200):
    current_user = get_current_user(request)
    payload = {
        "request": request,
        "current_user": current_user,
        "primary_role": get_primary_role(current_user),
        "nav_items": visible_sections(current_user),
        "flash": pop_flash(request),
        "can_access": can_access,
    }
    if context:
        payload.update(context)
    return request.app.state.templates.TemplateResponse(template_name, payload, status_code=status_code)


def redirect_to(path: str):
    return RedirectResponse(path, status_code=303)


def authorize_section(request: Request, section: str):
    user = get_current_user(request)
    if not user:
        return redirect_to("/login")
    if not can_access(user, section):
        return render_template(
            request,
            "error.html",
            {
                "title": "Access denied",
                "message": "You do not have permission to open this section.",
            },
            status_code=403,
        )
    return user

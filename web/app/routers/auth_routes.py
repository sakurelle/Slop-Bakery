from fastapi import APIRouter, Form, Request

from ..auth import (
    authenticate_user,
    get_current_user,
    login_user,
    logout_user,
    record_login,
    redirect_to,
    render_template,
    set_flash,
)


router = APIRouter()


@router.get("/login")
def login_page(request: Request):
    if get_current_user(request):
        return redirect_to("/")
    return render_template(request, "login.html", {"title": "Вход"})


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    user = authenticate_user(username.strip(), password)
    if not user:
        return render_template(
            request,
            "login.html",
            {
                "title": "Вход",
                "error_message": "Неверный логин или пароль.",
                "form_data": {"username": username},
            },
            status_code=401,
        )

    login_user(request, user)
    record_login(user, request.client.host if request.client else None)
    set_flash(request, "Вход выполнен успешно.")
    return redirect_to("/")


@router.get("/logout")
def logout(request: Request):
    logout_user(request)
    set_flash(request, "Вы вышли из системы.", "info")
    return redirect_to("/login")

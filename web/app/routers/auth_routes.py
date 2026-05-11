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
    return render_template(request, "login.html", {"title": "Login"})


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
                "title": "Login",
                "error_message": "Invalid username or password.",
                "form_data": {"username": username},
            },
            status_code=401,
        )

    login_user(request, user)
    record_login(user, request.client.host if request.client else None)
    set_flash(request, "You have successfully signed in.")
    return redirect_to("/")


@router.get("/logout")
def logout(request: Request):
    logout_user(request)
    set_flash(request, "You have been signed out.", "info")
    return redirect_to("/login")

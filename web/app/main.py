from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from .auth import get_current_user, render_template
from .config import get_settings
from .routers import (
    audit_routes,
    auth_routes,
    customers_routes,
    dashboard_routes,
    invoices_routes,
    materials_routes,
    orders_routes,
    production_routes,
    products_routes,
    quality_routes,
    reports_routes,
    shipments_routes,
    supplier_invoices_routes,
    suppliers_routes,
    tech_cards_routes,
)


settings = get_settings()
app = FastAPI(title=settings.app_name)

template_dir = Path(__file__).resolve().parent / "templates"
static_dir = Path(__file__).resolve().parent / "static"
app.state.templates = Jinja2Templates(directory=str(template_dir))
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


PUBLIC_PATHS = {"/login", "/logout"}


@app.middleware("http")
async def require_login_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/static"):
        return await call_next(request)

    current_user = get_current_user(request)
    if path == "/login" and current_user:
        return RedirectResponse("/", status_code=303)

    if path not in PUBLIC_PATHS and not current_user:
        return RedirectResponse("/login", status_code=303)

    return await call_next(request)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie=settings.session_cookie,
    same_site="lax",
    https_only=False,
)

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return render_template(
        request,
        "error.html",
        {
            "title": "Ошибка приложения",
            "message": str(exc),
        },
        status_code=500,
    )


app.include_router(auth_routes.router)
app.include_router(dashboard_routes.router)
app.include_router(customers_routes.router)
app.include_router(suppliers_routes.router)
app.include_router(materials_routes.router)
app.include_router(products_routes.router)
app.include_router(tech_cards_routes.router)
app.include_router(orders_routes.router)
app.include_router(production_routes.router)
app.include_router(quality_routes.router)
app.include_router(invoices_routes.router)
app.include_router(supplier_invoices_routes.router)
app.include_router(shipments_routes.router)
app.include_router(reports_routes.router)
app.include_router(audit_routes.router)

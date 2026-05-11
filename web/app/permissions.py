ROLE_PRIORITY = ["admin", "technologist", "warehouse_worker", "quality_control", "client"]

ROLE_LABELS = {
    "admin": "Администратор",
    "technologist": "Технолог",
    "warehouse_worker": "Складской работник",
    "quality_control": "Сотрудник ОТК",
    "client": "Клиент",
}

SECTION_RULES = {
    "dashboard": {"admin", "technologist", "warehouse_worker", "quality_control", "client"},
    "customers": {"admin"},
    "suppliers": {"admin", "warehouse_worker"},
    "materials": {"admin", "technologist", "warehouse_worker", "quality_control"},
    "deliveries": {"admin", "warehouse_worker"},
    "material_stock": {"admin", "technologist", "warehouse_worker", "quality_control"},
    "products": {"admin", "technologist", "warehouse_worker", "quality_control", "client"},
    "tech_cards": {"admin", "technologist"},
    "orders": {"admin", "technologist", "warehouse_worker", "client"},
    "production": {"admin", "technologist"},
    "finished_stock": {"admin", "technologist", "warehouse_worker"},
    "quality": {"admin", "quality_control"},
    "invoices": {"admin", "client"},
    "shipments": {"admin", "warehouse_worker", "client"},
    "reports": {"admin", "technologist", "warehouse_worker", "quality_control"},
    "audit": {"admin"},
    "users_roles": {"admin"},
}

NAV_ITEMS = [
    {"section": "dashboard", "label": "Главная", "path": "/"},
    {"section": "customers", "label": "Клиенты", "path": "/customers"},
    {"section": "suppliers", "label": "Поставщики", "path": "/suppliers"},
    {"section": "materials", "label": "Сырьё", "path": "/materials"},
    {"section": "deliveries", "label": "Поставки", "path": "/deliveries"},
    {"section": "material_stock", "label": "Остатки сырья", "path": "/material-stock"},
    {"section": "products", "label": "Продукция", "path": "/products"},
    {"section": "tech_cards", "label": "Техкарты", "path": "/tech-cards"},
    {"section": "orders", "label": "Заказы", "path": "/orders"},
    {"section": "production", "label": "Производство", "path": "/production"},
    {"section": "finished_stock", "label": "Готовая продукция", "path": "/finished-stock"},
    {"section": "quality", "label": "Качество", "path": "/quality"},
    {"section": "invoices", "label": "Счета", "path": "/invoices"},
    {"section": "shipments", "label": "Отгрузки", "path": "/shipments"},
    {"section": "reports", "label": "Отчёты", "path": "/reports"},
    {"section": "audit", "label": "Аудит", "path": "/audit"},
    {"section": "users_roles", "label": "Пользователи и роли", "path": "/admin/users"},
]


def get_roles(user: dict | None) -> list[str]:
    if not user:
        return []
    return list(user.get("roles", []))


def get_primary_role(user: dict | None) -> str | None:
    roles = set(get_roles(user))
    for role_code in ROLE_PRIORITY:
        if role_code in roles:
            return role_code
    return None


def get_role_label(role_code: str | None) -> str:
    if not role_code:
        return "Без роли"
    return ROLE_LABELS.get(role_code, role_code)


def can_access(user: dict | None, section: str) -> bool:
    roles = set(get_roles(user))
    if "admin" in roles:
        return True
    return bool(roles & SECTION_RULES.get(section, set()))


def visible_sections(user: dict | None) -> list[dict]:
    return [item for item in NAV_ITEMS if can_access(user, item["section"])]

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

ACTION_RULES = {
    "orders.view_all": {"admin", "technologist", "warehouse_worker"},
    "orders.view_own": {"client"},
    "orders.create": {"admin", "client"},
    "orders.add_item": {"admin", "client"},
    "orders.change_status": {"admin", "technologist"},
    "orders.cancel": {"admin"},
    "invoices.view_all": {"admin"},
    "invoices.view_own": {"client"},
    "invoices.create": {"admin"},
    "invoices.change_status": {"admin"},
    "shipments.view_all": {"admin", "warehouse_worker"},
    "shipments.view_own": {"client"},
    "shipments.create": {"admin", "warehouse_worker"},
    "shipments.add_item": {"admin", "warehouse_worker"},
    "shipments.change_status": {"admin", "warehouse_worker"},
    "production.view": {"admin", "technologist"},
    "production.create": {"admin", "technologist"},
    "production.change_status": {"admin", "technologist"},
    "quality.view": {"admin", "quality_control"},
    "quality.create": {"admin", "quality_control"},
    "audit.view": {"admin"},
    "users.manage": {"admin"},
    "deliveries.view": {"admin", "warehouse_worker"},
    "deliveries.create": {"admin", "warehouse_worker"},
    "deliveries.add_item": {"admin", "warehouse_worker"},
    "deliveries.change_status": {"admin", "warehouse_worker"},
    "materials.manage": {"admin", "warehouse_worker"},
    "products.manage": {"admin"},
    "tech_cards.manage": {"admin", "technologist"},
    "tech_cards.view": {"admin", "technologist"},
    "tech_cards.change_status": {"admin", "technologist"},
    "reports.view_full": {"admin"},
    "reports.view_production": {"technologist"},
    "reports.view_warehouse": {"warehouse_worker"},
    "reports.view_quality": {"quality_control"},
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


def has_action(user: dict | None, action: str) -> bool:
    roles = set(get_roles(user))
    if "admin" in roles:
        return True
    return bool(roles & ACTION_RULES.get(action, set()))


def visible_sections(user: dict | None) -> list[dict]:
    return [item for item in NAV_ITEMS if can_access(user, item["section"])]

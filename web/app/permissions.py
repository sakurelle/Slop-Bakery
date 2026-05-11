ROLE_PRIORITY = ["admin", "technologist", "warehouse_worker", "quality_control", "client"]

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
    {"section": "dashboard", "label": "Dashboard", "path": "/"},
    {"section": "customers", "label": "Customers", "path": "/customers"},
    {"section": "suppliers", "label": "Suppliers", "path": "/suppliers"},
    {"section": "materials", "label": "Materials", "path": "/materials"},
    {"section": "deliveries", "label": "Deliveries", "path": "/deliveries"},
    {"section": "material_stock", "label": "Material Stock", "path": "/material-stock"},
    {"section": "products", "label": "Products", "path": "/products"},
    {"section": "tech_cards", "label": "Tech Cards", "path": "/tech-cards"},
    {"section": "orders", "label": "Orders", "path": "/orders"},
    {"section": "production", "label": "Production", "path": "/production"},
    {"section": "finished_stock", "label": "Finished Stock", "path": "/finished-stock"},
    {"section": "quality", "label": "Quality", "path": "/quality"},
    {"section": "invoices", "label": "Invoices", "path": "/invoices"},
    {"section": "shipments", "label": "Shipments", "path": "/shipments"},
    {"section": "reports", "label": "Reports", "path": "/reports"},
    {"section": "audit", "label": "Audit", "path": "/audit"},
    {"section": "users_roles", "label": "Users & Roles", "path": "/admin/users"},
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


def can_access(user: dict | None, section: str) -> bool:
    roles = set(get_roles(user))
    if "admin" in roles:
        return True
    return bool(roles & SECTION_RULES.get(section, set()))


def visible_sections(user: dict | None) -> list[dict]:
    return [item for item in NAV_ITEMS if can_access(user, item["section"])]

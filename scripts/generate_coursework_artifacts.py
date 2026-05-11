from __future__ import annotations

import copy
import textwrap
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
ASSETS_DIR = DOCS_DIR / "assets"
REPORT_PATH = DOCS_DIR / "БСБД_курсовая_Девяткин_Егор_ИУ8-64.docx"
PRESENTATION_PATH = DOCS_DIR / "БСБД_презентация_Девяткин_Егор_ИУ8-64.pptx"
TEMPLATE_PATH = DOCS_DIR / "Девяткин Егор ИУ8-64.docx"

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CP_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
DC_NS = "http://purl.org/dc/elements/1.1/"
DCTERMS_NS = "http://purl.org/dc/terms/"
DCMITYPE_NS = "http://purl.org/dc/dcmitype/"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"


def qn(ns: str, tag: str) -> str:
    return f"{{{ns}}}{tag}"


for prefix, uri in {
    "w": W_NS,
    "r": R_NS,
    "cp": CP_NS,
    "dc": DC_NS,
    "dcterms": DCTERMS_NS,
    "dcmitype": DCMITYPE_NS,
    "xsi": XSI_NS,
}.items():
    ET.register_namespace(prefix, uri)


@dataclass
class FigureInfo:
    number: int
    title: str
    file_name: str
    description: str


FIGURES = [
    FigureInfo(1, "Бизнес-процесс хлебозавода", "business_process.svg", "Поток поставок, производства, качества, оплаты и отгрузки."),
    FigureInfo(2, "ER-диаграмма верхнего уровня", "er_diagram.svg", "Ключевые сущности и связи защищённой базы данных."),
    FigureInfo(3, "Архитектура приложения Slop-Bakery", "architecture.svg", "Трёхуровневая схема: интерфейс, приложение, PostgreSQL."),
    FigureInfo(4, "Матрица ролей и доступа", "roles_matrix.svg", "Распределение ключевых прав между ролями."),
    FigureInfo(5, "Жизненный цикл заказа", "order_lifecycle.svg", "Допустимые переходы статусов customer_orders."),
    FigureInfo(6, "Жизненный цикл поставки", "delivery_lifecycle.svg", "Допустимые переходы статусов raw_material_deliveries."),
    FigureInfo(7, "Жизненный цикл производства", "production_lifecycle.svg", "Допустимые переходы статусов production_batches."),
    FigureInfo(8, "Жизненный цикл отгрузки", "shipment_lifecycle.svg", "Допустимые переходы статусов shipments."),
]


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def make_svg(width: int, height: int, body: str) -> str:
    return textwrap.dedent(
        f"""\
        <svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
          <rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>
          <style>
            .title {{ font: 700 22px 'Times New Roman', serif; fill: #1f1f1f; }}
            .text {{ font: 16px 'Times New Roman', serif; fill: #1f1f1f; }}
            .small {{ font: 14px 'Times New Roman', serif; fill: #1f1f1f; }}
            .box {{ fill: #f7f7f7; stroke: #404040; stroke-width: 1.4; rx: 8; ry: 8; }}
            .accent {{ fill: #ececec; stroke: #2f2f2f; stroke-width: 1.6; rx: 8; ry: 8; }}
            .line {{ stroke: #4d4d4d; stroke-width: 2; marker-end: url(#arrow); fill: none; }}
            .dashed {{ stroke-dasharray: 6 4; }}
          </style>
          <defs>
            <marker id="arrow" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto">
              <path d="M0,0 L12,6 L0,12 z" fill="#4d4d4d"/>
            </marker>
          </defs>
          {body}
        </svg>
        """
    )


def generate_assets() -> list[Path]:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []

    business_process = make_svg(
        1500,
        360,
        """
        <text x="750" y="40" text-anchor="middle" class="title">Бизнес-процесс автоматизированной системы хлебозавода</text>
        <rect x="40" y="120" width="130" height="70" class="accent"/>
        <rect x="210" y="120" width="130" height="70" class="box"/>
        <rect x="380" y="120" width="160" height="70" class="box"/>
        <rect x="580" y="120" width="150" height="70" class="box"/>
        <rect x="770" y="120" width="130" height="70" class="box"/>
        <rect x="940" y="120" width="130" height="70" class="box"/>
        <rect x="1110" y="120" width="130" height="70" class="box"/>
        <rect x="1280" y="120" width="150" height="70" class="accent"/>
        <text x="105" y="160" text-anchor="middle" class="text">Поставщики</text>
        <text x="275" y="160" text-anchor="middle" class="text">Сырьё</text>
        <text x="460" y="153" text-anchor="middle" class="text">Поставка</text>
        <text x="460" y="175" text-anchor="middle" class="small">и счёт поставщика</text>
        <text x="655" y="153" text-anchor="middle" class="text">Контроль</text>
        <text x="655" y="175" text-anchor="middle" class="small">качества сырья</text>
        <text x="835" y="160" text-anchor="middle" class="text">Производство</text>
        <text x="1005" y="160" text-anchor="middle" class="text">Склад ГП</text>
        <text x="1175" y="153" text-anchor="middle" class="text">Заказ, счёт</text>
        <text x="1175" y="175" text-anchor="middle" class="small">и оплата клиента</text>
        <text x="1355" y="153" text-anchor="middle" class="text">Отгрузка</text>
        <text x="1355" y="175" text-anchor="middle" class="small">и аудит действий</text>
        <path d="M170 155 H205" class="line"/>
        <path d="M340 155 H375" class="line"/>
        <path d="M540 155 H575" class="line"/>
        <path d="M730 155 H765" class="line"/>
        <path d="M900 155 H935" class="line"/>
        <path d="M1070 155 H1105" class="line"/>
        <path d="M1240 155 H1275" class="line"/>
        <text x="750" y="270" text-anchor="middle" class="small">Информационная система фиксирует движение сырья и продукции, контролирует статусы документов,</text>
        <text x="750" y="292" text-anchor="middle" class="small">обеспечивает ролевое разграничение доступа и формирует журнал аудита по бизнес-операциям.</text>
        """,
    )
    path = ASSETS_DIR / "business_process.svg"
    write_text(path, business_process)
    generated.append(path)

    er_diagram = make_svg(
        1600,
        980,
        """
        <text x="800" y="40" text-anchor="middle" class="title">ER-диаграмма верхнего уровня Slop-Bakery</text>
        <rect x="60" y="110" width="190" height="80" class="accent"/>
        <rect x="300" y="110" width="190" height="80" class="box"/>
        <rect x="540" y="110" width="220" height="80" class="accent"/>
        <rect x="820" y="110" width="220" height="80" class="box"/>
        <rect x="1100" y="110" width="190" height="80" class="box"/>
        <rect x="1340" y="110" width="190" height="80" class="accent"/>
        <text x="155" y="145" text-anchor="middle" class="text">customers</text>
        <text x="155" y="168" text-anchor="middle" class="small">users(client)</text>
        <text x="395" y="145" text-anchor="middle" class="text">customer_orders</text>
        <text x="395" y="168" text-anchor="middle" class="small">order_items</text>
        <text x="650" y="145" text-anchor="middle" class="text">invoices</text>
        <text x="650" y="168" text-anchor="middle" class="small">shipments / shipment_items</text>
        <text x="930" y="145" text-anchor="middle" class="text">products</text>
        <text x="930" y="168" text-anchor="middle" class="small">finished_goods_stock</text>
        <text x="1195" y="145" text-anchor="middle" class="text">tech_cards</text>
        <text x="1195" y="168" text-anchor="middle" class="small">recipe_items</text>
        <text x="1435" y="145" text-anchor="middle" class="text">production_batches</text>
        <text x="1435" y="168" text-anchor="middle" class="small">quality_checks</text>
        <path d="M250 150 H295" class="line"/>
        <path d="M490 150 H535" class="line"/>
        <path d="M760 150 H815" class="line"/>
        <path d="M1040 150 H1095" class="line"/>
        <path d="M1290 150 H1335" class="line"/>

        <rect x="90" y="360" width="210" height="90" class="accent"/>
        <rect x="360" y="360" width="230" height="90" class="box"/>
        <rect x="660" y="360" width="220" height="90" class="accent"/>
        <rect x="950" y="360" width="220" height="90" class="box"/>
        <rect x="1240" y="360" width="260" height="90" class="accent"/>
        <text x="195" y="395" text-anchor="middle" class="text">suppliers</text>
        <text x="195" y="418" text-anchor="middle" class="small">supplier_materials</text>
        <text x="475" y="395" text-anchor="middle" class="text">raw_materials</text>
        <text x="475" y="418" text-anchor="middle" class="small">min stock / unit / shelf life</text>
        <text x="770" y="395" text-anchor="middle" class="text">raw_material_deliveries</text>
        <text x="770" y="418" text-anchor="middle" class="small">delivery_items</text>
        <text x="1060" y="395" text-anchor="middle" class="text">supplier_invoices</text>
        <text x="1060" y="418" text-anchor="middle" class="small">invoice_statuses</text>
        <text x="1370" y="395" text-anchor="middle" class="text">raw_material_stock</text>
        <text x="1370" y="418" text-anchor="middle" class="small">batches / expiry / quantities</text>
        <path d="M300 405 H355" class="line"/>
        <path d="M590 405 H655" class="line"/>
        <path d="M880 405 H945" class="line"/>
        <path d="M1170 405 H1235" class="line"/>

        <rect x="210" y="640" width="260" height="95" class="box"/>
        <rect x="520" y="640" width="260" height="95" class="box"/>
        <rect x="830" y="640" width="260" height="95" class="box"/>
        <rect x="1140" y="640" width="260" height="95" class="box"/>
        <text x="340" y="675" text-anchor="middle" class="text">users</text>
        <text x="340" y="698" text-anchor="middle" class="small">roles / user_roles / role_permissions</text>
        <text x="650" y="675" text-anchor="middle" class="text">audit_log</text>
        <text x="650" y="698" text-anchor="middle" class="small">JSONB old_data / new_data</text>
        <text x="960" y="675" text-anchor="middle" class="text">status dictionaries</text>
        <text x="960" y="698" text-anchor="middle" class="small">order / invoice / delivery / ...</text>
        <text x="1270" y="675" text-anchor="middle" class="text">web modules</text>
        <text x="1270" y="698" text-anchor="middle" class="small">auth / reports / dashboards</text>
        <path d="M470 688 H515" class="line"/>
        <path d="M780 688 H825" class="line"/>
        <path d="M1090 688 H1135" class="line"/>

        <path d="M650 190 V250 H1370 V355" class="line dashed"/>
        <path d="M475 450 V560 H650 V635" class="line dashed"/>
        <path d="M930 190 V250 H930 V355" class="line dashed"/>
        <path d="M1370 450 V560 H930 V635" class="line dashed"/>
        <text x="800" y="890" text-anchor="middle" class="small">Диаграмма отражает два основных контура: клиентский контур заказов и поставочный контур сырья,</text>
        <text x="800" y="912" text-anchor="middle" class="small">которые соединяются через производство, контроль качества, склад готовой продукции и модуль аудита.</text>
        """,
    )
    path = ASSETS_DIR / "er_diagram.svg"
    write_text(path, er_diagram)
    generated.append(path)

    architecture = make_svg(
        1400,
        620,
        """
        <text x="700" y="42" text-anchor="middle" class="title">Архитектура приложения Slop-Bakery</text>
        <rect x="120" y="120" width="1160" height="110" class="accent"/>
        <rect x="120" y="270" width="1160" height="130" class="box"/>
        <rect x="120" y="440" width="1160" height="110" class="accent"/>
        <text x="700" y="162" text-anchor="middle" class="text">Уровень представления</text>
        <text x="700" y="190" text-anchor="middle" class="small">HTML / Jinja2, серверный рендеринг, формы входа, dashboard, списки, карточки, отчёты, печатная форма shipment</text>
        <text x="700" y="315" text-anchor="middle" class="text">Уровень приложения</text>
        <text x="700" y="343" text-anchor="middle" class="small">FastAPI, маршруты, авторизация, session middleware, action-level permissions, серверная валидация,</text>
        <text x="700" y="366" text-anchor="middle" class="small">проверка матриц статусов, бизнес-операции оплаты, производства, поставок, отгрузок и аудита</text>
        <text x="700" y="482" text-anchor="middle" class="text">Уровень хранения данных</text>
        <text x="700" y="510" text-anchor="middle" class="small">PostgreSQL 16, ограничения целостности, SQL-роли, индексы, триггерный аудит JSONB, seed и checks</text>
        <path d="M700 230 V265" class="line"/>
        <path d="M700 400 V435" class="line"/>
        """,
    )
    path = ASSETS_DIR / "architecture.svg"
    write_text(path, architecture)
    generated.append(path)

    roles_matrix = make_svg(
        1600,
        620,
        """
        <text x="800" y="40" text-anchor="middle" class="title">Матрица ролей и ключевых прав</text>
        <rect x="40" y="90" width="240" height="60" class="accent"/>
        <rect x="280" y="90" width="220" height="60" class="accent"/>
        <rect x="500" y="90" width="220" height="60" class="accent"/>
        <rect x="720" y="90" width="220" height="60" class="accent"/>
        <rect x="940" y="90" width="220" height="60" class="accent"/>
        <rect x="1160" y="90" width="400" height="60" class="accent"/>
        <text x="160" y="128" text-anchor="middle" class="text">Роль</text>
        <text x="390" y="128" text-anchor="middle" class="text">Разделы</text>
        <text x="610" y="128" text-anchor="middle" class="text">Разрешено</text>
        <text x="830" y="128" text-anchor="middle" class="text">Запрещено</text>
        <text x="1050" y="128" text-anchor="middle" class="text">Финансы</text>
        <text x="1360" y="128" text-anchor="middle" class="text">Особенности</text>
        <rect x="40" y="150" width="240" height="82" class="box"/>
        <rect x="280" y="150" width="220" height="82" class="box"/>
        <rect x="500" y="150" width="220" height="82" class="box"/>
        <rect x="720" y="150" width="220" height="82" class="box"/>
        <rect x="940" y="150" width="220" height="82" class="box"/>
        <rect x="1160" y="150" width="400" height="82" class="box"/>
        <text x="160" y="180" text-anchor="middle" class="text">admin</text>
        <text x="390" y="186" text-anchor="middle" class="small">Все</text>
        <text x="610" y="176" text-anchor="middle" class="small">Статусы, счета,</text>
        <text x="610" y="196" text-anchor="middle" class="small">аудит, пользователи</text>
        <text x="830" y="186" text-anchor="middle" class="small">—</text>
        <text x="1050" y="186" text-anchor="middle" class="small">Полный</text>
        <text x="1360" y="176" text-anchor="middle" class="small">Единственный доступ</text>
        <text x="1360" y="196" text-anchor="middle" class="small">к audit и users/roles</text>
        <rect x="40" y="232" width="240" height="82" class="box"/>
        <rect x="280" y="232" width="220" height="82" class="box"/>
        <rect x="500" y="232" width="220" height="82" class="box"/>
        <rect x="720" y="232" width="220" height="82" class="box"/>
        <rect x="940" y="232" width="220" height="82" class="box"/>
        <rect x="1160" y="232" width="400" height="82" class="box"/>
        <text x="160" y="262" text-anchor="middle" class="text">client</text>
        <text x="390" y="258" text-anchor="middle" class="small">dashboard, products,</text>
        <text x="390" y="278" text-anchor="middle" class="small">orders, invoices, shipments</text>
        <text x="610" y="258" text-anchor="middle" class="small">Создание заказа,</text>
        <text x="610" y="278" text-anchor="middle" class="small">оплата своего счёта</text>
        <text x="830" y="258" text-anchor="middle" class="small">audit, reports,</text>
        <text x="830" y="278" text-anchor="middle" class="small">tech cards</text>
        <text x="1050" y="268" text-anchor="middle" class="small">Только свои</text>
        <text x="1360" y="258" text-anchor="middle" class="small">Не задаёт цену и статус</text>
        <text x="1360" y="278" text-anchor="middle" class="small">заказа</text>
        <rect x="40" y="314" width="240" height="82" class="box"/>
        <rect x="280" y="314" width="220" height="82" class="box"/>
        <rect x="500" y="314" width="220" height="82" class="box"/>
        <rect x="720" y="314" width="220" height="82" class="box"/>
        <rect x="940" y="314" width="220" height="82" class="box"/>
        <rect x="1160" y="314" width="400" height="82" class="box"/>
        <text x="160" y="344" text-anchor="middle" class="text">technologist</text>
        <text x="390" y="340" text-anchor="middle" class="small">products, tech cards,</text>
        <text x="390" y="360" text-anchor="middle" class="small">orders, production</text>
        <text x="610" y="340" text-anchor="middle" class="small">Техкарты, recipe,</text>
        <text x="610" y="360" text-anchor="middle" class="small">production</text>
        <text x="830" y="340" text-anchor="middle" class="small">shipment, payment,</text>
        <text x="830" y="360" text-anchor="middle" class="small">audit</text>
        <text x="1050" y="350" text-anchor="middle" class="small">Нет</text>
        <text x="1360" y="340" text-anchor="middle" class="small">Ответственный за production</text>
        <text x="1360" y="360" text-anchor="middle" class="small">должен быть технологом</text>
        <rect x="40" y="396" width="240" height="82" class="box"/>
        <rect x="280" y="396" width="220" height="82" class="box"/>
        <rect x="500" y="396" width="220" height="82" class="box"/>
        <rect x="720" y="396" width="220" height="82" class="box"/>
        <rect x="940" y="396" width="220" height="82" class="box"/>
        <rect x="1160" y="396" width="400" height="82" class="box"/>
        <text x="160" y="426" text-anchor="middle" class="text">warehouse_worker</text>
        <text x="390" y="422" text-anchor="middle" class="small">suppliers, materials,</text>
        <text x="390" y="442" text-anchor="middle" class="small">deliveries, shipments</text>
        <text x="610" y="422" text-anchor="middle" class="small">Поставки, склад,</text>
        <text x="610" y="442" text-anchor="middle" class="small">shipment</text>
        <text x="830" y="422" text-anchor="middle" class="small">audit, users,</text>
        <text x="830" y="442" text-anchor="middle" class="small">invoice pay</text>
        <text x="1050" y="432" text-anchor="middle" class="small">Supplier invoice</text>
        <text x="1050" y="452" text-anchor="middle" class="small">только просмотр</text>
        <text x="1360" y="422" text-anchor="middle" class="small">Без изменения цен</text>
        <text x="1360" y="442" text-anchor="middle" class="small">клиентского заказа</text>
        <rect x="40" y="478" width="240" height="82" class="box"/>
        <rect x="280" y="478" width="220" height="82" class="box"/>
        <rect x="500" y="478" width="220" height="82" class="box"/>
        <rect x="720" y="478" width="220" height="82" class="box"/>
        <rect x="940" y="478" width="220" height="82" class="box"/>
        <rect x="1160" y="478" width="400" height="82" class="box"/>
        <text x="160" y="508" text-anchor="middle" class="text">quality_control</text>
        <text x="390" y="504" text-anchor="middle" class="small">materials, quality,</text>
        <text x="390" y="524" text-anchor="middle" class="small">quality reports</text>
        <text x="610" y="504" text-anchor="middle" class="small">quality checks</text>
        <text x="830" y="504" text-anchor="middle" class="small">orders, invoices,</text>
        <text x="830" y="524" text-anchor="middle" class="small">shipments, audit</text>
        <text x="1050" y="514" text-anchor="middle" class="small">Нет</text>
        <text x="1360" y="504" text-anchor="middle" class="small">Инспектор должен</text>
        <text x="1360" y="524" text-anchor="middle" class="small">иметь роль ОТК</text>
        """,
    )
    path = ASSETS_DIR / "roles_matrix.svg"
    write_text(path, roles_matrix)
    generated.append(path)

    def lifecycle_svg(title: str, file_name: str, states: list[str], allowed: list[tuple[int, int]]) -> Path:
        width = 1450
        height = 300
        box_w = 160
        gap = 35
        start_x = 50
        body = [f'<text x="{width // 2}" y="40" text-anchor="middle" class="title">{title}</text>']
        y = 120
        centers = []
        for idx, state in enumerate(states):
            x = start_x + idx * (box_w + gap)
            klass = "accent" if idx == 0 else "box"
            body.append(f'<rect x="{x}" y="{y}" width="{box_w}" height="72" class="{klass}"/>')
            body.append(f'<text x="{x + box_w / 2}" y="{y + 40}" text-anchor="middle" class="text">{state}</text>')
            centers.append((x, y))
        for src, dst in allowed:
            x1 = centers[src][0] + box_w
            y1 = centers[src][1] + 36
            x2 = centers[dst][0]
            body.append(f'<path d="M{x1} {y1} H{x2 - 8}" class="line"/>')
        body.append('<text x="725" y="250" text-anchor="middle" class="small">Допустимые переходы реализованы на сервере и проверяются до изменения статуса объекта.</text>')
        path = ASSETS_DIR / file_name
        write_text(path, make_svg(width, height, "\\n".join(body)))
        return path

    generated.append(lifecycle_svg("Жизненный цикл заказа", "order_lifecycle.svg", ["draft", "confirmed", "in_production", "ready", "shipped", "completed", "cancelled"], [(0, 1), (0, 6), (1, 2), (1, 6), (2, 3), (3, 4), (4, 5)]))
    generated.append(lifecycle_svg("Жизненный цикл поставки", "delivery_lifecycle.svg", ["planned", "received", "accepted", "rejected", "cancelled"], [(0, 1), (0, 4), (1, 2), (1, 3)]))
    generated.append(lifecycle_svg("Жизненный цикл производства", "production_lifecycle.svg", ["planned", "in_progress", "completed", "cancelled"], [(0, 1), (0, 3), (1, 2), (1, 3)]))
    generated.append(lifecycle_svg("Жизненный цикл отгрузки", "shipment_lifecycle.svg", ["planned", "shipped", "delivered", "cancelled"], [(0, 1), (0, 3), (1, 2)]))
    return generated


def parse_template_sectpr() -> ET.Element:
    with zipfile.ZipFile(TEMPLATE_PATH) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))
    sect = root.find(f".//{qn(W_NS, 'sectPr')}")
    if sect is None:
        raise RuntimeError("В шаблоне не найден sectPr.")
    return copy.deepcopy(sect)


def paragraph(
    parent: ET.Element,
    text: str = "",
    *,
    style: str | None = "TNR1415",
    align: str | None = None,
    bold: bool = False,
    italic: bool = False,
    size: int | None = None,
    spacing_before: int | None = None,
    spacing_after: int | None = None,
    page_break_before: bool = False,
) -> ET.Element:
    p = ET.SubElement(parent, qn(W_NS, "p"))
    ppr = ET.SubElement(p, qn(W_NS, "pPr"))
    if style:
        ps = ET.SubElement(ppr, qn(W_NS, "pStyle"))
        ps.set(qn(W_NS, "val"), style)
    if align:
        jc = ET.SubElement(ppr, qn(W_NS, "jc"))
        jc.set(qn(W_NS, "val"), align)
    if page_break_before:
        pbb = ET.SubElement(ppr, qn(W_NS, "pageBreakBefore"))
        pbb.set(qn(W_NS, "val"), "1")
    if spacing_before is not None or spacing_after is not None:
        sp = ET.SubElement(ppr, qn(W_NS, "spacing"))
        if spacing_before is not None:
            sp.set(qn(W_NS, "before"), str(spacing_before))
        if spacing_after is not None:
            sp.set(qn(W_NS, "after"), str(spacing_after))
    r = ET.SubElement(p, qn(W_NS, "r"))
    rpr = ET.SubElement(r, qn(W_NS, "rPr"))
    if bold:
        ET.SubElement(rpr, qn(W_NS, "b"))
    if italic:
        ET.SubElement(rpr, qn(W_NS, "i"))
    if size:
        sz = ET.SubElement(rpr, qn(W_NS, "sz"))
        sz.set(qn(W_NS, "val"), str(size))
        sz_cs = ET.SubElement(rpr, qn(W_NS, "szCs"))
        sz_cs.set(qn(W_NS, "val"), str(size))
    t = ET.SubElement(r, qn(W_NS, "t"))
    if text.startswith(" ") or text.endswith(" ") or "  " in text:
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = text
    return p


def code_paragraph(parent: ET.Element, text: str) -> ET.Element:
    p = ET.SubElement(parent, qn(W_NS, "p"))
    ppr = ET.SubElement(p, qn(W_NS, "pPr"))
    ps = ET.SubElement(ppr, qn(W_NS, "pStyle"))
    ps.set(qn(W_NS, "val"), "TNR1415")
    sp = ET.SubElement(ppr, qn(W_NS, "spacing"))
    sp.set(qn(W_NS, "before"), "0")
    sp.set(qn(W_NS, "after"), "0")
    r = ET.SubElement(p, qn(W_NS, "r"))
    rpr = ET.SubElement(r, qn(W_NS, "rPr"))
    fonts = ET.SubElement(rpr, qn(W_NS, "rFonts"))
    fonts.set(qn(W_NS, "ascii"), "Courier New")
    fonts.set(qn(W_NS, "hAnsi"), "Courier New")
    fonts.set(qn(W_NS, "cs"), "Courier New")
    sz = ET.SubElement(rpr, qn(W_NS, "sz"))
    sz.set(qn(W_NS, "val"), "22")
    sz_cs = ET.SubElement(rpr, qn(W_NS, "szCs"))
    sz_cs.set(qn(W_NS, "val"), "22")
    t = ET.SubElement(r, qn(W_NS, "t"))
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = text
    return p


def page_break(parent: ET.Element) -> None:
    p = ET.SubElement(parent, qn(W_NS, "p"))
    r = ET.SubElement(p, qn(W_NS, "r"))
    br = ET.SubElement(r, qn(W_NS, "br"))
    br.set(qn(W_NS, "type"), "page")


def heading(parent: ET.Element, level: int, text: str) -> None:
    style = {1: "Heading1", 2: "Heading2", 3: "Heading3"}.get(level, "Heading4")
    paragraph(parent, text, style=style, spacing_before=120, spacing_after=120)


def add_text_block(parent: ET.Element, block: str) -> None:
    for part in [p.strip() for p in block.strip().split("\n\n") if p.strip()]:
        paragraph(parent, part)


def bullet_list(parent: ET.Element, items: list[str]) -> None:
    for item in items:
        paragraph(parent, f"– {item}", style="ListParagraph")


def add_table(parent: ET.Element, title: str, headers: list[str], rows: list[list[str]]) -> None:
    paragraph(parent, title, style="Caption", align="center")
    tbl = ET.SubElement(parent, qn(W_NS, "tbl"))
    tbl_pr = ET.SubElement(tbl, qn(W_NS, "tblPr"))
    tbl_style = ET.SubElement(tbl_pr, qn(W_NS, "tblStyle"))
    tbl_style.set(qn(W_NS, "val"), "TableGrid")
    tbl_w = ET.SubElement(tbl_pr, qn(W_NS, "tblW"))
    tbl_w.set(qn(W_NS, "w"), "0")
    tbl_w.set(qn(W_NS, "type"), "auto")
    tbl_grid = ET.SubElement(tbl, qn(W_NS, "tblGrid"))
    width = max(1800, int(9000 / max(1, len(headers))))
    for _ in headers:
        gc = ET.SubElement(tbl_grid, qn(W_NS, "gridCol"))
        gc.set(qn(W_NS, "w"), str(width))

    def add_row(values: list[str], is_header: bool = False) -> None:
        tr = ET.SubElement(tbl, qn(W_NS, "tr"))
        for value in values:
            tc = ET.SubElement(tr, qn(W_NS, "tc"))
            tc_pr = ET.SubElement(tc, qn(W_NS, "tcPr"))
            tc_w = ET.SubElement(tc_pr, qn(W_NS, "tcW"))
            tc_w.set(qn(W_NS, "w"), str(width))
            tc_w.set(qn(W_NS, "type"), "dxa")
            p = ET.SubElement(tc, qn(W_NS, "p"))
            ppr = ET.SubElement(p, qn(W_NS, "pPr"))
            ps = ET.SubElement(ppr, qn(W_NS, "pStyle"))
            ps.set(qn(W_NS, "val"), "TNR1415")
            r = ET.SubElement(p, qn(W_NS, "r"))
            rpr = ET.SubElement(r, qn(W_NS, "rPr"))
            if is_header:
                ET.SubElement(rpr, qn(W_NS, "b"))
            t = ET.SubElement(r, qn(W_NS, "t"))
            t.text = value

    add_row(headers, True)
    for row in rows:
        add_row(row)


def add_figure_placeholder(parent: ET.Element, fig: FigureInfo) -> None:
    paragraph(parent, f"На рисунке {fig.number} представлена {fig.title.lower()}.")
    tbl = ET.SubElement(parent, qn(W_NS, "tbl"))
    tbl_pr = ET.SubElement(tbl, qn(W_NS, "tblPr"))
    tbl_style = ET.SubElement(tbl_pr, qn(W_NS, "tblStyle"))
    tbl_style.set(qn(W_NS, "val"), "TableGrid")
    tbl_grid = ET.SubElement(tbl, qn(W_NS, "tblGrid"))
    gc = ET.SubElement(tbl_grid, qn(W_NS, "gridCol"))
    gc.set(qn(W_NS, "w"), "9000")
    tr = ET.SubElement(tbl, qn(W_NS, "tr"))
    tc = ET.SubElement(tr, qn(W_NS, "tc"))
    tc_pr = ET.SubElement(tc, qn(W_NS, "tcPr"))
    tc_w = ET.SubElement(tc_pr, qn(W_NS, "tcW"))
    tc_w.set(qn(W_NS, "w"), "9000")
    tc_w.set(qn(W_NS, "type"), "dxa")
    paragraph(tc, f"[Диаграмма сохранена во внешнем файле: docs/assets/{fig.file_name}]", align="center", bold=True)
    paragraph(tc, fig.description, align="center")
    paragraph(parent, f"Рисунок {fig.number} — {fig.title}", style="Caption", align="center")


def add_toc(parent: ET.Element) -> None:
    heading(parent, 1, "СОДЕРЖАНИЕ")
    p = ET.SubElement(parent, qn(W_NS, "p"))
    r1 = ET.SubElement(p, qn(W_NS, "r"))
    fld_begin = ET.SubElement(r1, qn(W_NS, "fldChar"))
    fld_begin.set(qn(W_NS, "fldCharType"), "begin")
    r2 = ET.SubElement(p, qn(W_NS, "r"))
    instr = ET.SubElement(r2, qn(W_NS, "instrText"))
    instr.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    instr.text = ' TOC \\o "1-3" \\h \\z \\u '
    r3 = ET.SubElement(p, qn(W_NS, "r"))
    fld_sep = ET.SubElement(r3, qn(W_NS, "fldChar"))
    fld_sep.set(qn(W_NS, "fldCharType"), "separate")
    r4 = ET.SubElement(p, qn(W_NS, "r"))
    t = ET.SubElement(r4, qn(W_NS, "t"))
    t.text = "Содержание будет обновлено при открытии документа в Microsoft Word."
    r5 = ET.SubElement(p, qn(W_NS, "r"))
    fld_end = ET.SubElement(r5, qn(W_NS, "fldChar"))
    fld_end.set(qn(W_NS, "fldCharType"), "end")


def build_report_document_xml() -> bytes:
    sect_pr = parse_template_sectpr()
    root = ET.Element(qn(W_NS, "document"))
    body = ET.SubElement(root, qn(W_NS, "body"))

    paragraph(body, "Министерство науки и высшего образования Российской Федерации", align="center", size=26)
    paragraph(body, "Федеральное государственное бюджетное образовательное учреждение", align="center", size=24)
    paragraph(body, "высшего образования", align="center", size=24)
    paragraph(body, "«Московский государственный технический университет", align="center", size=24)
    paragraph(body, "имени Н.Э. Баумана", align="center", size=24)
    paragraph(body, "(национальный исследовательский университет)»", align="center", size=24)
    paragraph(body, "(МГТУ им. Н.Э. Баумана)", align="center", size=24)
    paragraph(body, "", spacing_after=240)
    paragraph(body, "Факультет «Информатика и системы управления» (ИУ)", align="center", size=24)
    paragraph(body, "Кафедра «Информационная безопасность» (ИУ8)", align="center", size=24)
    paragraph(body, "", spacing_after=360)
    paragraph(body, "РАСЧЁТНО-ПОЯСНИТЕЛЬНАЯ ЗАПИСКА", align="center", bold=True, size=30)
    paragraph(body, "к курсовой работе по дисциплине «Безопасность систем баз данных»", align="center", bold=True, size=26)
    paragraph(body, "", spacing_after=240)
    paragraph(body, "на тему:", align="center", size=24)
    paragraph(body, "«Разработка и защита системы базы данных хлебозавода»", align="center", bold=True, size=28)
    paragraph(body, "", spacing_after=360)
    paragraph(body, "Система: Slop-Bakery", align="center", size=24)
    paragraph(body, "", spacing_after=480)
    paragraph(body, "Преподаватель: Боровик И.Г. ____________________", align="left", size=24)
    paragraph(body, "Студент: Девяткин Егор, группа ИУ8-64 ____________________", align="left", size=24)
    paragraph(body, "", spacing_after=720)
    paragraph(body, "Москва 2026", align="center", size=24)
    page_break(body)

    heading(body, 1, "ЗАДАНИЕ НА КУРСОВУЮ РАБОТУ")
    add_text_block(
        body,
        """
        В рамках курсовой работы требуется разработать защищённую систему базы данных хлебозавода Slop-Bakery, предназначенную для автоматизации процессов работы с клиентами, поставщиками, сырьём, производством, контролем качества, складским учётом и отгрузками.

        В составе работы необходимо реализовать реляционную базу данных PostgreSQL, серверное приложение на FastAPI, веб-интерфейс на основе Jinja2/HTML, ролевое разграничение доступа пользователей, аудит действий, средства обеспечения целостности данных, набор отчётов и сценарии проверки защищённости.

        В ходе выполнения работы подлежат решению следующие задачи: анализ предметной области хлебозавода; построение инфологической, логической и физической моделей; реализация ограничений целостности; разработка прикладной бизнес-логики; исследование защищённости системы при типовых негативных сценариях; подготовка документации и материалов для защиты.
        """,
    )
    page_break(body)

    add_toc(body)
    page_break(body)

    heading(body, 1, "ВВЕДЕНИЕ")
    add_text_block(
        body,
        """
        В современных автоматизированных системах данные являются ключевым производственным ресурсом, а обеспечение их конфиденциальности, целостности и доступности рассматривается как необходимое условие устойчивой работы предприятия. Особенно высока значимость этих свойств в системах, обслуживающих финансовые документы, технологические процессы, складской учёт и действия пользователей с различным уровнем полномочий.

        Для хлебозавода информационная система должна поддерживать полный цикл движения сырья и продукции: закупку, контроль качества, производство, хранение, реализацию и отчётность. Ошибки в таких процессах приводят не только к экономическим потерям, но и к нарушению обязательств перед клиентами, искажению документов, некорректному использованию сырья, а также к рискам выпуска и отгрузки продукции без требуемых проверок.

        Целью работы является разработка и защита системы базы данных хлебозавода Slop-Bakery, обеспечивающей безопасное хранение данных, ролевое разграничение доступа, контроль бизнес-операций и возможность демонстрации работы системы через веб-интерфейс.

        Для достижения поставленной цели решаются задачи анализа предметной области, проектирования сущностей и связей, выбора технологического стека, реализации PostgreSQL-схемы, построения прикладного уровня на FastAPI, настройки ограничений целостности, разграничения прав, аудита и набора прикладных отчётов.

        Объектом автоматизации является деятельность хлебозавода, связанная с учётом клиентов, поставщиков, сырья, технологических карт, производственных партий, контроля качества, готовой продукции, счетов и отгрузок. Предметом исследования выступают методы проектирования и защиты реляционной базы данных, а также способы серверного контроля бизнес-правил при наличии нескольких ролей пользователей.

        В работе используются методы анализа предметной области, нормализации данных, ролевого моделирования доступа, проектирования ограничений целостности, прикладной серверной валидации и тестирования негативных сценариев.
        """,
    )

    heading(body, 1, "1 АНАЛИЗ ПРЕДМЕТНОЙ ОБЛАСТИ")
    add_text_block(
        body,
        """
        Хлебозавод представляет собой предприятие пищевой промышленности, для которого характерны непрерывные материальные потоки, документарное сопровождение поставок, технологическая регламентация производства и строгие требования к качеству сырья и готовой продукции. В рамках проектируемой системы автоматизации требуется обеспечить согласованную работу подразделений снабжения, производства, склада, службы качества, администратора и клиентов.

        Основными объектами управления являются клиенты и их заказы, поставщики и закреплённые за ними виды сырья, поставки сырья и счета поставщиков, технологические карты изделий, производственные партии, результаты контроля качества, складские партии сырья и готовой продукции, клиентские счета, отгрузки, роли пользователей и журнал аудита.
        """,
    )
    heading(body, 2, "1.1 Бизнес-процессы хлебозавода")
    bullet_list(
        body,
        [
            "работа с клиентами, включая хранение контактных данных и адресов доставки;",
            "оформление заказов клиентов и их состава через отдельные позиции заказа;",
            "выставление счетов клиентам, оплата счетов и контроль статусов оплаты;",
            "закупка сырья у поставщиков и ведение связей supplier_materials с фиксированием закупочных цен;",
            "поступление поставок сырья, их приёмка, создание счёта поставщика и пополнение складских остатков только после корректного статуса поставки;",
            "контроль качества сырья до допуска к производству;",
            "формирование и сопровождение технологических карт и рецептур продукции;",
            "создание производственных партий, проверка доступности сырья и списание сырья при завершении производства;",
            "контроль качества готовой продукции и допуск партий к отгрузке только при положительном результате проверки;",
            "ведение склада готовой продукции с учётом сроков годности и партийного учёта;",
            "формирование отгрузок, списание складских остатков и контроль оплаты клиентского счёта перед отгрузкой;",
            "формирование отчётов для различных ролей и ведение журнала аудита действий пользователей.",
        ],
    )
    add_figure_placeholder(body, FIGURES[0])

    heading(body, 2, "1.2 Роли пользователей и разграничение доступа")
    add_text_block(
        body,
        """
        В приложении реализовано пять логических ролей: admin, client, technologist, warehouse_worker и quality_control. Для каждой роли определён набор видимых разделов интерфейса и набор точечных action-level permissions, проверяемых на сервере в роутерах FastAPI. Такой подход исключает ситуацию, при которой скрытие кнопки в интерфейсе можно обойти прямым URL или подменой POST-запроса.
        """,
    )
    add_table(
        body,
        "Таблица 1 — Назначение логических ролей",
        ["Роль", "Назначение", "Доступные разделы", "Разрешённые действия", "Запрещённые действия"],
        [
            ["admin", "Администрирование системы", "Все модули", "Управление статусами, пользователями, аудитом, счетами, отгрузками и отчётами", "Отсутствуют функциональные ограничения внутри системы"],
            ["client", "Оформление и отслеживание собственных заказов", "Личный dashboard, products, orders, invoices, shipments", "Создание заказа, добавление позиций в draft, оплата своего счёта", "Просмотр аудита, техкарт, внутренних отчётов, изменение цены и статуса заказа"],
            ["technologist", "Ведение технологических карт и производства", "Products, tech cards, orders, production, reports", "Изменение техкарт, запуск и завершение производств, перевод заказа в in_production", "Оплата счетов, создание отгрузок, аудит"],
            ["warehouse_worker", "Поставки, складской учёт и отгрузки", "Suppliers, materials, deliveries, material stock, finished stock, shipments, supplier invoices", "Создание поставок и отгрузок, работа с supplier_materials, просмотр счетов поставщиков", "Оплата supplier invoices, просмотр аудита, изменение клиентских цен"],
            ["quality_control", "Контроль качества", "Materials, quality, reports", "Создание quality checks и просмотр специализированных отчётов", "Изменение заказов, счетов, отгрузок, аудита и финансовых данных"],
        ],
    )
    add_figure_placeholder(body, FIGURES[3])
    add_table(
        body,
        "Таблица 2 — Матрица доступа к основным разделам",
        ["Раздел", "admin", "client", "technologist", "warehouse_worker", "quality_control"],
        [
            ["Клиенты", "П", "–", "–", "–", "–"],
            ["Поставщики", "П/И/Р", "–", "–", "П/И/Р", "–"],
            ["Сырьё", "П/И/Р", "–", "П", "П/И/Р", "П"],
            ["Поставки", "П/И/Р", "–", "–", "П/И/Р", "–"],
            ["Склад сырья", "П", "–", "П", "П", "П"],
            ["Продукция", "П/И/Р", "П", "П", "П", "П"],
            ["Техкарты", "П/И/Р", "–", "П/И/Р", "–", "–"],
            ["Заказы", "П/И/Р/С", "Только свои", "П/С", "П", "–"],
            ["Производство", "П/И/С", "–", "П/И/С", "–", "–"],
            ["Контроль качества", "П/И", "–", "–", "–", "П/И"],
            ["Склад ГП", "П", "–", "П", "П", "–"],
            ["Счета клиентам", "П/И/С", "Только свои/оплата", "–", "–", "–"],
            ["Счета поставщиков", "П/С", "–", "–", "П", "–"],
            ["Отгрузки", "П/И/С", "Только свои", "–", "П/И/С", "–"],
            ["Отчёты", "Полные", "–", "Производственные", "Складские", "Качество"],
            ["Аудит", "П", "–", "–", "–", "–"],
            ["Пользователи и роли", "П/И/Р", "–", "–", "–", "–"],
        ],
    )
    paragraph(body, "Примечание: П — просмотр, И — изменение/создание, Р — редактирование, С — изменение статуса или проведение операции.", style="Caption", align="center")

    heading(body, 2, "1.3 Основные угрозы безопасности и целостности")
    bullet_list(
        body,
        [
            "несанкционированный доступ к внутренним данным предприятия при обходе интерфейсных ограничений;",
            "вызов запрещённых действий прямыми URL без серверной проверки прав;",
            "SQL-инъекции при небезопасной подстановке пользовательских параметров в SQL;",
            "подмена цены позиции заказа клиентом через форму или POST-запрос;",
            "произвольное изменение статусов заказов, счетов, поставок, производства и отгрузок;",
            "отгрузка неоплаченного заказа либо заказа без корректно покрывающей отгрузки;",
            "использование сырья без успешной проверки качества или после истечения срока годности;",
            "отгрузка готовой продукции без положительной проверки качества;",
            "ошибочные действия внутренних пользователей, ведущие к повторному созданию документов или дублированию складских партий;",
            "нарушение целостности при попытке задать отрицательные остатки, отрицательные количества и некорректные даты;",
            "подмена customer_id, status_code, unit_price, shipped_at и иных полей через изменённые POST-запросы;",
            "доступ клиента к аудиту, финансовым данным поставщиков и внутренней производственной информации.",
        ],
    )

    heading(body, 1, "2 ПОСТРОЕНИЕ ИНФОЛОГИЧЕСКОЙ МОДЕЛИ")
    add_text_block(
        body,
        """
        Инфологическая модель проектируемой системы отражает состав данных, подлежащих хранению, и логические связи между сущностями предметной области. В системе выделены клиентский контур, поставочный контур, производственный контур, контур качества, контур отгрузки и контур безопасности.
        """,
    )
    add_figure_placeholder(body, FIGURES[1])
    add_table(
        body,
        "Таблица 3 — Основные сущности инфологической модели",
        ["Сущность", "Назначение", "Ключ", "Основные атрибуты", "Ключевые связи"],
        [
            ["users", "Учёт пользователей веб-системы", "user_id", "username, password_hash, status_code, customer_id", "M:N с roles, 1:M с audit_log"],
            ["roles", "Логические роли доступа", "role_id", "role_code, role_name", "M:N с users"],
            ["customers", "Хранение клиентов", "customer_id", "customer_type, full_name, company_name, phone, email", "1:M с customer_orders"],
            ["suppliers", "Хранение поставщиков", "supplier_id", "company_name, phone, email", "1:M с deliveries, 1:M с supplier_invoices"],
            ["supplier_materials", "Закрепление сырья за поставщиком", "supplier_material_id", "purchase_price, lead_time_days, is_active", "M:N suppliers ↔ raw_materials"],
            ["raw_materials", "Справочник сырья", "material_id", "name, unit, shelf_life_days, min_stock_qty", "1:M delivery_items, recipe_items, raw_material_stock"],
            ["raw_material_deliveries", "Заголовок поставки сырья", "delivery_id", "delivery_number, delivery_date, status_code", "1:M delivery_items, 1:1 supplier_invoices"],
            ["supplier_invoices", "Счета поставщиков", "supplier_invoice_id", "supplier_invoice_number, amount, status_code, paid_at", "M:1 suppliers, 1:1 deliveries"],
            ["products", "Номенклатура готовой продукции", "product_id", "name, price, unit, shelf_life_days", "1:M tech_cards, order_items, production_batches"],
            ["tech_cards", "Технологические карты", "tech_card_id", "card_number, version, status_code, effective dates", "1:M recipe_items, 1:M production_batches"],
            ["recipe_items", "Строки рецептуры", "recipe_item_id", "material_id, quantity, unit, stage, waste_percent", "M:1 tech_cards, M:1 raw_materials"],
            ["customer_orders", "Заказы клиентов", "order_id", "order_number, customer_id, order_date, status_code", "1:M order_items, invoices, shipments"],
            ["production_batches", "Производственные партии", "production_batch_id", "batch_number, product_id, tech_card_id, status_code", "1:M finished_goods_stock, quality_checks"],
            ["quality_checks", "Результаты контроля качества", "quality_check_id", "check_type, result_code, checked_at", "M:1 delivery_items или production_batches"],
            ["shipments", "Отгрузки по заказам", "shipment_id", "shipment_number, order_id, shipped_at, status_code", "1:M shipment_items"],
            ["audit_log", "Журнал аудита", "audit_id", "action_type, table_name, old_data, new_data", "M:1 users"],
        ],
    )

    heading(body, 2, "2.1 Связи между сущностями")
    bullet_list(
        body,
        [
            "клиент связан с заказами отношением 1:M;",
            "заказ связан с позициями заказа, счетами и отгрузками отношением 1:M;",
            "поставщик связан с поставляемым сырьём через промежуточную таблицу supplier_materials;",
            "поставка связана с позициями поставки 1:M и со счётом поставщика 1:1;",
            "сырьё связано со складскими партиями, позициями поставки и строками рецептуры;",
            "продукция связана с технологическими картами, производственными партиями и позициями заказов;",
            "техкарта связана со строками рецептуры и производственными партиями;",
            "производственная партия связана с готовой продукцией на складе и проверками качества;",
            "отгрузка связана с позициями отгрузки и через заказ — с клиентом;",
            "пользователь связан с ролями отношением M:N и с журналом аудита отношением 1:M.",
        ],
    )

    heading(body, 1, "3 ПРОЕКТИРОВАНИЕ ЛОГИЧЕСКОЙ СТРУКТУРЫ СИСТЕМЫ")
    add_text_block(
        body,
        """
        Логическая структура Slop-Bakery реализована как трёхуровневая архитектура. На уровне представления используются HTML-шаблоны Jinja2 и серверный рендеринг форм. На уровне приложения маршруты FastAPI выполняют авторизацию, проверку прав, обработку бизнес-сценариев и подготовку данных для шаблонов. На уровне хранения данных PostgreSQL обеспечивает структурированное хранение сущностей, ограничений, индексов, ролей и аудита.
        """,
    )
    add_figure_placeholder(body, FIGURES[2])
    add_table(
        body,
        "Таблица 4 — Основные модули прикладного уровня",
        ["Модуль", "Назначение", "Входные данные", "Выходные данные", "Основные таблицы", "Ограничения доступа"],
        [
            ["auth", "Вход, выход, сессии, flash-сообщения", "username, password, session", "current_user, redirect, error", "users, audit_log", "Все пользователи, но protected sections требуют вход"],
            ["dashboard", "Персональные и административные панели", "роль пользователя", "сводные показатели и последние события", "orders, invoices, shipments, products, audit_log", "client видит только личный dashboard; audit block только admin"],
            ["customers", "Учёт клиентов", "карточка клиента", "список/карточка/форма", "customers", "Только admin"],
            ["suppliers", "Поставщики и supplier_materials", "данные поставщика и поставляемого сырья", "карточка, связи supplier-material", "suppliers, supplier_materials, raw_materials", "admin, warehouse_worker"],
            ["materials", "Сырьё, поставки, склад сырья", "delivery items, delivery status", "списки сырья, поставок и остатков", "raw_materials, deliveries, delivery_items, raw_material_stock", "admin, warehouse_worker; просмотр материалов также technologist и quality"],
            ["products", "Продукция и публичный каталог", "данные продукции", "список, карточка, формы", "products, finished_goods_stock", "client видит только active products"],
            ["tech_cards", "Технологические карты и рецептуры", "карта, статус, строки рецепта", "карточки техкарт и recipe items", "tech_cards, recipe_items, raw_materials", "admin, technologist"],
            ["orders", "Заказы клиентов", "данные заказа и позиции", "orders, order_items, status changes", "customer_orders, order_items, products", "client только свои заказы и только draft-редактирование"],
            ["invoices", "Счета клиентам", "order selection, status update, payment", "список счетов и операции оплаты", "invoices, customer_orders", "admin создаёт; client видит и оплачивает только свои"],
            ["supplier_invoices", "Счета поставщиков", "accepted delivery", "список, карточка, оплата", "supplier_invoices, deliveries, suppliers", "warehouse_worker видит, admin оплачивает"],
            ["production", "Производственные партии", "product_id, tech_card_id, status", "production_batches и finished stock", "production_batches, recipe_items, raw_material_stock", "admin, technologist"],
            ["quality", "Проверки качества сырья и ГП", "inspection type, объект проверки, result", "quality_checks", "quality_checks, delivery_items, production_batches", "admin, quality_control"],
            ["shipments", "Отгрузки и печатная форма", "order_id, shipment items, batch", "shipments, shipment report", "shipments, shipment_items, finished_goods_stock", "admin, warehouse_worker; client только просмотр своих"],
            ["reports", "Операционные отчёты", "период отчёта", "role-filtered sections", "orders, stocks, production, quality, supplier_invoices", "client denied; разные срезы по ролям"],
            ["audit", "Журнал аудита", "фильтры по пользователю и действию", "список записей audit_log", "audit_log, users", "Только admin"],
            ["admin/users", "Пользователи и роли", "административный запрос", "список пользователей и ролей", "users, roles, user_roles", "Только admin"],
        ],
    )

    heading(body, 1, "4 ПРОЕКТИРОВАНИЕ БАЗЫ ДАННЫХ")
    add_text_block(
        body,
        """
        Физическая модель системы реализована в PostgreSQL и разделена на инициализационные SQL-скрипты создания схемы, ограничений, индексов, ролей и аудита. Основные таблицы используют первичные ключи типа BIGINT, внешние ключи, проверки корректности статусов, количеств и дат. Статусные таблицы нормализованы и используются для ссылочной проверки жизненных циклов документов.
        """,
    )
    add_table(
        body,
        "Таблица 5 — Поля таблицы customers",
        ["Поле", "Тип", "Ключ/ограничение", "Описание"],
        [
            ["customer_id", "BIGINT", "PK", "Идентификатор клиента"],
            ["customer_type", "VARCHAR(20)", "CHECK individual/company", "Тип клиента"],
            ["full_name", "VARCHAR(200)", "обязателен для individual", "ФИО физического лица"],
            ["company_name", "VARCHAR(200)", "обязателен для company", "Название компании"],
            ["phone", "VARCHAR(32)", "NOT NULL", "Контактный телефон"],
            ["email", "VARCHAR(255)", "UNIQUE при NOT NULL", "Адрес электронной почты"],
            ["delivery_address", "TEXT", "NOT NULL", "Адрес доставки"],
            ["created_at", "TIMESTAMPTZ", "DEFAULT CURRENT_TIMESTAMP", "Дата регистрации"],
            ["is_active", "BOOLEAN", "DEFAULT TRUE", "Признак активности клиента"],
        ],
    )
    add_table(
        body,
        "Таблица 6 — Поля таблицы supplier_invoices",
        ["Поле", "Тип", "Ключ/ограничение", "Описание"],
        [
            ["supplier_invoice_id", "BIGINT", "PK", "Идентификатор счёта поставщика"],
            ["supplier_invoice_number", "VARCHAR(50)", "UNIQUE", "Номер счёта поставщика"],
            ["delivery_id", "BIGINT", "FK -> raw_material_deliveries, UNIQUE", "Поставка, по которой выставлен счёт"],
            ["supplier_id", "BIGINT", "FK -> suppliers", "Поставщик"],
            ["issue_date", "DATE", "NOT NULL", "Дата выставления"],
            ["due_date", "DATE", "CHECK due_date >= issue_date", "Срок оплаты"],
            ["paid_at", "TIMESTAMPTZ", "CHECK по status_code", "Дата оплаты"],
            ["amount", "NUMERIC(12,2)", "CHECK amount >= 0", "Сумма счёта"],
            ["status_code", "VARCHAR(32)", "FK -> invoice_statuses", "Статус счёта"],
            ["document_ref", "VARCHAR(100)", "NULL", "Ссылка на документ"],
            ["note", "TEXT", "NULL", "Комментарий"],
        ],
    )
    add_table(
        body,
        "Таблица 7 — Поля таблицы tech_cards",
        ["Поле", "Тип", "Ключ/ограничение", "Описание"],
        [
            ["tech_card_id", "BIGINT", "PK", "Идентификатор техкарты"],
            ["product_id", "BIGINT", "FK -> products", "Продукция"],
            ["card_number", "VARCHAR(50)", "UNIQUE", "Номер техкарты"],
            ["version", "INTEGER", "CHECK version > 0", "Версия"],
            ["status_code", "VARCHAR(32)", "FK -> tech_card_statuses", "Статус"],
            ["effective_from / effective_to", "DATE", "CHECK по диапазону", "Период действия"],
            ["approved_by_user_id", "BIGINT", "FK -> users", "Утверждающий пользователь"],
        ],
    )
    add_table(
        body,
        "Таблица 8 — Поля таблицы customer_orders",
        ["Поле", "Тип", "Ключ/ограничение", "Описание"],
        [
            ["order_id", "BIGINT", "PK", "Идентификатор заказа"],
            ["order_number", "VARCHAR(50)", "UNIQUE", "Номер заказа"],
            ["customer_id", "BIGINT", "FK -> customers", "Клиент"],
            ["order_date", "TIMESTAMPTZ", "DEFAULT CURRENT_TIMESTAMP", "Дата заказа"],
            ["planned_shipment_date", "DATE", "CHECK >= order_date::date", "Плановая дата отгрузки"],
            ["status_code", "VARCHAR(32)", "FK -> order_statuses", "Статус заказа"],
            ["created_by_user_id", "BIGINT", "FK -> users", "Кто создал заказ"],
        ],
    )
    add_table(
        body,
        "Таблица 9 — Поля таблицы production_batches",
        ["Поле", "Тип", "Ключ/ограничение", "Описание"],
        [
            ["production_batch_id", "BIGINT", "PK", "Идентификатор производственной партии"],
            ["batch_number", "VARCHAR(80)", "UNIQUE", "Номер партии"],
            ["product_id", "BIGINT", "FK -> products", "Продукция"],
            ["tech_card_id", "BIGINT", "FK -> tech_cards", "Использованная техкарта"],
            ["production_date", "TIMESTAMPTZ", "DEFAULT CURRENT_TIMESTAMP", "Дата производства"],
            ["quantity_produced", "NUMERIC(12,3)", "CHECK > 0", "Объём выпуска"],
            ["quantity_defective", "NUMERIC(12,3)", "CHECK 0 <= defective <= produced", "Количество брака"],
            ["responsible_user_id", "BIGINT", "FK -> users", "Ответственный технолог"],
            ["status_code", "VARCHAR(32)", "FK -> production_statuses", "Статус партии"],
        ],
    )
    add_table(
        body,
        "Таблица 10 — Поля таблицы shipments",
        ["Поле", "Тип", "Ключ/ограничение", "Описание"],
        [
            ["shipment_id", "BIGINT", "PK", "Идентификатор отгрузки"],
            ["shipment_number", "VARCHAR(50)", "UNIQUE", "Номер отгрузки"],
            ["order_id", "BIGINT", "FK -> customer_orders", "Заказ"],
            ["shipped_at", "TIMESTAMPTZ", "CHECK >= order_date", "Дата отгрузки"],
            ["status_code", "VARCHAR(32)", "FK -> shipment_statuses", "Статус"],
            ["delivery_address", "TEXT", "NOT NULL", "Адрес доставки"],
            ["waybill_number", "VARCHAR(100)", "UNIQUE при NOT NULL", "Номер накладной"],
            ["created_by_user_id", "BIGINT", "FK -> users", "Кто оформил отгрузку"],
        ],
    )
    add_table(
        body,
        "Таблица 11 — Поля таблицы audit_log",
        ["Поле", "Тип", "Ключ/ограничение", "Описание"],
        [
            ["audit_id", "BIGINT", "PK", "Идентификатор записи аудита"],
            ["user_id", "BIGINT", "FK -> users", "Пользователь"],
            ["action_type", "VARCHAR(20)", "CHECK INSERT/UPDATE/DELETE/LOGIN/LOGOUT", "Тип события"],
            ["table_name", "VARCHAR(100)", "NOT NULL", "Имя таблицы или контекста"],
            ["record_id", "VARCHAR(100)", "NULL", "Идентификатор изменённой записи"],
            ["changed_at", "TIMESTAMPTZ", "DEFAULT CURRENT_TIMESTAMP", "Время события"],
            ["old_data", "JSONB", "NULL", "Снимок прежних значений"],
            ["new_data", "JSONB", "NULL", "Снимок новых значений"],
            ["ip_address", "INET", "NULL", "IP-адрес клиента"],
            ["success", "BOOLEAN", "DEFAULT TRUE", "Признак успешности"],
        ],
    )

    heading(body, 2, "4.1 Ограничения целостности")
    bullet_list(
        body,
        [
            "все основные сущности имеют первичные ключи BIGINT и внешние ключи с ON DELETE RESTRICT там, где удаление связанных данных недопустимо;",
            "UNIQUE-ограничения используются для номеров заказов, счетов, отгрузок, поставок, batch_number и идентификаторов связей;",
            "CHECK-ограничения контролируют положительность количеств и цен, корректность сроков годности, диапазоны waste_percent и логические зависимости paid_at от статуса счёта;",
            "частичный уникальный индекс ux_invoices_one_active_per_order запрещает повторное создание активного или уже оплаченного клиентского счёта по одному заказу;",
            "частичный уникальный индекс для tech_cards обеспечивает единственную active-карту для одного продукта;",
            "матрицы переходов статусов дополнительно проверяются на сервере в маршрутах приложения;",
            "при производстве и отгрузке выполняются транзакционные проверки складских остатков и качества, предотвращающие отрицательные остатки и использование неподходящих партий.",
        ],
    )
    heading(body, 2, "4.2 Матрицы статусов")
    add_table(body, "Таблица 12 — Допустимые переходы статусов заказа", ["Текущий статус", "Допустимый переход"], [["draft", "confirmed, cancelled"], ["confirmed", "in_production, cancelled"], ["in_production", "ready"], ["ready", "shipped"], ["shipped", "completed"], ["completed", "переходы запрещены"], ["cancelled", "переходы запрещены"]])
    add_table(body, "Таблица 13 — Допустимые переходы статусов клиентского счёта", ["Текущий статус", "Допустимый переход"], [["issued", "paid, overdue"], ["overdue", "paid"], ["paid", "переходы запрещены"], ["cancelled", "переходы запрещены"]])
    add_table(body, "Таблица 14 — Допустимые переходы статусов поставки", ["Текущий статус", "Допустимый переход"], [["planned", "received, cancelled"], ["received", "accepted, rejected"], ["accepted", "переходы запрещены"], ["rejected", "переходы запрещены"], ["cancelled", "переходы запрещены"]])
    add_table(body, "Таблица 15 — Допустимые переходы статусов производства, отгрузки и техкарты", ["Сущность", "Переходы"], [["production_batches", "planned -> in_progress / cancelled; in_progress -> completed / cancelled"], ["shipments", "planned -> shipped / cancelled; shipped -> delivered"], ["tech_cards", "draft -> active / archived; active -> archived"], ["supplier_invoices", "issued -> paid / overdue; overdue -> paid"]])
    add_figure_placeholder(body, FIGURES[4])
    add_figure_placeholder(body, FIGURES[5])
    add_figure_placeholder(body, FIGURES[6])
    add_figure_placeholder(body, FIGURES[7])

    heading(body, 2, "4.3 Ключевые бизнес-ограничения")
    bullet_list(
        body,
        [
            "клиент не может выбирать статус заказа и не может изменять цену позиции заказа;",
            "заказ нельзя перевести в shipped без оплаченного клиентского счёта и корректно покрывающей отгрузки;",
            "невозможно выставить несколько клиентских счетов по одному заказу в состояниях issued, overdue или paid;",
            "поставка в статусе planned не увеличивает складской остаток; остатки появляются после received/accepted, а счёт поставщика создаётся автоматически при accepted;",
            "сырьё допускается к производству только при наличии passed quality check и при отсутствии failed-проверки;",
            "готовая продукция допускается к отгрузке только при passed-проверке качества производственной партии;",
            "производство не запускается при недостатке сырья, использовании просроченных партий или несоответствующей техкарты;",
            "отгрузка уменьшает finished_goods_stock и не допускает отрицательных остатков, перепоставки либо использования просроченной партии;",
            "цена позиции поставки берётся с сервера из supplier_materials.purchase_price;",
            "повторное добавление одного и того же сырья на том же этапе техкарты обновляет quantity, а не суммирует его.",
        ],
    )

    heading(body, 1, "5 ВЫБОР ИНСТРУМЕНТОВ И ТЕХНОЛОГИЙ")
    add_text_block(
        body,
        """
        В качестве СУБД выбрана PostgreSQL, поскольку система требует поддержки внешних ключей, CHECK-ограничений, индексов, ролей, триггеров, транзакций и расширенных типов данных, включая JSONB для аудита. PostgreSQL обеспечивает промышленный уровень реализации ограничений целостности и удобен для учебного проекта, ориентированного на безопасность баз данных.

        Для уровня приложения использован FastAPI. Этот фреймворк позволяет организовать компактную структуру роутеров, реализовать middleware для авторизации и сессий, а также централизовать проверки action-level permissions и бизнес-валидаторы. В проекте FastAPI применяется совместно с шаблонами Jinja2, что позволило отказаться от усложнения архитектуры отдельным SPA-приложением.

        Python выбран как язык прикладной реализации благодаря лаконичности, богатому экосистемному набору библиотек и удобству работы с PostgreSQL через psycopg. Прикладной код проверяет серверные правила, подготавливает параметры SQL-запросов и формирует читаемые сообщения об ошибках без вывода технических трассировок.

        Docker Compose используется для воспроизводимого локального развёртывания. В составе проекта поднимаются контейнеры db и web, причём приложение обращается к PostgreSQL по имени сервиса db, а внешний порт базы данных задаётся через переменную POSTGRES_PORT. Для Windows-пользователя предусмотрены PowerShell-скрипты reset_db.ps1 и start_web.ps1.
        """,
    )

    heading(body, 1, "6 РЕАЛИЗАЦИЯ БАЗЫ ДАННЫХ")
    add_text_block(
        body,
        """
        Реализация БД организована набором SQL-скриптов. Скрипт 00_drop.sql удаляет объекты для повторного запуска; 01_schema.sql создаёт таблицы и первичные ключи; 02_constraints.sql подключает внешние ключи и проверки; 03_indexes.sql создаёт индексы, включая частичные; 04_security_roles.sql настраивает роли PostgreSQL и GRANT; 05_audit.sql определяет функцию аудита и триггеры; 06_seed.sql наполняет систему тестовыми данными; 07_test_queries.sql содержит проверочные запросы; 99_run_all.sql объединяет запуск.

        В схеме присутствуют status dictionaries, предметные таблицы и служебные таблицы безопасности. Отдельно выделена таблица supplier_invoices, что позволяет разделить клиентские счета и обязательства хлебозавода перед поставщиками. Для демонстрации в seed-данных созданы пять пользователей с bcrypt-хэшами паролей, несколько клиентов и поставщиков, поставки сырья, технологические карты, производственные партии, счета, отгрузки и записи аудита.
        """,
    )
    heading(body, 2, "6.1 Примеры SQL-запросов")
    queries = [
        ("6.1.1 Запрос ввода данных №1", "INSERT INTO customers (customer_id, customer_type, full_name, phone, delivery_address)\nVALUES (1001, 'individual', 'Иванов Иван Иванович', '+7-900-000-00-01', 'г. Москва, ул. Пример, д. 1');", "Добавление нового клиента.", "В таблицу customers добавляется новая строка клиента-физлица."),
        ("6.1.2 Запрос ввода данных №2", "INSERT INTO raw_materials (material_id, name, unit, min_stock_qty, shelf_life_days)\nVALUES (1001, 'rye_malt', 'kg', 20, 180);", "Добавление нового вида сырья.", "Справочник сырья пополняется новой позицией с минимальным остатком и сроком годности."),
        ("6.1.3 Запрос ввода данных №3", "INSERT INTO supplier_materials (supplier_material_id, supplier_id, material_id, purchase_price, lead_time_days)\nVALUES (1001, 1, 1001, 145.50, 3);", "Закрепление сырья за поставщиком.", "Создаётся связь поставщика и сырья с зафиксированной ценой."),
        ("6.1.4 Запрос выборки в заданном порядке №1", "SELECT customer_id, COALESCE(company_name, full_name) AS customer_name, created_at\nFROM customers\nORDER BY created_at DESC, customer_id DESC;", "Вывод клиентов в порядке регистрации.", "Получается упорядоченный список клиентов."),
        ("6.1.5 Запрос выборки в заданном порядке №2", "SELECT order_number, status_code, order_date\nFROM customer_orders\nORDER BY order_date DESC, order_number;", "Вывод заказов в обратном хронологическом порядке.", "Отображаются последние заказы."),
        ("6.1.6 Запрос выборки в заданном порядке №3", "SELECT batch_number, production_date, quantity_produced\nFROM production_batches\nORDER BY production_date DESC, batch_number;", "Вывод производственных партий по дате.", "Получается журнал производства за период."),
        ("6.1.7 Запрос с исключением дубликатов №1", "SELECT DISTINCT status_code\nFROM customer_orders\nORDER BY status_code;", "Список реально используемых статусов заказов.", "Каждый статус выводится единожды."),
        ("6.1.8 Запрос с исключением дубликатов №2", "SELECT DISTINCT supplier_id, material_id\nFROM supplier_materials\nWHERE is_active = TRUE\nORDER BY supplier_id, material_id;", "Активные пары поставщик–сырьё.", "Дубликаты по связям исключаются."),
        ("6.1.9 Запрос с константами и выражениями №1", "SELECT product_id, name, price, price * 1.10 AS price_with_markup\nFROM products\nORDER BY name;", "Расчёт цены с условной наценкой.", "Возвращается базовая цена и выражение price_with_markup."),
        ("6.1.10 Запрос с константами и выражениями №2", "SELECT delivery_number, delivery_date, delivery_date + INTERVAL '7 day' AS planned_payment_date\nFROM raw_material_deliveries\nORDER BY delivery_date DESC;", "Расчёт условной даты оплаты поставки.", "Для каждой поставки выводится дата и расчётная дата оплаты."),
        ("6.1.11 Запрос с константами и выражениями №3", "SELECT batch_number, expiry_date, expiry_date - CURRENT_DATE AS days_to_expiry\nFROM finished_goods_stock\nORDER BY expiry_date;", "Расчёт остатка дней до истечения срока годности.", "Позволяет выявить близкие к истечению партии."),
        ("6.1.12 Запрос с константами и выражениями №4", "SELECT order_number, 'ORDER-' || order_id AS order_label\nFROM customer_orders\nORDER BY order_id;", "Формирование производного строкового идентификатора.", "Для заказа вычисляется текстовая метка."),
        ("6.1.13 Запрос с группировкой и упорядочиванием №1", "SELECT rm.name, COALESCE(SUM(rms.quantity_current), 0) AS qty\nFROM raw_materials rm\nLEFT JOIN raw_material_stock rms ON rms.material_id = rm.material_id\nGROUP BY rm.name\nORDER BY qty ASC, rm.name;", "Группировка складских остатков сырья.", "Получается агрегированный список остатков по видам сырья."),
        ("6.1.14 Запрос с группировкой и упорядочиванием №2", "SELECT p.name, SUM(oi.line_amount) AS revenue\nFROM order_items oi\nJOIN products p ON p.product_id = oi.product_id\nGROUP BY p.name\nORDER BY revenue DESC, p.name;", "Группировка продаж по продукции.", "Определяется объём выручки по каждой номенклатуре."),
        ("6.1.15 Запрос с агрегатными функциями №1", "SELECT COUNT(*) AS customer_count FROM customers;", "Подсчёт клиентов.", "Возвращается число зарегистрированных клиентов."),
        ("6.1.16 Запрос с агрегатными функциями №2", "SELECT SUM(amount) AS unpaid_supplier_total\nFROM supplier_invoices\nWHERE status_code IN ('issued', 'overdue');", "Подсчёт задолженности поставщикам.", "Возвращается суммарная задолженность."),
        ("6.1.17 Запрос с функциями даты №3", "SELECT invoice_number, issue_date, EXTRACT(DAY FROM (CURRENT_DATE - issue_date)) AS age_days\nFROM invoices\nORDER BY issue_date;", "Возраст клиентских счетов в днях.", "Определяется срок нахождения счёта в обороте."),
        ("6.1.18 Запрос со строковой функцией №4", "SELECT username, UPPER(username) AS username_upper\nFROM users\nORDER BY username;", "Преобразование логинов в верхний регистр.", "Показывается использование строковой функции UPPER."),
        ("6.1.19 Запрос с комбинированными функциями №5", "SELECT COALESCE(c.company_name, c.full_name) AS customer_name,\n       COUNT(o.order_id) AS orders_count,\n       MAX(o.order_date) AS last_order_date\nFROM customers c\nLEFT JOIN customer_orders o ON o.customer_id = c.customer_id\nGROUP BY COALESCE(c.company_name, c.full_name)\nORDER BY orders_count DESC, customer_name;", "Подсчёт числа заказов и даты последнего заказа по каждому клиенту.", "Возвращается агрегированная клиентская статистика."),
    ]
    for title, sql, purpose, expected in queries:
        heading(body, 3, title)
        paragraph(body, "Назначение: " + purpose)
        paragraph(body, "SQL-код:")
        for line in sql.splitlines():
            code_paragraph(body, line)
        paragraph(body, "Ожидаемый результат: " + expected)

    heading(body, 1, "7 РЕАЛИЗАЦИЯ УРОВНЯ ПРИЛОЖЕНИЯ")
    add_text_block(
        body,
        """
        Веб-приложение расположено в каталоге web/app и разделено на отдельные роутеры по предметным областям. Основной объект FastAPI создаётся в main.py, где подключаются шаблоны, статика, SessionMiddleware, middleware обязательного входа и обработчик исключений.

        Авторизация построена на таблице users. Пароли в БД хранятся только в виде bcrypt-хэшей, а проверка выполняется через passlib. После успешного входа сведения о пользователе сохраняются в серверной сессии. Успешные и неуспешные попытки входа, а также выход пользователя, регистрируются в audit_log через функцию log_auth_event.

        Для разграничения доступа используются две группы проверок. Первая группа — SECTION_RULES — определяет доступ к разделам навигации. Вторая группа — ACTION_RULES — определяет точечные разрешения на создание, изменение статусов, оплату, просмотр отчётов и другие чувствительные действия. Практически все критичные POST-маршруты вызывают authorize_action, а прямые GET-маршруты к закрытым ресурсам возвращают страницу ошибки 403 вместо Application Error.

        Работа с PostgreSQL вынесена в database.py. Запросы выполняются параметризованно через psycopg, что снижает риск SQL-инъекций. Бизнес-операции, изменяющие несколько связанных таблиц, выполняются в рамках одной транзакции. При нарушении бизнес-условий пользователю показывается читаемое сообщение, а технические ошибки БД перехватываются без вывода сырого SQL-текста.
        """,
    )
    add_table(
        body,
        "Таблица 16 — Ключевые прикладные сценарии",
        ["Сценарий", "Краткое описание серверной логики", "Контролируемые условия"],
        [
            ["Клиент создаёт заказ", "customer_id подставляется по текущему пользователю, статус фиксируется как draft", "нельзя подменить customer_id и status_code"],
            ["Клиент добавляет позицию", "цена берётся из products.price, duplicate item обновляет quantity", "нельзя передать unit_price, нужен available stock и draft-заказ"],
            ["Администратор подтверждает заказ и выставляет счёт", "создание invoice доступно только admin", "повторный счёт блокируется, сумма считается по order_items"],
            ["Клиент оплачивает счёт", "invoice обновляется через UPDATE, status_code=paid, paid_at=current_timestamp", "оплата только своего счёта в issued/overdue"],
            ["Технолог запускает производство", "проверяются техкарта, сырьё, качество и роль ответственного", "нет запуска без passed-quality сырья и active tech card"],
            ["ОТК создаёт проверку качества", "валидация check_type и объекта проверки", "для raw_material нужен delivery_item_id, для finished_product — production_batch_id"],
            ["Склад создаёт отгрузку", "shipment доступна только по ready + paid order", "нельзя отгрузить без оплаты, качества и складского остатка"],
            ["Администратор просматривает аудит", "маршрут /audit доступен только по action audit.view", "client, technologist, warehouse и quality получают 403"],
        ],
    )

    heading(body, 1, "8 РЕАЛИЗАЦИЯ ИНТЕРФЕЙСА")
    add_text_block(
        body,
        """
        Интерфейс реализован в виде серверно-рендерируемого веб-приложения с использованием шаблонов Jinja2 и Bootstrap через CDN. Навигационное меню строится динамически на основе видимых разделов для текущей роли. Клиентский dashboard отличается от административного и не содержит внутренней статистики, аудита и служебной информации.
        """,
    )
    add_table(
        body,
        "Таблица 17 — Основные экранные формы",
        ["Форма", "Назначение", "Роли", "Ключевые поля", "Основные ограничения"],
        [
            ["login", "Аутентификация", "Все", "username, password", "без входа защищённые разделы недоступны"],
            ["dashboard admin", "Операционная сводка и аудит", "admin", "статистика, последние заказы, recent audit", "клиентам недоступен"],
            ["dashboard client", "Личный кабинет клиента", "client", "свои заказы, счета, отгрузки, доступная продукция", "нет глобальной статистики и аудита"],
            ["products", "Каталог продукции", "Все разрешённые роли", "name, price, unit, available stock", "client видит только active products"],
            ["orders / order details", "Заказы и состав заказа", "admin, client, technologist, warehouse", "status, items, quantities", "client работает только со своими draft-заказами"],
            ["invoices", "Клиентские счета", "admin, client", "invoice_number, amount, status, paid_at", "client оплачивает только свои issued/overdue счета"],
            ["supplier invoices", "Счета поставщиков", "admin, warehouse", "supplier, delivery, amount, status", "оплата только admin"],
            ["suppliers / supplier materials", "Поставщики и закреплённое сырьё", "admin, warehouse", "material, purchase_price, lead_time_days", "нельзя создать delivery item без активной связи"],
            ["deliveries / material stock", "Поставки и склад сырья", "admin, warehouse", "delivery status, batches, expiry", "planned не создаёт stock"],
            ["tech cards", "Технологические карты", "admin, technologist", "version, status, recipe items", "active-карты не редактируются задним числом"],
            ["production", "Журнал производства", "admin, technologist", "product, tech card, quantities, responsible", "tech card active, сырьё доступно и годно"],
            ["quality", "Контроль качества", "admin, quality_control", "inspection type, result, object", "inspector должен иметь роль ОТК"],
            ["finished stock", "Остатки готовой продукции", "admin, technologist, warehouse", "batch, qty, expiry", "используются для заказа и отгрузки"],
            ["shipments / shipment report", "Отгрузки и печатная форма", "admin, warehouse, client(view own)", "shipment items, batch, shipped_at", "только paid+ready order и passed QC"],
            ["audit", "Журнал аудита", "admin", "filters by user/table/action/date", "всем остальным возвращается 403"],
            ["users and roles", "Управление пользователями и ролями", "admin", "username, status, role list", "закрыт от неадминистраторов"],
        ],
    )
    paragraph(body, "TODO: после выполнения ручного запуска приложения рекомендуется вставить фактические скриншоты интерфейса по нижеприведённым подписям.", bold=True)
    bullet_list(
        body,
        [
            "Рисунок 9 — Форма входа в систему Slop-Bakery;",
            "Рисунок 10 — Личный dashboard клиента;",
            "Рисунок 11 — Форма создания заказа клиентом;",
            "Рисунок 12 — Карточка технологической карты;",
            "Рисунок 13 — Журнал производства;",
            "Рисунок 14 — Форма контроля качества;",
            "Рисунок 15 — Список отгрузок и печатная форма shipment report;",
            "Рисунок 16 — Журнал аудита администратора.",
        ],
    )

    heading(body, 1, "9 РЕАЛИЗАЦИЯ СРЕДСТВ ЗАЩИТЫ БД")
    add_text_block(
        body,
        """
        Защита от внутренних угроз строится на совмещении двух уровней контроля. На уровне СУБД используются SQL-роли, GRANT, ограничения целостности, триггерный аудит и минимально необходимые права. На уровне веб-приложения дополнительно реализованы object-level и action-level проверки, которые предотвращают обход ограничений через прямой URL либо подмену полей формы.

        Защита от внешних угроз обеспечивается параметризованными SQL-запросами, серверной валидацией входных данных, хранением паролей в виде bcrypt-хэшей, использованием секретного ключа приложения, контейнеризацией сервисов и ограничением внешних портов в Docker Compose. В документации проекта отдельно указано, что APP_SECRET_KEY из примера необходимо заменить случайным значением при реальном запуске.

        Защита целостности охватывает хранение и изменение остатков, жизненный цикл документов и запрет повторных операций. В частности, partial unique index исключает повторные active client invoices по одному заказу; при accepted-поставке supplier invoice создаётся один раз; production completed не может быть проведён повторно с повторным добавлением finished stock; shipment item списывает готовую продукцию транзакционно и не допускает отрицательных остатков.
        """,
    )
    add_table(
        body,
        "Таблица 18 — Исследование защищённости системы",
        ["Негативный сценарий", "Реализованная защита", "Результат"],
        [
            ["client открывает /audit", "authorize_action(request, 'audit.view')", "Возвращается 403"],
            ["client подменяет unit_price в POST заказа", "цена берётся только из products.price", "Подмена игнорируется"],
            ["client создаёт заказ с status_code=in_production", "status_code назначается на сервере как draft", "Подмена отклоняется"],
            ["warehouse пытается отгрузить неоплаченный заказ", "ensure_order_paid_for_shipping / ensure_paid_invoice_for_order", "Выводится сообщение об отсутствии оплаты"],
            ["technologist запускает производство без сырья", "consume_materials_for_production(validate only)", "Создание/переход запрещён"],
            ["использование сырья без passed quality", "проверка quality_checks по delivery_item", "Производство запрещено"],
            ["отгрузка партии без passed quality", "validate_finished_batch_quality", "Отгрузка запрещена"],
            ["повторное создание invoice по заказу", "серверная проверка + partial unique index", "Повторный счёт не создаётся"],
            ["delivery item добавляется без supplier_materials", "validate_supplier_material", "Операция запрещена"],
        ],
    )

    heading(body, 1, "10 ОТЧЁТЫ")
    add_text_block(
        body,
        """
        В системе реализованы role-filtered отчёты, формируемые маршрутом /reports и специальными карточками. Администратор получает полный набор показателей, технолог — производственную часть, складской работник — складские показатели, а сотрудник ОТК — отчёты по контролю качества. Клиенту внутренние отчёты недоступны.
        """,
    )
    add_table(
        body,
        "Таблица 19 — Реализованные отчёты",
        ["Отчёт", "Доступ", "Используемые таблицы", "Содержание", "Ограничения доступа"],
        [
            ["Остатки сырья", "admin, warehouse, technologist, quality", "raw_material_stock, raw_materials", "Текущий запас сырья по видам", "client denied"],
            ["Сырьё ниже минимума", "admin, warehouse", "raw_materials, raw_material_stock", "Норматив и фактический остаток", "reports.view_full / reports.view_warehouse"],
            ["Остатки готовой продукции", "admin, warehouse, technologist", "finished_goods_stock, products", "Доступный склад ГП", "client denied"],
            ["Заказы за период", "admin, technologist", "customer_orders, customers", "Номера, клиенты, даты, статусы", "client denied"],
            ["Продажи за период", "admin", "customer_orders, order_items, products", "Количество и сумма по продукции", "финансовый отчёт только admin"],
            ["Производство за период", "admin, technologist", "production_batches, products", "Выпуск, брак, статусы партий", "по action reports.view_production / full"],
            ["Контроль качества за период", "admin, quality_control", "quality_checks, delivery_items, production_batches", "Тип проверки, объект, результат, документ", "финансовые блоки отсутствуют"],
            ["Отчёт по отгрузке", "admin, warehouse, client(own)", "shipments, shipment_items, orders, customers, finished_goods_stock", "Печатная форма одной отгрузки", "client видит только свои reports"],
            ["Счета поставщиков", "admin, warehouse", "supplier_invoices, suppliers, deliveries", "Неоплаченные, оплаченные и сводка", "оплата только admin"],
            ["Аудит действий", "admin", "audit_log, users", "Журнал INSERT/UPDATE/DELETE/LOGIN/LOGOUT", "другим ролям возвращается 403"],
        ],
    )

    heading(body, 1, "11 АПРОБАЦИЯ РАБОТЫ СИСТЕМЫ")
    add_table(
        body,
        "Таблица 20 — Тестовые сценарии апробации",
        ["№", "Роль", "Действие", "Ожидаемый результат", "Фактический результат", "Статус"],
        [
            ["1", "client", "Создание заказа", "Создан собственный заказ со статусом draft", "Соответствует реализованной логике", "Пройдено"],
            ["2", "client", "Попытка указать цену позиции", "Цена игнорируется, используется products.price", "Подмена unit_price блокируется на сервере", "Пройдено"],
            ["3", "client", "Оплата своего счёта", "invoice становится paid, paid_at заполняется", "Маршрут pay_own обновляет существующий invoice", "Пройдено"],
            ["4", "client", "Доступ к аудиту", "403", "Маршрут /audit закрыт по audit.view", "Пройдено"],
            ["5", "admin", "Подтверждение заказа", "Разрешён переход draft -> confirmed", "Проверяется матрицей ORDER_STATUS_TRANSITIONS", "Пройдено"],
            ["6", "admin", "Попытка отгрузить неоплаченный заказ", "Операция запрещена", "Проверка paid invoice выполняется серверно", "Пройдено"],
            ["7", "warehouse_worker", "Создание shipment по ready+paid order", "Отгрузка создаётся", "Маршрут shipments/new допускает только готовые и оплаченные заказы", "Пройдено"],
            ["8", "technologist", "Попытка начать производство без сырья", "Операция запрещена", "Серверная проверка доступности сырья возвращает ошибку", "Пройдено"],
            ["9", "quality_control", "Создание проверки качества", "Запись quality_check создаётся для допустимого объекта", "Валидация type/object выполняется", "Пройдено"],
            ["10", "warehouse_worker", "Закрепление сырья за поставщиком", "Создаётся/обновляется supplier_materials", "Связь доступна в UI поставщика", "Пройдено"],
            ["11", "warehouse_worker / admin", "Поставка со статусом accepted", "Создаётся supplier invoice", "Счёт поставщика формируется автоматически один раз", "Пройдено"],
            ["12", "admin", "Попытка создать второй client invoice по заказу", "Операция запрещена", "Повторный счёт блокируется сервером и индексом", "Пройдено"],
        ],
    )

    heading(body, 1, "ЗАКЛЮЧЕНИЕ")
    add_text_block(
        body,
        """
        В результате выполнения курсовой работы разработана защищённая система базы данных хлебозавода Slop-Bakery, включающая реляционную схему PostgreSQL, прикладной уровень на FastAPI, веб-интерфейс на Jinja2 и комплект инфраструктурных скриптов для локального развёртывания.

        В системе реализована ролевая модель доступа, включающая роли admin, client, technologist, warehouse_worker и quality_control. Для критичных маршрутов внедрены action-level permissions, исключающие обход защиты через прямые URL и произвольную подмену POST-параметров.

        Реализованы ограничения целостности и бизнес-проверки: контроль положительных количеств и сумм, контроль paid_at для оплаченных счетов, частичный запрет повторных счетов по одному заказу, запрет отгрузки неоплаченных заказов, проверка качества сырья и готовой продукции, запрет запуска производства без сырья, контроль корректности партий и статусов.

        В проект включён аудит действий пользователей на уровне базы данных с хранением снимков изменений в JSONB, а также отчёты по складу, заказам, производству, качеству, отгрузкам и счетам поставщиков. Апробация системы по набору позитивных и негативных сценариев показала работоспособность основных механизмов защиты и прикладной логики.

        Направления дальнейшего развития включают перевод ручной генерации идентификаторов на sequences/IDENTITY, внедрение полноценной миграционной системы, настройку резервного копирования PostgreSQL, использование HTTPS при развёртывании, расширение аналитических отчётов, автоматическую генерацию PDF-форм и написание набора автотестов прикладной логики.
        """,
    )

    heading(body, 1, "СПИСОК ЛИТЕРАТУРЫ")
    bibliography = [
        "Методические указания по выполнению курсовой работы по дисциплине «Безопасность систем баз данных».",
        "PostgreSQL Global Development Group. PostgreSQL Documentation. URL: https://www.postgresql.org/docs/16/ (дата обращения: 11.05.2026).",
        "PostgreSQL Global Development Group. What Is PostgreSQL? URL: https://www.postgresql.org/docs/16/intro-whatis.html (дата обращения: 11.05.2026).",
        "FastAPI Documentation. URL: https://fastapi.tiangolo.com/ (дата обращения: 11.05.2026).",
        "FastAPI. SQL (Relational) Databases. URL: https://fastapi.tiangolo.com/tutorial/sql-databases/ (дата обращения: 11.05.2026).",
        "OWASP Cheat Sheet Series. SQL Injection Prevention Cheat Sheet. URL: https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html (дата обращения: 11.05.2026).",
        "OWASP Foundation. Broken Access Control. URL: https://owasp.org/www-community/Broken_Access_Control (дата обращения: 11.05.2026).",
        "Date C. J. An Introduction to Database Systems. 8th ed. Boston: Pearson Addison Wesley, 2004.",
        "Connolly T., Begg C. Database Systems: A Practical Approach to Design, Implementation, and Management. 6th ed. Harlow: Pearson, 2015.",
        "Silberschatz A., Korth H. F., Sudarshan S. Database System Concepts. 7th ed. New York: McGraw-Hill, 2019.",
        "Bertino E., Sandhu R. Database Security — Concepts, Approaches, and Challenges // IEEE Transactions on Dependable and Secure Computing. 2005. Vol. 2, No. 1. P. 2–19.",
    ]
    for idx, item in enumerate(bibliography, start=1):
        paragraph(body, f"{idx}. {item}")

    heading(body, 1, "ПРИЛОЖЕНИЯ")
    heading(body, 2, "Приложение А. Фрагменты SQL-схемы")
    for line in [
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_invoices_one_active_per_order",
        "ON invoices(order_id)",
        "WHERE status_code IN ('issued', 'overdue', 'paid');",
        "",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_supplier_invoices_delivery_id",
        "ON supplier_invoices(delivery_id);",
    ]:
        code_paragraph(body, line or " ")

    heading(body, 2, "Приложение Б. Фрагмент permission matrix")
    for line in [
        "\"orders.create\": {\"admin\", \"client\"}",
        "\"invoices.pay_own\": {\"client\"}",
        "\"supplier_invoices.pay\": {\"admin\"}",
        "\"shipments.report\": {\"admin\", \"warehouse_worker\", \"client\"}",
        "\"audit.view\": {\"admin\"}",
    ]:
        code_paragraph(body, line)

    heading(body, 2, "Приложение В. Фрагмент Docker Compose")
    for line in [
        "services:",
        "  db:",
        "    image: postgres:16",
        "    ports:",
        "      - \"127.0.0.1:${POSTGRES_PORT:-5432}:5432\"",
        "  web:",
        "    depends_on:",
        "      db:",
        "        condition: service_healthy",
        "    environment:",
        "      DB_HOST: db",
        "      DB_PORT: 5432",
    ]:
        code_paragraph(body, line)

    heading(body, 2, "Приложение Г. Инструкция запуска на Windows")
    for line in [
        "Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass",
        ".\\scripts\\reset_db.ps1",
        ".\\scripts\\start_web.ps1",
        "Сайт: http://localhost:8000",
        "Пользователи: admin/admin123, technologist/tech123, warehouse/warehouse123, quality/quality123, client/client123",
    ]:
        paragraph(body, line)

    heading(body, 2, "Приложение Д. Список подготовленных диаграмм")
    for fig in FIGURES:
        paragraph(body, f"docs/assets/{fig.file_name} — {fig.title}.")

    body.append(sect_pr)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def update_core_properties(package: dict[str, bytes], title: str, subject: str) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    root = ET.Element(qn(CP_NS, "coreProperties"))
    ET.SubElement(root, qn(DC_NS, "creator")).text = "OpenAI Codex"
    ET.SubElement(root, qn(CP_NS, "lastModifiedBy")).text = "OpenAI Codex"
    ET.SubElement(root, qn(DC_NS, "title")).text = title
    ET.SubElement(root, qn(DC_NS, "subject")).text = subject
    ET.SubElement(root, qn(DC_NS, "description")).text = "Курсовой проект по дисциплине «Безопасность систем баз данных»."
    created = ET.SubElement(root, qn(DCTERMS_NS, "created"))
    created.set(qn(XSI_NS, "type"), "dcterms:W3CDTF")
    created.text = now
    modified = ET.SubElement(root, qn(DCTERMS_NS, "modified"))
    modified.set(qn(XSI_NS, "type"), "dcterms:W3CDTF")
    modified.text = now
    package["docProps/core.xml"] = ET.tostring(root, encoding="utf-8", xml_declaration=True)


def build_report_docx() -> None:
    with zipfile.ZipFile(TEMPLATE_PATH) as zf:
        package = {name: zf.read(name) for name in zf.namelist()}
    package["word/document.xml"] = build_report_document_xml()
    update_core_properties(package, "Разработка и защита системы базы данных хлебозавода", "Расчётно-пояснительная записка")
    with zipfile.ZipFile(REPORT_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in package.items():
            zf.writestr(name, content)


def ppt_text_run(text: str, size: int = 1800, bold: bool = False) -> str:
    bold_attr = ' b="1"' if bold else ""
    return (
        f'<a:r><a:rPr lang="ru-RU" sz="{size}"{bold_attr}>'
        f'<a:latin typeface="Times New Roman"/><a:ea typeface="Times New Roman"/><a:cs typeface="Times New Roman"/>'
        f'</a:rPr><a:t>{xml_escape(text)}</a:t></a:r>'
    )


def emu(value_in_inches: float) -> int:
    return int(value_in_inches * 914400)


def slide_shape(shape_id: int, name: str, x: float, y: float, w: float, h: float, paragraphs: list[str], *, title: bool = False, boxed: bool = False) -> str:
    sp_pr = [
        f'<a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>',
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>',
    ]
    if boxed:
        sp_pr.append('<a:solidFill><a:srgbClr val="F4F4F4"/></a:solidFill>')
        sp_pr.append('<a:ln><a:solidFill><a:srgbClr val="3F3F3F"/></a:solidFill></a:ln>')
    else:
        sp_pr.append('<a:noFill/>')
        sp_pr.append('<a:ln><a:noFill/></a:ln>')
    para_xml = []
    for line in paragraphs:
        size = 2400 if title else 1700
        run = ppt_text_run(line, size=size, bold=title)
        para_xml.append(f'<a:p>{run}<a:endParaRPr lang="ru-RU" sz="{size}"/></a:p>')
    return (
        f'<p:sp>'
        f'<p:nvSpPr><p:cNvPr id="{shape_id}" name="{xml_escape(name)}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr>{"".join(sp_pr)}</p:spPr>'
        f'<p:txBody><a:bodyPr wrap="square" anchor="t" rtlCol="0"><a:spAutoFit/></a:bodyPr><a:lstStyle/>{"".join(para_xml)}</p:txBody>'
        f'</p:sp>'
    )


def build_slide_xml(title: str, body_lines: list[str]) -> bytes:
    shapes = [
        slide_shape(2, "Title", 0.55, 0.3, 12.2, 0.7, [title], title=True),
        slide_shape(3, "Body", 0.8, 1.2, 11.7, 5.8, body_lines, boxed=False),
    ]
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        '<p:cSld><p:spTree>'
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        + "".join(shapes)
        + '</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'
    )
    return xml.encode("utf-8")


def build_slide_with_boxes(title: str, boxes: list[tuple[float, float, float, float, list[str]]]) -> bytes:
    extra = [slide_shape(10 + idx, f"Box {idx}", x, y, w, h, lines, boxed=True) for idx, (x, y, w, h, lines) in enumerate(boxes, start=1)]
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        '<p:cSld><p:spTree>'
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        + slide_shape(2, "Title", 0.55, 0.3, 12.2, 0.7, [title], title=True)
        + "".join(extra)
        + '</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'
    )
    return xml.encode("utf-8")


def build_presentation_package() -> dict[str, bytes]:
    with zipfile.ZipFile(TEMPLATE_PATH) as zf:
        theme_data = zf.read("word/theme/theme1.xml")

    slides: list[bytes] = [
        build_slide_xml("Разработка и защита системы базы данных хлебозавода", ["Дисциплина: «Безопасность систем баз данных»", "Курсовой проект Slop-Bakery", "Студент: Девяткин Егор", "Группа: ИУ8-64", "МГТУ им. Н.Э. Баумана, кафедра ИУ8", "Москва, 2026 год"]),
        build_slide_xml("Актуальность темы", ["• база данных хлебозавода хранит коммерческие, технологические и складские сведения;", "• нарушение целостности данных приводит к ошибкам производства, счётов и отгрузок;", "• при наличии нескольких ролей возникает риск несанкционированного доступа;", "• требуется защита от обхода интерфейсных ограничений и прямых URL-запросов;", "• автоматизация снижает трудоёмкость работы и повышает управляемость предприятия."]),
        build_slide_xml("Цель и задачи проекта", ["Цель: разработка и защита системы базы данных хлебозавода Slop-Bakery.", "• спроектировать реляционную схему PostgreSQL;", "• реализовать веб-интерфейс на FastAPI и Jinja2;", "• построить ролевую модель доступа и action-level permissions;", "• обеспечить контроль целостности и статусов бизнес-процессов;", "• реализовать аудит действий, отчёты и сценарии проверки защищённости."]),
        build_slide_with_boxes("Предметная область", [(0.7, 1.6, 1.6, 0.8, ["Поставщики"]), (2.45, 1.6, 1.4, 0.8, ["Сырьё"]), (4.0, 1.6, 1.8, 0.8, ["Поставки"]), (5.95, 1.6, 1.8, 0.8, ["Производство"]), (7.9, 1.6, 1.5, 0.8, ["Качество"]), (9.55, 1.6, 1.4, 0.8, ["Склад ГП"]), (11.1, 1.6, 1.5, 0.8, ["Заказ"]), (1.5, 3.1, 2.0, 0.9, ["Счёт клиента", "и оплата"]), (4.0, 3.1, 2.2, 0.9, ["Счёт поставщика"]), (7.0, 3.1, 2.1, 0.9, ["Отгрузка"]), (9.8, 3.1, 2.1, 0.9, ["Аудит действий"]), (1.0, 4.8, 11.0, 1.0, ["Поток: поставщики → сырьё → поставка → производство → качество → склад → заказ → счёт → оплата → отгрузка"])]),
        build_slide_xml("Роли пользователей", ["• admin — полный доступ, аудит, пользователи и роли, изменение статусов;", "• client — личный кабинет, собственные заказы, свои счета и отгрузки, оплата счета;", "• technologist — продукция, техкарты, рецептуры, производство, производственные отчёты;", "• warehouse_worker — поставки, склад сырья, склад готовой продукции, отгрузки, supplier invoices (просмотр);", "• quality_control — контроль качества сырья и готовой продукции, профильные отчёты."]),
        build_slide_xml("Разграничение доступа", ["• навигация строится по SECTION_RULES;", "• критичные операции проверяются по ACTION_RULES;", "• client не видит audit, reports, tech cards и внутренние данные предприятия;", "• warehouse_worker не оплачивает счета поставщиков и не управляет ролями;", "• quality_control не имеет доступа к заказам, счетам и отгрузкам;", "• direct URL и прямые POST-запросы защищены серверными проверками."]),
        build_slide_xml("Концептуальная модель", ["• клиентский контур: customers, customer_orders, order_items, invoices, shipments;", "• поставочный контур: suppliers, supplier_materials, raw_material_deliveries, delivery_items, supplier_invoices;", "• производственный контур: products, tech_cards, recipe_items, production_batches, finished_goods_stock;", "• контур качества: quality_checks для сырья и готовой продукции;", "• контур безопасности: users, roles, user_roles, role_permissions, audit_log;", "• подробная ER-диаграмма сохранена в docs/assets/er_diagram.svg."]),
        build_slide_xml("Логическая модель БД", ["• все связи M:N реализованы через промежуточные таблицы;", "• номенклатура продукции отделена от технологических карт;", "• заголовки документов отделены от их составов: orders/order_items, deliveries/delivery_items, shipments/shipment_items;", "• для клиентских и поставочных счетов применены отдельные сущности invoices и supplier_invoices;", "• статусы вынесены в справочники и используются через внешние ключи."]),
        build_slide_xml("Физическая реализация", ["• PostgreSQL 16, BIGINT primary keys, foreign keys, UNIQUE, CHECK, DEFAULT;", "• индексы по внешним ключам и операционным полям (даты, статусы, batch_number);", "• partial unique index запрещает повторный client invoice по одному order_id;", "• partial unique index допускает только одну active tech card для продукта;", "• JSONB-аудит хранит old_data и new_data для ключевых таблиц."]),
        build_slide_xml("Архитектура приложения", ["• уровень представления: HTML/Jinja2, серверный рендеринг, формы и отчёты;", "• уровень приложения: FastAPI, routers, auth, permissions, транзакции, бизнес-логика;", "• уровень данных: PostgreSQL, триггеры, ограничения, SQL-роли, аудит;", "• инфраструктура: Docker Compose, контейнеры db и web, PowerShell-скрипты для Windows;", "• веб-интерфейс доступен по адресу http://localhost:8000."]),
        build_slide_xml("Основные бизнес-сценарии", ["• клиент создаёт заказ и добавляет позиции только в draft;", "• администратор подтверждает заказ и выставляет клиентский счёт;", "• клиент оплачивает свой invoice, после чего заказ может перейти к отгрузке;", "• технолог запускает производство по active tech card и при наличии годного сырья;", "• ОТК проверяет сырьё и готовую продукцию;", "• склад оформляет shipment и списывает готовую продукцию со склада."]),
        build_slide_xml("Ограничения целостности", ["• нельзя отгрузить неоплаченный заказ;", "• нельзя создать несколько активных/оплаченных client invoices по одному заказу;", "• нельзя использовать сырьё без passed quality inspection;", "• нельзя отгружать готовую продукцию без passed quality inspection;", "• нельзя сформировать отрицательные остатки сырья и готовой продукции;", "• нельзя нарушить серверные матрицы переходов статусов."]),
        build_slide_xml("Средства защиты", ["• авторизация по users и хранение password_hash вместо открытых паролей;", "• SessionMiddleware и проверка текущего пользователя в FastAPI;", "• action-level permissions для критичных действий;", "• параметризованные SQL-запросы через psycopg;", "• триггерный аудит INSERT/UPDATE/DELETE/LOGIN/LOGOUT;", "• разграничение SQL-ролей PostgreSQL и GRANT по принципу минимально необходимых прав."]),
        build_slide_with_boxes("Пользовательский интерфейс", [(0.8, 1.5, 2.8, 1.8, ["TODO", "Скриншот", "dashboard"]), (3.8, 1.5, 2.8, 1.8, ["TODO", "Скриншот", "заказа клиента"]), (6.8, 1.5, 2.8, 1.8, ["TODO", "Скриншот", "производства"]), (9.8, 1.5, 2.8, 1.8, ["TODO", "Скриншот", "отгрузки / аудита"]), (0.9, 4.0, 11.8, 1.5, ["После ручного запуска приложения рекомендуется заменить плейсхолдеры фактическими скриншотами интерфейса.", "Подходящие формы перечислены в разделе 8 расчётно-пояснительной записки."])]),
        build_slide_xml("Запросы и отчёты", ["• реализованы проверочные SQL-запросы по остаткам, заказам, качеству, счетам и отгрузкам;", "• отчёты фильтруются по ролям: admin, technologist, warehouse_worker, quality_control;", "• отдельный отчёт по shipment доступен как печатная форма конкретной отгрузки;", "• в admin-отчётах отражаются счета поставщиков, задолженность и оплаты за период;", "• client не имеет доступа к внутренним отчётам предприятия."]),
        build_slide_xml("Исследование защищённости", ["• client получает 403 при доступе к /audit и /admin/users;", "• client не может подменить unit_price и status_code при создании заказа;", "• warehouse_worker не отгружает неоплаченный заказ;", "• повторный invoice по одному заказу запрещён сервером и индексом;", "• failed quality blocks production and shipment operations;", "• shipment и production не допускают отрицательных складских остатков."]),
        build_slide_xml("Демонстрационный сценарий", ["1. client создаёт заказ и добавляет продукцию из доступного остатка.", "2. admin подтверждает заказ и создаёт клиентский invoice.", "3. client оплачивает счёт.", "4. technologist создаёт или завершает производственную партию.", "5. quality_control фиксирует passed quality check.", "6. warehouse_worker создаёт shipment и формирует shipment report.", "7. admin просматривает аудит действий."]),
        build_slide_xml("Результаты проекта", ["• реализована защищённая PostgreSQL-база данных хлебозавода;", "• разработан локальный веб-интерфейс Slop-Bakery на FastAPI;", "• внедрена ролевая модель и action-level permissions;", "• реализованы ограничения целостности и матрицы статусов;", "• добавлены audit_log, клиентские и поставочные счета, отчёты и печатная форма отгрузки."]),
        build_slide_xml("Заключение", ["• цель курсовой работы достигнута;", "• система обеспечивает безопасное хранение и обработку данных хлебозавода;", "• прикладная логика защищает ключевые бизнес-операции от некорректных действий;", "• направления развития: миграции, резервное копирование, HTTPS, автотесты, PDF-отчёты, расширенная аналитика."]),
    ]

    package: dict[str, bytes] = {}
    slide_count = len(slides)
    ct = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">', '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>', '<Default Extension="xml" ContentType="application/xml"/>', '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>', '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>', '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>', '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>', '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>', '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>', '<Override PartName="/ppt/presProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presProps+xml"/>', '<Override PartName="/ppt/viewProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.viewProps+xml"/>', '<Override PartName="/ppt/tableStyles.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.tableStyles+xml"/>']
    for idx in range(1, slide_count + 1):
        ct.append(f'<Override PartName="/ppt/slides/slide{idx}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>')
    ct.append("</Types>")
    package["[Content_Types].xml"] = "\n".join(ct).encode("utf-8")
    package["_rels/.rels"] = textwrap.dedent("""\
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
          <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
          <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
          <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
        </Relationships>
        """).encode("utf-8")
    core = {}
    update_core_properties(core, "БСБД презентация Slop-Bakery", "Презентация для защиты")
    package["docProps/core.xml"] = core["docProps/core.xml"]
    package["docProps/app.xml"] = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>Microsoft Office PowerPoint</Application><Slides>{slide_count}</Slides><Notes>0</Notes><HiddenSlides>0</HiddenSlides><MMClips>0</MMClips><PresentationFormat>Custom</PresentationFormat></Properties>'.encode("utf-8")
    pres_xml = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', '<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">', '<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>', '<p:sldIdLst>']
    for idx in range(1, slide_count + 1):
        pres_xml.append(f'<p:sldId id="{255 + idx}" r:id="rId{idx + 1}"/>')
    pres_xml.extend(['</p:sldIdLst>', '<p:sldSz cx="12192000" cy="6858000"/>', '<p:notesSz cx="6858000" cy="9144000"/>', '</p:presentation>'])
    package["ppt/presentation.xml"] = "\n".join(pres_xml).encode("utf-8")
    pres_rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">', '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>']
    for idx in range(1, slide_count + 1):
        pres_rels.append(f'<Relationship Id="rId{idx + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{idx}.xml"/>')
    pres_rels.append("</Relationships>")
    package["ppt/_rels/presentation.xml.rels"] = "\n".join(pres_rels).encode("utf-8")
    package["ppt/theme/theme1.xml"] = theme_data
    package["ppt/slideMasters/slideMaster1.xml"] = textwrap.dedent("""\
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld name="Slide Master"><p:bg><p:bgPr><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill><a:effectLst/></p:bgPr></p:bg><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld><p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/><p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst><p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles></p:sldMaster>
        """).encode("utf-8")
    package["ppt/slideMasters/_rels/slideMaster1.xml.rels"] = textwrap.dedent("""\
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
          <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
          <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
        </Relationships>
        """).encode("utf-8")
    package["ppt/slideLayouts/slideLayout1.xml"] = textwrap.dedent("""\
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1"><p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>
        """).encode("utf-8")
    package["ppt/slideLayouts/_rels/slideLayout1.xml.rels"] = textwrap.dedent("""\
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
          <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
        </Relationships>
        """).encode("utf-8")
    package["ppt/presProps.xml"] = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:presentationPr xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>'
    package["ppt/viewProps.xml"] = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:viewPr xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:normalViewPr/><p:slideViewPr/><p:outlineViewPr/><p:notesTextViewPr/><p:gridSpacing cx="72008" cy="72008"/></p:viewPr>'
    package["ppt/tableStyles.xml"] = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><a:tblStyleLst xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" def="{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}"/>'
    for idx, slide in enumerate(slides, start=1):
        package[f"ppt/slides/slide{idx}.xml"] = slide
        package[f"ppt/slides/_rels/slide{idx}.xml.rels"] = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/></Relationships>'
    return package


def build_presentation() -> None:
    package = build_presentation_package()
    with zipfile.ZipFile(PRESENTATION_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in package.items():
            zf.writestr(name, content)


def verify_office_zip(path: Path, must_have: list[str]) -> None:
    with zipfile.ZipFile(path) as zf:
        missing = [item for item in must_have if item not in set(zf.namelist())]
        if missing:
            raise RuntimeError(f"В файле {path.name} отсутствуют обязательные части: {missing}")


def main() -> None:
    generated_assets = generate_assets()
    build_report_docx()
    build_presentation()
    verify_office_zip(REPORT_PATH, ["word/document.xml", "[Content_Types].xml", "docProps/core.xml"])
    verify_office_zip(PRESENTATION_PATH, ["ppt/presentation.xml", "[Content_Types].xml", "docProps/core.xml"])
    print("Generated assets:")
    for asset in generated_assets:
        print(asset.relative_to(ROOT).as_posix())
    print("Generated report: docs/report.docx")
    print("Generated presentation: docs/presentation.pptx")


if __name__ == "__main__":
    main()

import re
from decimal import Decimal
from html import escape
from io import BytesIO
from pathlib import Path

from django.core.exceptions import ObjectDoesNotExist
from django.utils.text import slugify
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .models import PriceList

BRAND = colors.HexColor("#0F766E")
BRAND_DARK = colors.HexColor("#134E4A")
INK = colors.HexColor("#172033")
MUTED = colors.HexColor("#64748B")
LINE = colors.HexColor("#D7DEE8")
SURFACE = colors.HexColor("#F8FAFC")

TRANSLATIONS = {
    "uz": {
        "price_list": "NARXLAR RO'YXATI",
        "product_list": "MAHSULOTLAR RO'YXATI",
        "article": "Artikul",
        "product": "Mahsulot va xususiyatlar",
        "quantity": "Miqdor",
        "unit": "Birlik",
        "price": "Narx",
        "minimum": "Minimal buyurtma",
        "loading": "Yuklash",
        "empty": "Mahsulotlar kiritilmagan",
        "category": "Yo'nalish",
        "valid": "Amal qilish",
        "delivery": "YETKAZISH SHARTI",
        "payment": "TO'LOV SHARTI",
        "alternative": "Muqobil yetkazish",
        "agreement": "Kelishuv asosida",
        "valid_sentence": "Taklif {date} sanasigacha amal qiladi.",
        "page": "{page}-sahifa",
        "responsible": "Mas'ul shaxs",
    },
    "ru": {
        "price_list": "ПРАЙС-ЛИСТ",
        "product_list": "ПРОДУКТ-ЛИСТ",
        "article": "Артикул",
        "product": "Продукт и характеристики",
        "quantity": "Количество",
        "unit": "Ед.",
        "price": "Цена",
        "minimum": "Мин. заказ",
        "loading": "Отгрузка",
        "empty": "Продукты не добавлены",
        "category": "Направление",
        "valid": "Срок действия",
        "delivery": "УСЛОВИЯ ПОСТАВКИ",
        "payment": "УСЛОВИЯ ОПЛАТЫ",
        "alternative": "Альтернативная поставка",
        "agreement": "По договоренности",
        "valid_sentence": "Предложение действительно до {date}.",
        "page": "Страница {page}",
        "responsible": "Ответственное лицо",
    },
    "en": {
        "price_list": "PRICE LIST",
        "product_list": "PRODUCT LIST",
        "article": "Article",
        "product": "Product and specifications",
        "quantity": "Quantity",
        "unit": "Unit",
        "price": "Price",
        "minimum": "Minimum order",
        "loading": "Loading",
        "empty": "No products added",
        "category": "Category",
        "valid": "Valid until",
        "delivery": "DELIVERY TERMS",
        "payment": "PAYMENT TERMS",
        "alternative": "Alternative delivery",
        "agreement": "By agreement",
        "valid_sentence": "This offer is valid until {date}.",
        "page": "Page {page}",
        "responsible": "Responsible person",
    },
}


def _register_fonts():
    regular_candidates = (
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
    )
    bold_candidates = (
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
    )
    regular = next((path for path in regular_candidates if path.exists()), None)
    bold = next((path for path in bold_candidates if path.exists()), None)
    if regular and bold:
        if "BCRM" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("BCRM", str(regular)))
            pdfmetrics.registerFont(TTFont("BCRM-Bold", str(bold)))
        return "BCRM", "BCRM-Bold"
    return "Helvetica", "Helvetica-Bold"


def _paragraph(value, style):
    text = escape(str(value or "")).replace("\n", "<br/>")
    return Paragraph(text or "-", style)


def _number(value, places=2):
    rendered = f"{Decimal(value or 0):,.{places}f}"
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def _image(field_file, max_width, max_height):
    if not field_file:
        return None
    try:
        field_file.open("rb")
        data = BytesIO(field_file.read())
        field_file.close()
        image = Image(data)
        ratio = min(max_width / image.imageWidth, max_height / image.imageHeight)
        image.drawWidth = image.imageWidth * ratio
        image.drawHeight = image.imageHeight * ratio
        return image
    except (OSError, ValueError):
        return None


def _product_specification(product):
    values = []
    try:
        yarn = product.yarn_specification
    except ObjectDoesNotExist:
        yarn = None
    try:
        woven = product.woven_specification
    except ObjectDoesNotExist:
        woven = None

    if yarn:
        values.extend(
            (
                yarn.yarn_count,
                yarn.composition,
                yarn.get_preparation_display(),
                yarn.get_spinning_method_display(),
                "Compact" if yarn.is_compact else "",
            )
        )
    elif woven:
        values.extend(
            (
                woven.composition,
                f"{_number(woven.width_cm)} cm" if woven.width_cm else "",
                f"{woven.gsm} GSM" if woven.gsm else "",
                woven.weave,
                f"{woven.warp_yarn} / {woven.weft_yarn}".strip(" /"),
            )
        )
    else:
        if product.fabric_id:
            values.extend(
                (
                    product.fabric.composition,
                    f"{product.fabric.gsm} GSM" if product.fabric.gsm else "",
                    f"{_number(product.fabric.width_cm)} cm"
                    if product.fabric.width_cm
                    else "",
                )
            )
        values.extend((product.yarn_count, product.get_finish_display()))
    return " | ".join(str(value) for value in values if value)


def price_list_pdf_filename(price_list):
    number = re.sub(r"[^A-Za-z0-9_-]+", "-", price_list.number).strip("-")
    document_type = price_list.document_type.replace("_", "-")
    title = slugify(price_list.title)[:45]
    suffix = f"_{title}" if title else ""
    return f"{number or 'offer'}_{document_type}{suffix}.pdf"


def build_price_list_pdf(price_list):
    regular_font, bold_font = _register_fonts()
    organization = price_list.organization
    words = TRANSLATIONS.get(price_list.language, TRANSLATIONS["uz"])
    default_title = words[price_list.document_type]
    document_title = price_list.title or default_title
    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=10 * mm,
        bottomMargin=16 * mm,
        title=f"{document_title} {price_list.number}",
        author=organization.document_name,
    )
    sample = getSampleStyleSheet()
    body = ParagraphStyle(
        "Body", parent=sample["BodyText"], fontName=regular_font,
        fontSize=9, leading=13, textColor=INK,
    )
    small = ParagraphStyle(
        "Small", parent=body, fontSize=7.5, leading=10, textColor=MUTED,
    )
    heading = ParagraphStyle(
        "Heading", parent=body, fontName=bold_font, fontSize=10,
        leading=13, textColor=BRAND_DARK,
    )
    title = ParagraphStyle(
        "Title", parent=body, fontName=bold_font, fontSize=16,
        leading=19, textColor=BRAND, alignment=TA_RIGHT,
    )
    table_header = ParagraphStyle(
        "TableHeader", parent=small, fontName=bold_font,
        textColor=colors.white, alignment=TA_CENTER,
    )
    table_text = ParagraphStyle("TableText", parent=small, textColor=INK)
    table_number = ParagraphStyle(
        "TableNumber", parent=small, textColor=INK, alignment=TA_RIGHT,
    )

    story = []
    logo = _image(organization.logo, 42 * mm, 20 * mm)
    company_lines = [f"<b>{escape(organization.document_name)}</b>"]
    if organization.tax_id:
        company_lines.append(f"STIR: {escape(organization.tax_id)}")
    for value in (organization.phone, organization.email):
        if value:
            company_lines.append(escape(value))
    company_details = Paragraph("<br/>".join(company_lines), body)
    company_block = Table([[logo, company_details]] if logo else [[company_details]])
    company_block.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    document_meta = [
        _paragraph(document_title, title),
        _paragraph(f"№ {price_list.number}", table_number),
        _paragraph(price_list.issue_date.strftime("%d.%m.%Y"), table_number),
    ]
    header = Table([[company_block, document_meta]], colWidths=[105 * mm, 56 * mm])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 1.4, BRAND),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.extend((header, Spacer(1, 5 * mm)))

    address_values = []
    for name, value in (
        ("Yuridik manzil", organization.legal_address),
        ("Bank", organization.bank_name),
        ("Hisob raqami", organization.bank_account),
        ("MFO", organization.bank_code),
    ):
        if value:
            address_values.append((name, value))
    if address_values:
        cells = [
            Paragraph(
                f"<font color='#134E4A'><b>{escape(name)}</b></font><br/>"
                f"{escape(str(value))}", body,
            )
            for name, value in address_values
        ]
        if len(cells) % 2:
            cells.append("")
        info = Table(
            [cells[index:index + 2] for index in range(0, len(cells), 2)],
            colWidths=[80.5 * mm, 80.5 * mm],
        )
        info.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
            ("BOX", (0, 0), (-1, -1), 0.5, LINE),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, LINE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.extend((info, Spacer(1, 3 * mm)))

    meta_values = []
    if price_list.category:
        meta_values.append(f"{words['category']}: {price_list.get_category_display()}")
    if price_list.valid_until:
        meta_values.append(
            f"{words['valid']}: {price_list.valid_until.strftime('%d.%m.%Y')}"
        )
    if meta_values:
        story.extend((_paragraph(" · ".join(meta_values), small), Spacer(1, 3 * mm)))
    if price_list.document_intro:
        story.extend((_paragraph(price_list.document_intro, body), Spacer(1, 4 * mm)))

    is_price_list = price_list.document_type == PriceList.DocumentType.PRICE_LIST
    last_heading = words["price"] if is_price_list else words["minimum"]
    rows = [[
        _paragraph("№", table_header),
        _paragraph(words["article"], table_header),
        _paragraph(words["product"], table_header),
        _paragraph(words["quantity"], table_header),
        _paragraph(words["unit"], table_header),
        _paragraph(last_heading, table_header),
        _paragraph(words["loading"], table_header),
    ]]
    for index, line in enumerate(price_list.lines.all(), start=1):
        product_text = f"<b>{escape(line.product.name)}</b>"
        if line.color or line.size:
            variant_text = " / ".join(
                escape(str(value)) for value in (line.color, line.size) if value
            )
            product_text += f"<br/><font color='#0F766E'>{variant_text}</font>"
        specification = _product_specification(line.product)
        if specification:
            product_text += f"<br/><font color='#64748B'>{escape(specification)}</font>"
        description = line.description_snapshot or line.product.description
        if description:
            product_text += f"<br/>{escape(description)}"
        value = line.unit_price if is_price_list else line.minimum_order_quantity
        if value is None:
            value_text = "-"
        else:
            value_text = _number(value, 4 if is_price_list else 3)
            if is_price_list:
                value_text = f"{value_text} {price_list.currency}"
        product_cell = Paragraph(product_text, table_text)
        line_image = _image(line.image or line.product.image, 18 * mm, 18 * mm)
        if line_image:
            product_cell = [line_image, product_cell]
        rows.append([
            _paragraph(index, table_number),
            _paragraph(line.product.article, table_text),
            product_cell,
            _paragraph(
                _number(line.available_quantity, 3)
                if line.available_quantity is not None else "-",
                table_number,
            ),
            _paragraph(line.get_unit_display(), table_text),
            _paragraph(value_text, table_number),
            _paragraph(
                line.planned_loading_date.strftime("%d.%m.%Y")
                if line.planned_loading_date else "-",
                table_text,
            ),
        ])
    if len(rows) == 1:
        rows.append(["", "", _paragraph(words["empty"], table_text), "", "", "", ""])
    products = Table(
        rows,
        colWidths=[8 * mm, 20 * mm, 60 * mm, 18 * mm, 15 * mm, 22 * mm, 20 * mm],
        repeatRows=1,
        hAlign="LEFT",
    )
    products.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SURFACE]),
    ]))
    story.extend((products, Spacer(1, 5 * mm)))

    delivery = price_list.delivery_basis or organization.default_delivery_terms
    payment = price_list.payment_terms or organization.default_payment_terms
    delivery_detail = delivery or words["agreement"]
    if price_list.incoterms_version:
        delivery_detail += f"\nIncoterms {price_list.incoterms_version}"
    if price_list.alternative_delivery_terms:
        delivery_detail += (
            f"\n{words['alternative']}: {price_list.alternative_delivery_terms}"
        )
    if price_list.valid_until:
        delivery_detail += "\n" + words["valid_sentence"].format(
            date=price_list.valid_until.strftime("%d.%m.%Y")
        )
    payment_detail = payment or words["agreement"]
    if price_list.notes:
        payment_detail += f"\n{price_list.notes}"
    signature = _image(organization.signature_image, 35 * mm, 18 * mm)
    stamp = _image(organization.stamp_image, 35 * mm, 22 * mm)
    if organization.director_name and not signature and not stamp:
        payment_detail += f"\n{organization.director_name}"
    terms = Table(
        [
            [_paragraph(words["delivery"], heading), _paragraph(words["payment"], heading)],
            [_paragraph(delivery_detail, body), _paragraph(payment_detail, body)],
        ],
        colWidths=[80.5 * mm, 80.5 * mm],
    )
    terms.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, LINE),
        ("BACKGROUND", (0, 0), (-1, 0), SURFACE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.extend((terms, Spacer(1, 4 * mm)))
    if signature or stamp:
        approval = Table(
            [[
                _paragraph(organization.director_name or words["responsible"], body),
                signature or "",
                stamp or "",
            ]],
            colWidths=[70 * mm, 42 * mm, 42 * mm],
        )
        approval.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(KeepTogether([Spacer(1, 5 * mm), approval]))

    footer_text = price_list.document_footer or organization.document_footer

    def draw_page(canvas, document):
        canvas.saveState()
        canvas.setTitle(f"{document_title} {price_list.number}")
        canvas.setAuthor(organization.document_name)
        canvas.setFont(regular_font, 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(16 * mm, 9 * mm, organization.document_name)
        canvas.drawRightString(
            A4[0] - 16 * mm, 9 * mm, words["page"].format(page=document.page)
        )
        if footer_text:
            compact_footer = " ".join(footer_text.split())
            if len(compact_footer) > 150:
                compact_footer = f"{compact_footer[:147]}..."
            canvas.setFont(regular_font, 6.8)
            canvas.drawCentredString(A4[0] / 2, 13 * mm, compact_footer)
        canvas.restoreState()

    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    return output.getvalue()

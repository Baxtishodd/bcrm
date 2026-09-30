import re
from decimal import Decimal
from html import escape
from io import BytesIO
from pathlib import Path

from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
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

BRAND = colors.HexColor("#0F766E")
BRAND_DARK = colors.HexColor("#134E4A")
INK = colors.HexColor("#172033")
MUTED = colors.HexColor("#64748B")
LINE = colors.HexColor("#D7DEE8")
SURFACE = colors.HexColor("#F8FAFC")


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
    decimal_value = Decimal(value or 0)
    rendered = f"{decimal_value:,.{places}f}"
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


def _product_specification(line):
    product = line.product
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
                f"{_number(woven.width_cm)} cm",
                f"{woven.gsm} GSM",
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
                    (f"{_number(product.fabric.width_cm)} cm" if product.fabric.width_cm else ""),
                )
            )
        values.extend((product.yarn_count, product.get_finish_display()))

    if line.variant_id:
        values.append(str(line.variant))
    return " | ".join(str(value) for value in values if value)


def quotation_pdf_filename(quotation):
    number = re.sub(r"[^A-Za-z0-9_-]+", "-", quotation.number).strip("-")
    customer = slugify(quotation.customer.name) or f"customer-{quotation.customer_id}"
    return f"{number or 'quotation'}_{customer}.pdf"


def build_quotation_pdf(quotation):
    regular_font, bold_font = _register_fonts()
    organization = quotation.organization
    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title=f"{quotation.document_title} {quotation.number}",
        author=organization.document_name,
    )
    sample = getSampleStyleSheet()
    body = ParagraphStyle(
        "Body",
        parent=sample["BodyText"],
        fontName=regular_font,
        fontSize=9,
        leading=13,
        textColor=INK,
    )
    small = ParagraphStyle(
        "Small",
        parent=body,
        fontSize=7.5,
        leading=10,
        textColor=MUTED,
    )
    label = ParagraphStyle(
        "Label",
        parent=small,
        fontName=bold_font,
        textColor=BRAND_DARK,
        spaceAfter=2,
    )
    title = ParagraphStyle(
        "Title",
        parent=body,
        fontName=bold_font,
        fontSize=16,
        leading=19,
        textColor=BRAND,
        alignment=TA_RIGHT,
    )
    heading = ParagraphStyle(
        "Heading",
        parent=body,
        fontName=bold_font,
        fontSize=10,
        leading=13,
        textColor=BRAND_DARK,
    )
    table_header = ParagraphStyle(
        "TableHeader",
        parent=small,
        fontName=bold_font,
        textColor=colors.white,
        alignment=TA_CENTER,
    )
    table_text = ParagraphStyle("TableText", parent=small, textColor=INK)
    table_number = ParagraphStyle("TableNumber", parent=small, textColor=INK, alignment=TA_RIGHT)

    story = []
    logo = _image(organization.logo, 42 * mm, 20 * mm)
    company_lines = [f"<b>{escape(organization.document_name)}</b>"]
    if organization.tax_id:
        company_lines.append(f"STIR: {escape(organization.tax_id)}")
    if organization.phone:
        company_lines.append(escape(organization.phone))
    if organization.email:
        company_lines.append(escape(organization.email))
    company_details = Paragraph("<br/>".join(company_lines), body)
    company_block = Table([[logo, company_details]] if logo else [[company_details]])
    company_block.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    document_meta = [
        _paragraph(quotation.document_title, title),
        _paragraph(f"№ {quotation.number}", table_number),
        _paragraph(
            timezone.localtime(quotation.created_at).strftime("%d.%m.%Y"),
            table_number,
        ),
    ]
    header = Table([[company_block, document_meta]], colWidths=[105 * mm, 56 * mm])
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 1.4, BRAND),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.extend((header, Spacer(1, 8 * mm)))

    address_values = []
    if organization.legal_address:
        address_values.append(("Yuridik manzil", organization.legal_address))
    if organization.bank_name:
        address_values.append(("Bank", organization.bank_name))
    if organization.bank_account:
        address_values.append(("Hisob raqami", organization.bank_account))
    if organization.bank_code:
        address_values.append(("MFO", organization.bank_code))
    if address_values:
        address_cells = [
            Paragraph(
                f"<font color='#134E4A'><b>{escape(name)}</b></font><br/>{escape(str(value))}",
                body,
            )
            for name, value in address_values
        ]
        if len(address_cells) % 2:
            address_cells.append("")
        address_rows = [
            address_cells[index : index + 2] for index in range(0, len(address_cells), 2)
        ]
        address_table = Table(address_rows, colWidths=[80.5 * mm, 80.5 * mm])
        address_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
                    ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, LINE),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.extend((address_table, Spacer(1, 5 * mm)))

    recipient_rows = [[_paragraph("MIJOZ", label), _paragraph(quotation.customer.name, body)]]
    if quotation.contact:
        recipient_rows.append(
            [_paragraph("KONTAKT", label), _paragraph(quotation.contact.full_name, body)]
        )
    if quotation.customer.address:
        recipient_rows.append(
            [_paragraph("MANZIL", label), _paragraph(quotation.customer.address, body)]
        )
    recipient = Table(recipient_rows, colWidths=[28 * mm, 133 * mm])
    recipient.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.extend((recipient, Spacer(1, 4 * mm)))
    if quotation.document_intro:
        story.extend((_paragraph(quotation.document_intro, body), Spacer(1, 4 * mm)))

    rows = [
        [
            _paragraph("№", table_header),
            _paragraph("Artikul", table_header),
            _paragraph("Mahsulot va xususiyatlar", table_header),
            _paragraph("Miqdor", table_header),
            _paragraph("Birlik", table_header),
            _paragraph("Narx", table_header),
            _paragraph("Jami", table_header),
        ]
    ]
    for index, line in enumerate(quotation.lines.all(), start=1):
        product_text = f"<b>{escape(line.product.name)}</b>"
        specification = _product_specification(line)
        if specification:
            product_text += f"<br/><font color='#64748B'>{escape(specification)}</font>"
        if line.description:
            product_text += f"<br/>{escape(line.description)}"
        rows.append(
            [
                _paragraph(index, table_number),
                _paragraph(line.product.article, table_text),
                Paragraph(product_text, table_text),
                _paragraph(_number(line.quantity, 3), table_number),
                _paragraph(line.product.get_unit_display(), table_text),
                _paragraph(_number(line.unit_price), table_number),
                _paragraph(_number(line.line_total), table_number),
            ]
        )
    if len(rows) == 1:
        rows.append(
            [
                "",
                "",
                _paragraph("Mahsulotlar kiritilmagan", table_text),
                "",
                "",
                "",
                "",
            ]
        )
    product_table = Table(
        rows,
        colWidths=[8 * mm, 21 * mm, 57 * mm, 18 * mm, 17 * mm, 20 * mm, 22 * mm],
        repeatRows=1,
        hAlign="LEFT",
    )
    product_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BRAND),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SURFACE]),
            ]
        )
    )
    story.extend((product_table, Spacer(1, 5 * mm)))

    totals = [
        ["Oraliq jami", f"{_number(quotation.subtotal)} {quotation.currency}"],
        [
            f"Chegirma ({_number(quotation.discount_percent)}%)",
            f"-{_number(quotation.discount_amount)} {quotation.currency}",
        ],
        [
            f"Soliq ({_number(quotation.tax_percent)}%)",
            f"{_number(quotation.tax_amount)} {quotation.currency}",
        ],
        ["UMUMIY", f"{_number(quotation.total)} {quotation.currency}"],
    ]
    totals_table = Table(
        [[_paragraph(name, body), _paragraph(value, table_number)] for name, value in totals],
        colWidths=[50 * mm, 42 * mm],
        hAlign="RIGHT",
    )
    totals_table.setStyle(
        TableStyle(
            [
                ("LINEABOVE", (0, -1), (-1, -1), 1.2, BRAND_DARK),
                ("FONTNAME", (0, -1), (-1, -1), bold_font),
                ("BACKGROUND", (0, -1), (-1, -1), SURFACE),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend((totals_table, Spacer(1, 6 * mm)))

    delivery_terms = quotation.delivery_terms or organization.default_delivery_terms
    payment_terms = quotation.payment_terms or organization.default_payment_terms
    conditions = [
        [
            _paragraph("YETKAZISH SHARTI", heading),
            _paragraph("TO'LOV SHARTI", heading),
        ],
        [
            _paragraph(delivery_terms or "Kelishuv asosida", body),
            _paragraph(payment_terms or "Kelishuv asosida", body),
        ],
    ]
    if organization.default_incoterm:
        conditions[1][0] = _paragraph(
            f"{delivery_terms or 'Kelishuv asosida'}\nIncoterm: {organization.default_incoterm}",
            body,
        )
    terms_table = Table(conditions, colWidths=[80.5 * mm, 80.5 * mm])
    terms_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, LINE),
                ("BACKGROUND", (0, 0), (-1, 0), SURFACE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend((terms_table, Spacer(1, 5 * mm)))

    if quotation.valid_until:
        story.append(
            _paragraph(
                f"Taklif {quotation.valid_until.strftime('%d.%m.%Y')} sanasigacha amal qiladi.",
                body,
            )
        )
    if quotation.notes:
        story.extend((Spacer(1, 2 * mm), _paragraph(quotation.notes, body)))

    footer_text = quotation.document_footer or organization.document_footer
    signature = _image(organization.signature_image, 35 * mm, 18 * mm)
    stamp = _image(organization.stamp_image, 35 * mm, 22 * mm)
    if organization.director_name or signature or stamp:
        approval_cells = [
            _paragraph(organization.director_name or "Mas'ul shaxs", body),
            signature or "",
            stamp or "",
        ]
        approval = Table([approval_cells], colWidths=[70 * mm, 42 * mm, 42 * mm])
        approval.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                    ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        story.append(KeepTogether([Spacer(1, 5 * mm), approval]))

    def draw_page(canvas, document):
        canvas.saveState()
        canvas.setTitle(f"{quotation.document_title} {quotation.number}")
        canvas.setAuthor(organization.document_name)
        canvas.setFont(regular_font, 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(16 * mm, 9 * mm, organization.document_name)
        canvas.drawRightString(
            A4[0] - 16 * mm,
            9 * mm,
            f"{document.page}-sahifa",
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

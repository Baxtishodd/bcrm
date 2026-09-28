import posixpath
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.customers.models import Contact, CustomerCompany
from apps.organizations.models import Organization


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\s()\-]{6,}\d)(?!\d)")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
LEGAL_FORMS = {"ooo", "ооо", "llc", "ltd", "srl", "mchj", "мчж", "ип"}

STATUS_PRIORITY = {
    CustomerCompany.RelationshipStatus.REJECTED: 0,
    CustomerCompany.RelationshipStatus.POTENTIAL: 1,
    CustomerCompany.RelationshipStatus.OFFER_SENT: 2,
    CustomerCompany.RelationshipStatus.WORKING: 3,
}


def clean_text(value):
    if value is None:
        return ""
    return re.sub(r"[ \t]+", " ", str(value).replace("\r\n", "\n")).strip()


def normalized_name(value):
    words = re.findall(r"\w+", clean_text(value).casefold(), flags=re.UNICODE)
    while len(words) > 1 and words[0] in LEGAL_FORMS:
        words.pop(0)
    while len(words) > 1 and words[-1] in LEGAL_FORMS:
        words.pop()
    return "".join(words)


def normalized_header(value):
    return " ".join(clean_text(value).casefold().split())


def merge_text(current, incoming, separator="\n\n"):
    current = clean_text(current)
    incoming = clean_text(incoming)
    if not incoming:
        return current
    if incoming == current or incoming in current:
        return current
    parts = [part.strip() for part in current.split(separator) if part.strip()]
    if incoming in parts:
        return current
    return separator.join([*parts, incoming])


def excel_column_index(reference):
    letters = re.match(r"[A-Z]+", reference or "")
    if not letters:
        return 0
    result = 0
    for letter in letters.group(0):
        result = result * 26 + ord(letter) - 64
    return result - 1


class XlsxReader:
    def __init__(self, path):
        self.path = Path(path)
        self.archive = zipfile.ZipFile(self.path)
        self.shared_strings = self._load_shared_strings()

    def close(self):
        self.archive.close()

    def _load_shared_strings(self):
        try:
            root = ElementTree.fromstring(self.archive.read("xl/sharedStrings.xml"))
        except KeyError:
            return []
        return [
            "".join(node.text or "" for node in item.findall(f".//{{{MAIN_NS}}}t"))
            for item in root.findall(f"{{{MAIN_NS}}}si")
        ]

    def sheets(self):
        workbook = ElementTree.fromstring(self.archive.read("xl/workbook.xml"))
        rels = ElementTree.fromstring(
            self.archive.read("xl/_rels/workbook.xml.rels")
        )
        targets = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels.findall(f"{{{PACKAGE_REL_NS}}}Relationship")
        }
        for sheet in workbook.findall(f".//{{{MAIN_NS}}}sheet"):
            target = targets[sheet.attrib[f"{{{REL_NS}}}id"]]
            if target.startswith("/"):
                sheet_path = target.lstrip("/")
            else:
                sheet_path = posixpath.normpath(posixpath.join("xl", target))
            yield sheet.attrib["name"], sheet_path

    def rows(self, sheet_path):
        root = ElementTree.fromstring(self.archive.read(sheet_path))
        for row in root.findall(f".//{{{MAIN_NS}}}sheetData/{{{MAIN_NS}}}row"):
            values = {}
            for cell in row.findall(f"{{{MAIN_NS}}}c"):
                index = excel_column_index(cell.attrib.get("r", ""))
                cell_type = cell.attrib.get("t")
                if cell_type == "inlineStr":
                    value = "".join(
                        node.text or ""
                        for node in cell.findall(f".//{{{MAIN_NS}}}t")
                    )
                else:
                    value_node = cell.find(f"{{{MAIN_NS}}}v")
                    value = value_node.text if value_node is not None else ""
                    if cell_type == "s" and value:
                        value = self.shared_strings[int(value)]
                values[index] = clean_text(value)
            if values:
                width = max(values) + 1
                yield int(row.attrib.get("r", 0)), [values.get(i, "") for i in range(width)]


def value_at(row, index):
    if index is None or index >= len(row):
        return ""
    return clean_text(row[index])


def find_column(headers, *needles):
    for index, header in enumerate(headers):
        normalized = normalized_header(header)
        if any(needle in normalized for needle in needles):
            return index
    return None


def sheet_status(sheet_name):
    name = normalized_header(sheet_name)
    if "отказ" in name:
        return CustomerCompany.RelationshipStatus.REJECTED
    if "потенциаль" in name:
        return CustomerCompany.RelationshipStatus.POTENTIAL
    if "отправил запрос" in name:
        return CustomerCompany.RelationshipStatus.OFFER_SENT
    return CustomerCompany.RelationshipStatus.WORKING


def business_direction(file_name, sheet_name):
    file_key = normalized_header(file_name)
    sheet_key = normalized_header(sheet_name)
    if "трикотаж" in file_key:
        return CustomerCompany.BusinessDirection.KNIT_FABRIC
    if "швейная" in file_key:
        return CustomerCompany.BusinessDirection.SEWING
    if "пряжа" in sheet_key:
        return CustomerCompany.BusinessDirection.YARN
    if "ткац" in sheet_key:
        return CustomerCompany.BusinessDirection.WEAVING
    return CustomerCompany.BusinessDirection.OTHER


def is_local_country(country):
    key = normalized_header(country)
    return any(part in key for part in ("ўзбекистон", "узбекистан", "o'zbekiston"))


def split_people(value):
    people = []
    for part in re.split(r"[,;\n]+", clean_text(value)):
        person = part.strip(" .-")
        if person and person.casefold() not in {"нет", "йўқ", "yo'q"}:
            people.append(person[:160])
    return people


def extract_contact_details(contact_data, person=""):
    lines = [line.strip() for line in clean_text(contact_data).splitlines() if line.strip()]
    selected = ""
    if person:
        tokens = [token for token in re.findall(r"\w+", person.casefold()) if len(token) > 2]
        for line in lines:
            line_key = line.casefold()
            if any(token in line_key for token in tokens):
                selected = line
                break
    if not selected and len(lines) == 1:
        selected = lines[0]
    phones = PHONE_RE.findall(selected or contact_data)
    emails = EMAIL_RE.findall(selected or contact_data)
    phone = re.sub(r"\s+", " ", phones[0]).strip()[:30] if phones else ""
    email = emails[0][:254] if emails else ""
    return phone, email


class Command(BaseCommand):
    help = "Bunyodkor mijozlarini Excel bazalaridan dublikatsiyasiz import qiladi."

    def add_arguments(self, parser):
        parser.add_argument("workbooks", nargs="+", type=Path)
        parser.add_argument("--organization", default="bunyodkor")
        parser.add_argument("--dry-run", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            organization = Organization.objects.get(slug=options["organization"])
        except Organization.DoesNotExist as exc:
            raise CommandError("Tashkilot topilmadi.") from exc

        missing = [str(path) for path in options["workbooks"] if not path.exists()]
        if missing:
            raise CommandError(f"Fayl topilmadi: {', '.join(missing)}")

        existing = {
            normalized_name(customer.name): customer
            for customer in CustomerCompany.objects.filter(organization=organization)
        }
        stats = {
            "rows": 0,
            "created": 0,
            "updated": 0,
            "contacts_created": 0,
            "contacts_updated": 0,
        }

        for workbook_path in options["workbooks"]:
            reader = XlsxReader(workbook_path)
            try:
                for sheet_name, sheet_path in reader.sheets():
                    rows = list(reader.rows(sheet_path))
                    if not rows:
                        continue
                    candidates = [item for item in rows if item[0] <= 12]
                    header_number, headers = max(
                        candidates,
                        key=lambda item: sum(bool(value) for value in item[1]),
                    )
                    name_col = find_column(headers, "название клиента")
                    if name_col is None:
                        continue
                    country_col = find_column(headers, "страна")
                    product_col = find_column(headers, "наименование продукта")
                    purpose_col = find_column(headers, "цели приоб")
                    manager_col = find_column(headers, "руководитель")
                    employee_col = find_column(headers, "сотрудник")
                    contact_col = find_column(headers, "контактные данные")
                    comments_col = find_column(headers, "комментарии")
                    date_col = find_column(headers, "дата отправления", "дата")
                    offer_cols = [
                        index
                        for index, header in enumerate(headers)
                        if "предложение" in normalized_header(header)
                    ]

                    for row_number, row in rows:
                        if row_number <= header_number:
                            continue
                        name = value_at(row, name_col)
                        key = normalized_name(name)
                        if not key:
                            continue
                        stats["rows"] += 1

                        status = sheet_status(sheet_name)
                        direction = business_direction(workbook_path.name, sheet_name)
                        country = value_at(row, country_col)
                        product = value_at(row, product_col)
                        if not product and direction == CustomerCompany.BusinessDirection.YARN:
                            product = sheet_name
                        purpose = value_at(row, purpose_col)
                        comments = value_at(row, comments_col)
                        contact_data = value_at(row, contact_col)
                        sent_date = value_at(row, date_col)
                        offers = [value_at(row, index) for index in offer_cols]
                        offers = [offer for offer in offers if offer]
                        if sent_date:
                            comments = merge_text(
                                comments,
                                f"Taklif yuborilgan sana: {sent_date}",
                            )
                        for offer in offers:
                            comments = merge_text(comments, f"Taklif: {offer}")

                        customer = existing.get(key)
                        created = customer is None
                        if created:
                            phone, email = extract_contact_details(contact_data)
                            customer = CustomerCompany(
                                organization=organization,
                                name=name[:200],
                                relationship_status=status,
                                business_direction=direction,
                                customer_type=(
                                    CustomerCompany.Type.LOCAL
                                    if is_local_country(country)
                                    else CustomerCompany.Type.EXPORT
                                ),
                                product_interest=product,
                                purchase_purpose=purpose,
                                notes=comments,
                                country=country[:80],
                                phone=phone,
                                email=email,
                                is_active=status != CustomerCompany.RelationshipStatus.REJECTED,
                            )
                            customer.save()
                            existing[key] = customer
                            stats["created"] += 1
                        else:
                            changed = False
                            if STATUS_PRIORITY[status] > STATUS_PRIORITY[customer.relationship_status]:
                                customer.relationship_status = status
                                changed = True
                            if customer.business_direction == CustomerCompany.BusinessDirection.OTHER:
                                customer.business_direction = direction
                                changed = True
                            for field, value in (
                                ("product_interest", product),
                                ("purchase_purpose", purpose),
                                ("notes", comments),
                            ):
                                merged = merge_text(getattr(customer, field), value)
                                if merged != getattr(customer, field):
                                    setattr(customer, field, merged)
                                    changed = True
                            if not customer.country and country:
                                customer.country = country[:80]
                                changed = True
                            if changed:
                                customer.save()
                                stats["updated"] += 1

                        people = [
                            *(('Rahbar', person) for person in split_people(value_at(row, manager_col))),
                            *(('Xodim', person) for person in split_people(value_at(row, employee_col))),
                        ]
                        if not people and contact_data:
                            people = [("Aloqa", "Aloqa ma'lumoti")]

                        known_contacts = {
                            normalized_name(contact.full_name): contact
                            for contact in customer.contacts.all()
                        }
                        for position, person in people:
                            contact_key = normalized_name(person)
                            if not contact_key:
                                continue
                            phone, email = extract_contact_details(contact_data, person)
                            contact = known_contacts.get(contact_key)
                            if contact is None:
                                contact = Contact.objects.create(
                                    organization=organization,
                                    company=customer,
                                    full_name=person,
                                    position=position,
                                    phone=phone,
                                    email=email,
                                    is_primary=position == "Rahbar",
                                )
                                known_contacts[contact_key] = contact
                                stats["contacts_created"] += 1
                            else:
                                changed = False
                                if position == "Rahbar" and contact.position != "Rahbar":
                                    contact.position = "Rahbar"
                                    contact.is_primary = True
                                    changed = True
                                if not contact.phone and phone:
                                    contact.phone = phone
                                    changed = True
                                if not contact.email and email:
                                    contact.email = email
                                    changed = True
                                if changed:
                                    contact.save()
                                    stats["contacts_updated"] += 1
            finally:
                reader.close()

        if options["dry_run"]:
            transaction.set_rollback(True)

        mode = "SINOV" if options["dry_run"] else "IMPORT"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode}: {stats['rows']} qator, {stats['created']} yangi mijoz, "
                f"{stats['updated']} yangilangan mijoz, "
                f"{stats['contacts_created']} yangi kontakt, "
                f"{stats['contacts_updated']} yangilangan kontakt."
            )
        )

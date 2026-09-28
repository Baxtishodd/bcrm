from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from apps.catalog.models import (
    PriceList,
    PriceListLine,
    Product,
    WovenFabricSpecification,
    YarnSpecification,
)
from apps.organizations.models import Organization


YARN_ROWS = (
    ("YARN-NE24-CCD-RING", "Ne24/1 CCD carded ring", "Ne24/1", "carded", False, "ring", "21000", "2.45", date(2026, 10, 20)),
    ("YARN-NE26-CCD-RING", "Ne26/1 CCD carded ring", "Ne26/1", "carded", False, "ring", "21000", "2.50", date(2026, 10, 20)),
    ("YARN-NE28-CCD-RING", "Ne28/1 CCD carded ring", "Ne28/1", "carded", False, "ring", "21000", "2.50", date(2026, 10, 20)),
    ("YARN-NE30-CD-RING", "Ne30/1 CD carded ring", "Ne30/1", "carded", False, "ring", "21000", "2.55", date(2026, 10, 11)),
    ("YARN-NE30-CCD-COMPACT", "Ne30/1 CCD carded compact ring", "Ne30/1", "carded", True, "ring", "21000", "2.60", date(2026, 10, 11)),
    ("YARN-NE32-CCD-COMPACT", "Ne32/1 CCD carded compact ring", "Ne32/1", "carded", True, "ring", "21000", "2.65", date(2026, 10, 11)),
    ("YARN-NE30-CCM-COMPACT", "Ne30/1 CCM combed compact ring", "Ne30/1", "combed", True, "ring", "21000", "2.95", date(2026, 10, 11)),
    ("YARN-NE40-CCM-COMPACT", "Ne40/1 CCM combed compact ring", "Ne40/1", "combed", True, "ring", "21000", "3.50", date(2026, 10, 9)),
    ("YARN-OE-NE20", "OE Ne20/1", "Ne20/1", "carded", False, "open_end", "20000", "1.95", date(2026, 10, 20)),
    ("YARN-OE-NE30", "OE Ne30/1", "Ne30/1", "carded", False, "open_end", "20000", "2.15", date(2026, 10, 10)),
)


WOVEN_PRICE_ROWS = (
    ("WOV-POPLIN-243-105", "Poplin 243 cm / 105 gsm", "243", 105, "1/1", "Ne30/1 rotor", "Ne30/1 rotor", "closed", 280, 238, "500", "600", "80000", "0.78", ""),
    ("WOV-POPLIN-243-110", "Poplin 243 cm / 110 gsm", "243", 110, "1/1", "Ne30/1 rotor", "Ne30/1 rotor", "closed", 280, 240, "500", "600", "75000", "0.80", ""),
    ("WOV-POPLIN-243-115", "Poplin 243 cm / 115 gsm", "243", 115, "1/1", "Ne30/1 rotor", "Ne30/1 rotor", "closed", 280, 250, "500", "600", "75000", "0.82", ""),
    ("WOV-POPLIN-260-110", "Poplin 260 cm / 110 gsm", "260", 110, "1/1", "Ne30/1 rotor", "Ne30/1 rotor", "closed", 280, 242, "500", "600", "65000", "0.90", ""),
    ("WOV-POPLIN-168-110", "Poplin 168 cm / 110 gsm", "168", 110, "1/1", "Ne30/1 rotor", "Ne30/1 rotor", "closed", 280, 240, "500", "600", "110000", "0.62", ""),
    ("WOV-DIAGONAL-175-220", "Diagonal 175 cm / 220 gsm", "175", 220, "3/1", "Ne20/1 rotor", "Ne20/1 rotor", "open", 400, 240, "150", "200", "40000", "1.10", ""),
    ("WOV-WAFFLE-230", "Waffle fabric / 230 gsm", None, 230, "", "Nm34/1", "Ne20/1 rotor", "open", 310, 250, "150", "200", "12000", "1.20", "Manbada '2,0 cm' ko'rsatilgan; mato eni sifatida tasdiqlanmagan."),
    ("WOV-SATIN-STRIPE-325-130", "Satin stripe 3-3 cm / 325 cm / 130 gsm", "325", 130, "4/1", "Ne40/1 combed compact", "Ne40/1 combed compact", "closed", 480, 310, "150", "200", "40000", "2.05", "Stripe 3-3 cm; roll 100-200 m."),
    ("WOV-SATIN-STRIPE-310-130", "Satin stripe 1-1 cm / 310 cm / 130 gsm", "310", 130, "4/1", "Ne40/1 combed compact", "Ne40/1 combed compact", "closed", 480, 310, "150", "200", "45000", "2.00", "Stripe 1-1 cm; roll 100-200 m."),
    ("WOV-SATIN-SMOOTH-325-140", "Satin smooth 325 cm / 140 gsm", "325", 140, "4/1", "Ne40/1 combed compact", "Ne40/1 combed compact", "closed", 480, 310, "150", "200", "40000", "2.10", "Roll 100-200 m."),
    ("WOV-SATIN-SMOOTH-325-130", "Satin smooth 325 cm / 130 gsm", "325", 130, "4/1", "Ne40/1 combed compact", "Ne40/1 combed compact", "closed", 480, 310, "150", "200", "40000", "2.05", "Roll 100-200 m."),
    ("WOV-SATIN-SMOOTH-310-130", "Satin smooth 310 cm / 130 gsm", "310", 130, "4/1", "Ne40/1 combed compact", "Ne40/1 combed compact", "closed", 480, 310, "150", "200", "45000", "2.00", "Roll 100-200 m."),
    ("WOV-SATIN-STRIPE-280-140", "Satin stripe 1-1 cm / 280 cm / 140 gsm", "280", 140, "4/1", "Ne40/1 combed compact", "Ne40/1 combed compact", "closed", 492, 320, "150", "200", "55000", "1.85", "Stripe 1-1 cm; roll 100-200 m."),
    ("WOV-SATIN-STRIPE-290-130", "Satin stripe 1-1 cm / 290 cm / 130 gsm", "290", 130, "4/1", "Ne40/1 combed compact", "Ne40/1 combed compact", "closed", 492, 310, "150", "200", "55000", "1.85", "Stripe 1-1 cm; roll 100-200 m."),
    ("WOV-SATIN-STRIPE-165-130", "Satin stripe 3-3 cm / 165 cm / 130 gsm", "165", 130, "4/1", "Ne40/1 combed compact", "Ne40/1 combed compact", "closed", 500, 340, "150", "200", "100000", "1.45", "Stripe 3-3 cm; roll 100-200 m."),
)


WOVEN_PRODUCT_ROWS = (
    ("WOV-SATIN-RAW-280-140", "Satin raw 280 cm / 140 gsm", "280", 140, "4/1", "Ne40/1 combed compact", "Ne40/1 combed compact", "closed", 480, 310, "300", "500", "25250", ""),
    ("WOV-POPLIN-243-110", "Poplin 243 cm / 110 gsm", "243", 110, "1/1", "Ne30/1 rotor", "Ne30/1 rotor", "closed", 280, 240, "500", "600", "75000", ""),
    ("WOV-POPLIN-192-130", "Poplin 192 cm / 130 gsm", "192", 130, "1/1", "Ne30/1 carded compact", "Ne30/1 carded compact", "open", 280, 242, "500", "600", "44800", ""),
    ("WOV-DIAGONAL-168-130", "Diagonal 168 cm / 130 gsm", "168", 130, "3/1", "CCD Ne30/1 ring carded", "CCD Ne30/1 ring carded", "open", 400, 240, "150", "200", "16200", ""),
    ("WOV-CALICO-167-120", "Calico 167 cm / 120 gsm", "167", 120, "", "Ne20/1", "Ne20/1 rotor", "closed", 250, 124, "200", "500", "36600", ""),
)


class Command(BaseCommand):
    help = "Import the 28.09.2026 yarn and woven-fabric offer documents."

    def add_arguments(self, parser):
        parser.add_argument("--organization", default="bunyodkor")

    def handle(self, *args, **options):
        try:
            organization = Organization.objects.get(slug=options["organization"])
        except Organization.DoesNotExist as exc:
            raise CommandError("Tashkilot topilmadi.") from exc

        self.import_yarn(organization)
        self.import_woven_price_list(organization)
        self.import_woven_product_list(organization)
        self.stdout.write(self.style.SUCCESS("3 ta hujjat va ularning mahsulotlari import qilindi."))

    def product(self, organization, article, name, category, unit, **defaults):
        product, _ = Product.objects.update_or_create(
            organization=organization,
            article=article,
            defaults={
                "name": name,
                "category": category,
                "unit": unit,
                "finish": defaults.pop("finish", Product.Finish.RAW),
                "is_active": True,
                **defaults,
            },
        )
        return product

    def offer(self, organization, number, document_type, category, **defaults):
        offer, _ = PriceList.objects.update_or_create(
            organization=organization,
            number=number,
            document_type=document_type,
            defaults={"category": category, **defaults},
        )
        return offer

    def line(self, organization, offer, product, position, quantity, price=None, loading_date=None, description=""):
        PriceListLine.objects.update_or_create(
            organization=organization,
            price_list=offer,
            product=product,
            defaults={
                "description_snapshot": description or product.description,
                "available_quantity": Decimal(quantity),
                "unit": product.unit,
                "unit_price": Decimal(price) if price is not None else None,
                "planned_loading_date": loading_date,
                "sort_order": position,
            },
        )

    def import_yarn(self, organization):
        offer = self.offer(
            organization,
            "51/Y",
            PriceList.DocumentType.PRICE_LIST,
            Product.Category.YARN,
            title="Yarn price list 28.09.2026",
            issue_date=date(2026, 9, 28),
            valid_until=date(2026, 10, 5),
            currency="USD",
            incoterm="FCA",
            delivery_place="Koson, UZB",
            incoterms_version="2020",
            payment_terms="100% advance payment",
            alternative_delivery_terms="CIP terms also considerable",
            language=PriceList.Language.EN,
            status=PriceList.Status.ACTIVE,
            notes="A truck departs every three days.",
        )
        for position, row in enumerate(YARN_ROWS, start=1):
            article, name, count, preparation, compact, spinning, qty, price, loading = row
            description = f"{count}; {preparation}; {spinning}; {'compact; ' if compact else ''}100% cotton"
            product = self.product(
                organization,
                article,
                name,
                Product.Category.YARN,
                Product.Unit.KILOGRAM,
                description=description,
                yarn_count=count,
                availability=Product.Availability.MADE_TO_ORDER,
                stock_quantity=Decimal("0"),
                list_price=Decimal(price),
                price_currency="USD",
                delivery_basis="FCA Koson, UZB",
                price_valid_until=date(2026, 10, 5),
            )
            YarnSpecification.objects.update_or_create(
                organization=organization,
                product=product,
                defaults={
                    "yarn_count": count,
                    "composition": "100% cotton",
                    "spinning_method": spinning,
                    "preparation": preparation,
                    "is_compact": compact,
                },
            )
            self.line(organization, offer, product, position, qty, price, loading, description)

    def woven_product(self, organization, row, price=None, valid_until=None):
        article, name, width, gsm, weave, warp, weft, selvedge, warp_threads, weft_threads, roll_min, roll_max, qty, notes = row
        description = (
            f"Raw woven fabric; {width + ' cm; ' if width else ''}{gsm} gsm; weave {weave or '—'}; "
            f"warp {warp}; weft {weft}; {selvedge} selvedge; threads {warp_threads}/{weft_threads}; "
            f"packing {roll_min}-{roll_max} lm. {notes}"
        ).strip()
        commercial_defaults = {}
        if price is not None:
            commercial_defaults = {
                "list_price": Decimal(price),
                "price_currency": "USD",
                "delivery_basis": "FCA Koson, UZB",
                "price_valid_until": valid_until,
            }
        product = self.product(
            organization,
            article,
            name,
            Product.Category.WOVEN_FABRIC,
            Product.Unit.METER,
            description=description,
            availability=Product.Availability.STOCK,
            stock_quantity=Decimal(qty),
            **commercial_defaults,
        )
        if width:
            WovenFabricSpecification.objects.update_or_create(
                organization=organization,
                product=product,
                defaults={
                    "composition": "100% cotton",
                    "width_cm": Decimal(width),
                    "gsm": gsm,
                    "weave": weave,
                    "warp_yarn": warp,
                    "weft_yarn": weft,
                    "selvedge": selvedge,
                    "warp_threads": warp_threads,
                    "weft_threads": weft_threads,
                    "roll_length_min": Decimal(roll_min),
                    "roll_length_max": Decimal(roll_max),
                    "construction_notes": notes,
                },
            )
        return product, description

    def import_woven_price_list(self, organization):
        offer = self.offer(
            organization,
            "51/TT",
            PriceList.DocumentType.PRICE_LIST,
            Product.Category.WOVEN_FABRIC,
            title="Woven fabric price list 28.09.2026",
            issue_date=date(2026, 9, 28),
            valid_until=date(2026, 10, 5),
            currency="USD",
            incoterm="FCA",
            delivery_place="Koson, UZB",
            incoterms_version="",
            language=PriceList.Language.RU,
            status=PriceList.Status.ACTIVE,
        )
        for position, source_row in enumerate(WOVEN_PRICE_ROWS, start=1):
            row, price = source_row[:-2] + source_row[-1:], source_row[-2]
            product, description = self.woven_product(
                organization,
                row,
                price=price,
                valid_until=date(2026, 10, 5),
            )
            self.line(organization, offer, product, position, row[12], price, description=description)

    def import_woven_product_list(self, organization):
        offer = self.offer(
            organization,
            "51/TT",
            PriceList.DocumentType.PRODUCT_LIST,
            Product.Category.WOVEN_FABRIC,
            title="Woven fabric product list 28.09.2026",
            issue_date=date(2026, 9, 28),
            valid_until=date(2026, 10, 5),
            currency="USD",
            incoterm="FCA",
            delivery_place="Kasan, UZB",
            incoterms_version="2021",
            payment_terms="Contractual",
            language=PriceList.Language.RU,
            status=PriceList.Status.ACTIVE,
            notes="Quantity is guaranteed according to packing lists.",
        )
        for position, row in enumerate(WOVEN_PRODUCT_ROWS, start=1):
            product, description = self.woven_product(organization, row)
            self.line(organization, offer, product, position, row[12], description=description)

from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from tempfile import TemporaryDirectory

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from pypdf import PdfReader

from apps.accounts.models import User
from apps.common.images import MAX_IMAGE_UPLOAD_BYTES, validate_image_upload
from apps.organizations.models import Membership, Organization

from .models import (
    PriceList,
    PriceListLine,
    Product,
    WovenFabricSpecification,
    YarnSpecification,
)


class TextileCatalogModelTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Textile Specification",
            slug="textile-specification",
        )

    def test_yarn_and_woven_fabric_have_typed_specifications(self):
        yarn = Product.objects.create(
            organization=self.organization,
            article="YARN-NE30",
            name="Ne30/1 compact yarn",
            category=Product.Category.YARN,
            unit=Product.Unit.KILOGRAM,
        )
        yarn_specification = YarnSpecification.objects.create(
            organization=self.organization,
            product=yarn,
            yarn_count="Ne30/1",
            preparation=YarnSpecification.Preparation.COMBED,
            is_compact=True,
        )
        woven = Product.objects.create(
            organization=self.organization,
            article="WOVEN-POPLIN-243",
            name="Poplin 243 cm / 110 gsm",
            category=Product.Category.WOVEN_FABRIC,
            unit=Product.Unit.METER,
        )
        woven_specification = WovenFabricSpecification.objects.create(
            organization=self.organization,
            product=woven,
            width_cm=Decimal("243"),
            gsm=110,
            weave="1/1",
            warp_yarn="Ne30/1",
            weft_yarn="Ne30/1",
        )

        self.assertEqual(yarn.yarn_specification, yarn_specification)
        self.assertTrue(yarn_specification.is_compact)
        self.assertEqual(woven.woven_specification, woven_specification)
        self.assertEqual(woven_specification.weave, "1/1")

    def test_price_list_keeps_price_quantity_and_loading_snapshot(self):
        product = Product.objects.create(
            organization=self.organization,
            article="YARN-NE24",
            name="Ne24/1 carded ring",
            category=Product.Category.YARN,
            unit=Product.Unit.KILOGRAM,
        )
        offer = PriceList.objects.create(
            organization=self.organization,
            number="51/Y",
            category=Product.Category.YARN,
            currency="USD",
            valid_until=timezone.localdate() + timedelta(days=7),
        )
        line = PriceListLine.objects.create(
            organization=self.organization,
            price_list=offer,
            product=product,
            description_snapshot="Ne24/1, carded ring, 100% cotton",
            available_quantity=Decimal("21000"),
            unit=Product.Unit.KILOGRAM,
            unit_price=Decimal("2.4500"),
            planned_loading_date=timezone.localdate() + timedelta(days=20),
        )

        line.refresh_from_db()
        self.assertEqual(line.unit_price, Decimal("2.4500"))
        self.assertEqual(line.available_quantity, Decimal("21000.000"))
        self.assertFalse(offer.is_expired)


class PriceListTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="sales@example.com",
            password="test-password",
        )
        self.organization = Organization.objects.create(
            name="Bunyodkor Textile",
            slug="bunyodkor-textile",
        )
        Membership.objects.create(
            organization=self.organization,
            user=self.user,
            role=Membership.Role.SALES,
        )
        self.other_organization = Organization.objects.create(
            name="Other Textile",
            slug="other-textile-catalog",
        )
        self.client.force_login(self.user)

    def test_price_list_only_shows_current_organization_priced_products(self):
        visible = Product.objects.create(
            organization=self.organization,
            article="TR-001",
            name="Kulirka suprem",
            unit=Product.Unit.KILOGRAM,
            list_price=Decimal("2.90"),
            stock_quantity=Decimal("6000"),
        )
        Product.objects.create(
            organization=self.organization,
            article="TR-002",
            name="Narxsiz mahsulot",
        )
        Product.objects.create(
            organization=self.other_organization,
            article="TR-003",
            name="Yashirin mahsulot",
            list_price=Decimal("3.20"),
        )

        response = self.client.get(reverse("catalog:price-list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, visible.name)
        self.assertNotContains(response, "Narxsiz mahsulot")
        self.assertNotContains(response, "Yashirin mahsulot")

    def test_price_list_can_filter_made_to_order_products(self):
        Product.objects.create(
            organization=self.organization,
            article="TR-STOCK",
            name="Ombordagi mato",
            list_price=Decimal("2.90"),
            availability=Product.Availability.STOCK,
        )
        ordered = Product.objects.create(
            organization=self.organization,
            article="TR-ORDER",
            name="Buyurtma matosi",
            list_price=Decimal("3.20"),
            availability=Product.Availability.MADE_TO_ORDER,
        )

        response = self.client.get(
            reverse("catalog:price-list"),
            {"availability": Product.Availability.MADE_TO_ORDER},
        )

        self.assertContains(response, ordered.name)
        self.assertNotContains(response, "Ombordagi mato")

    def test_price_list_can_filter_product_category(self):
        yarn = Product.objects.create(
            organization=self.organization,
            article="YARN-FILTER",
            name="Filtered yarn",
            category=Product.Category.YARN,
            unit=Product.Unit.KILOGRAM,
            list_price=Decimal("2.45"),
        )
        Product.objects.create(
            organization=self.organization,
            article="WOVEN-FILTER",
            name="Hidden woven fabric",
            category=Product.Category.WOVEN_FABRIC,
            unit=Product.Unit.METER,
            list_price=Decimal("0.78"),
        )

        response = self.client.get(
            reverse("catalog:price-list"),
            {"category": Product.Category.YARN},
        )

        self.assertContains(response, yarn.name)
        self.assertNotContains(response, "Hidden woven fabric")

    def test_expired_price_is_marked(self):
        product = Product.objects.create(
            organization=self.organization,
            article="TR-OLD",
            name="Eski narxli mato",
            list_price=Decimal("2.65"),
            price_valid_until=timezone.localdate() - timedelta(days=1),
        )

        response = self.client.get(reverse("catalog:price-list"))

        self.assertTrue(product.price_is_expired)
        self.assertContains(response, "Muddati tugagan")

    def test_offer_documents_are_scoped_to_current_organization(self):
        visible = PriceList.objects.create(
            organization=self.organization,
            number="51/TT",
            document_type=PriceList.DocumentType.PRICE_LIST,
            category=Product.Category.WOVEN_FABRIC,
        )
        PriceList.objects.create(
            organization=self.other_organization,
            number="PRIVATE-51",
        )

        response = self.client.get(reverse("catalog:offer-list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, visible.number)
        self.assertNotContains(response, "PRIVATE-51")

    def test_activating_new_version_archives_previous_matching_version(self):
        previous = PriceList.objects.create(
            organization=self.organization,
            number="PL-KNIT",
            version=1,
            category=Product.Category.KNITTED_FABRIC,
            currency="USD",
            status=PriceList.Status.ACTIVE,
        )

        current = PriceList.objects.create(
            organization=self.organization,
            number="PL-KNIT",
            version=2,
            category=Product.Category.KNITTED_FABRIC,
            currency="USD",
            status=PriceList.Status.ACTIVE,
        )

        previous.refresh_from_db()
        self.assertEqual(previous.status, PriceList.Status.ARCHIVED)
        self.assertEqual(current.status, PriceList.Status.ACTIVE)
        self.assertIn("v2", str(current))

    def test_new_version_action_copies_document_and_lines_as_draft(self):
        product = Product.objects.create(
            organization=self.organization,
            article="VERSION-COPY",
            name="Versioned fabric",
            unit=Product.Unit.KILOGRAM,
        )
        source = PriceList.objects.create(
            organization=self.organization,
            number="PL-COPY",
            version=1,
            category=Product.Category.KNITTED_FABRIC,
            currency="USD",
            status=PriceList.Status.ACTIVE,
        )
        PriceListLine.objects.create(
            organization=self.organization,
            price_list=source,
            product=product,
            unit=Product.Unit.KILOGRAM,
            unit_price=Decimal("2.9500"),
        )

        response = self.client.post(
            reverse("catalog:offer-create-version", args=[source.public_id])
        )

        copied = PriceList.objects.get(number="PL-COPY", version=2)
        self.assertRedirects(
            response,
            reverse("catalog:offer-document-edit", args=[copied.public_id]),
        )
        self.assertEqual(copied.status, PriceList.Status.DRAFT)
        self.assertEqual(copied.created_by, self.user)
        self.assertEqual(copied.lines.get().product, product)
        self.assertEqual(copied.lines.get().unit_price, Decimal("2.9500"))

    def test_offer_document_editor_updates_document_and_lines(self):
        product = Product.objects.create(
            organization=self.organization,
            article="YARN-EDITOR",
            name="Editor yarn",
            category=Product.Category.YARN,
            unit=Product.Unit.KILOGRAM,
            list_price=Decimal("2.45"),
        )
        offer = PriceList.objects.create(
            organization=self.organization,
            number="51/Y",
            title="Old title",
            category=Product.Category.YARN,
        )
        line = PriceListLine.objects.create(
            organization=self.organization,
            price_list=offer,
            product=product,
            unit=Product.Unit.KILOGRAM,
            unit_price=Decimal("2.4500"),
        )

        response = self.client.post(
            reverse("catalog:offer-document-edit", args=[offer.public_id]),
            {
                "number": "51/Y",
                "version": "1",
                "document_type": PriceList.DocumentType.PRICE_LIST,
                "title": "Export yarn price list",
                "category": Product.Category.YARN,
                "issue_date": timezone.localdate().isoformat(),
                "valid_until": (timezone.localdate() + timedelta(days=10)).isoformat(),
                "currency": "USD",
                "incoterm": "FCA",
                "delivery_place": "Koson, UZB",
                "incoterms_version": "2020",
                "payment_terms": "100% prepayment",
                "alternative_delivery_terms": "CPT by agreement",
                "language": PriceList.Language.EN,
                "status": PriceList.Status.ACTIVE,
                "notes": "Test note",
                "document_intro": "Dear partner",
                "document_footer": "Valid for listed quantities.",
                "lines-TOTAL_FORMS": "1",
                "lines-INITIAL_FORMS": "1",
                "lines-MIN_NUM_FORMS": "0",
                "lines-MAX_NUM_FORMS": "1000",
                "lines-0-id": str(line.id),
                "lines-0-product": str(product.id),
                "lines-0-description_snapshot": "100% cotton, compact",
                "lines-0-available_quantity": "25000",
                "lines-0-unit": Product.Unit.KILOGRAM,
                "lines-0-unit_price": "2.55",
                "lines-0-planned_loading_date": (
                    timezone.localdate() + timedelta(days=20)
                ).isoformat(),
                "lines-0-minimum_order_quantity": "1000",
                "lines-0-sort_order": "1",
            },
        )

        self.assertRedirects(
            response,
            reverse("catalog:offer-document-edit", args=[offer.public_id]),
        )
        offer.refresh_from_db()
        line.refresh_from_db()
        self.assertEqual(offer.title, "Export yarn price list")
        self.assertEqual(offer.currency, "USD")
        self.assertEqual(offer.document_intro, "Dear partner")
        self.assertEqual(line.unit_price, Decimal("2.5500"))
        self.assertEqual(line.minimum_order_quantity, Decimal("1000.000"))

    def test_offer_pdf_contains_company_and_product_details(self):
        product = Product.objects.create(
            organization=self.organization,
            article="WOVEN-243",
            name="Cotton poplin",
            category=Product.Category.WOVEN_FABRIC,
            unit=Product.Unit.METER,
        )
        WovenFabricSpecification.objects.create(
            organization=self.organization,
            product=product,
            composition="100% cotton",
            width_cm=Decimal("243"),
            gsm=110,
            weave="1/1",
        )
        offer = PriceList.objects.create(
            organization=self.organization,
            number="51/TT",
            title="Woven export offer",
            category=Product.Category.WOVEN_FABRIC,
            language=PriceList.Language.EN,
        )
        PriceListLine.objects.create(
            organization=self.organization,
            price_list=offer,
            product=product,
            unit=Product.Unit.METER,
            unit_price=Decimal("0.7800"),
        )

        response = self.client.get(reverse("catalog:offer-pdf", args=[offer.public_id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertIn("51-TT_price-list", response["Content-Disposition"])
        text = "\n".join(
            page.extract_text() or "" for page in PdfReader(BytesIO(response.content)).pages
        )
        self.assertIn("Bunyodkor Textile", text)
        self.assertIn("WOVEN-243", text)
        self.assertIn("Woven export offer", text)

    def test_offer_editor_and_pdf_are_tenant_scoped(self):
        hidden = PriceList.objects.create(
            organization=self.other_organization,
            number="PRIVATE-PDF",
        )

        editor_response = self.client.get(
            reverse("catalog:offer-document-edit", args=[hidden.public_id])
        )
        pdf_response = self.client.get(reverse("catalog:offer-pdf", args=[hidden.public_id]))

        self.assertEqual(editor_response.status_code, 404)
        self.assertEqual(pdf_response.status_code, 404)

    def test_yarn_specification_form_saves_typed_fields(self):
        product = Product.objects.create(
            organization=self.organization,
            article="YARN-30",
            name="Ne30/1 yarn",
            category=Product.Category.YARN,
            unit=Product.Unit.KILOGRAM,
        )

        response = self.client.post(
            reverse("catalog:specification-update", args=[product.public_id]),
            {
                "yarn_count": "Ne30/1",
                "composition": "100% cotton",
                "spinning_method": YarnSpecification.SpinningMethod.RING,
                "preparation": YarnSpecification.Preparation.COMBED,
                "is_compact": "on",
            },
        )

        self.assertRedirects(
            response,
            reverse("catalog:detail", args=[product.public_id]),
        )
        product.refresh_from_db()
        self.assertEqual(product.yarn_count, "Ne30/1")
        self.assertTrue(product.yarn_specification.is_compact)


class ProductImageTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Image Textile",
            slug="image-textile",
        )
        self.media_directory = TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.media_directory.name)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(self.media_directory.cleanup)

    @staticmethod
    def image_upload(filename="fabric.jpg", size=(2000, 1000), image_format="JPEG"):
        output = BytesIO()
        Image.new("RGB", size, color=(24, 116, 102)).save(
            output,
            format=image_format,
            quality=90,
        )
        return SimpleUploadedFile(
            filename,
            output.getvalue(),
            content_type=f"image/{image_format.lower()}",
        )

    def test_images_are_optimized_and_get_unique_names(self):
        first = Product.objects.create(
            organization=self.organization,
            article="IMG-001",
            name="Birinchi mato",
            image=self.image_upload(),
        )
        second = Product.objects.create(
            organization=self.organization,
            article="IMG-002",
            name="Ikkinchi mato",
            image=self.image_upload(),
        )

        self.assertNotEqual(first.image.name, second.image.name)
        self.assertTrue(first.image.name.startswith("images/product/"))
        self.assertTrue(first.image.name.endswith((".webp", ".jpg", ".png")))
        with Image.open(first.image.path) as stored_image:
            self.assertLessEqual(stored_image.width, 1600)
            self.assertLessEqual(stored_image.height, 1600)

    def test_upload_larger_than_one_megabyte_is_rejected(self):
        upload = SimpleUploadedFile(
            "large.jpg",
            b"x" * (MAX_IMAGE_UPLOAD_BYTES + 1),
            content_type="image/jpeg",
        )

        with self.assertRaisesMessage(ValidationError, "1 MB"):
            validate_image_upload(upload)

    def test_image_dimensions_are_limited(self):
        upload = self.image_upload(
            filename="too-wide.png",
            size=(4097, 10),
            image_format="PNG",
        )

        with self.assertRaisesMessage(ValidationError, "4096x4096"):
            validate_image_upload(upload)

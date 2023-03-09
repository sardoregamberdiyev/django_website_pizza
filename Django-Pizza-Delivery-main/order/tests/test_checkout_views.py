from django.test import TestCase, Client
from django.urls import reverse
from django.http.cookie import SimpleCookie
from order.models import Order, OrderItem, Coupon
from store.models import Product, ProductVariant, Size
from users.models import Customer
from django.core.files.uploadedfile import SimpleUploadedFile
import json
from django.conf import settings
from unittest import skipIf
from django.utils import timezone
import datetime
from django.db.models import signals
import factory


class TestCheckoutViewVisitGuest(TestCase):
    """Test checkout views for Guest user"""

    @classmethod
    def setUpTestData(cls):
        # Set up data for the whole TestCase
        cls.customer, created = Customer.objects.get_or_create(device="TestDeviceId")
        # upload a test image
        with open("functional_tests/test_image.jpg", "rb") as image:
            image = SimpleUploadedFile(
                "test_image.jpg", image.read(), content_type="image/jpg"
            )

        # create a product without variants
        cls.product = Product.objects.create(name="Test Product", price=15, image=image)

        # create a product with 2 variants
        cls.product_with_variant = Product.objects.create(
            name="Test Product with Variant", image=image
        )
        size_1 = Size.objects.create(name="Test Size 1")
        size_2 = Size.objects.create(name="Test Size 2")
        cls.variant_1 = ProductVariant.objects.create(
            title="Test Variant 1",
            product=cls.product_with_variant,
            size=size_1,
            price=10,
        )
        cls.variant_2 = ProductVariant.objects.create(
            title="Test Variant 2",
            product=cls.product_with_variant,
            size=size_2,
            price=20,
        )

    def setUp(self):
        self.client_no_cookies = Client()
        self.client = Client()
        # set test cookies
        self.client.cookies = SimpleCookie({"device": "TestDeviceId"})

    def tearDown(self):
        self.product.image.delete()
        self.product_with_variant.image.delete()

    def test_checkout_without_user_and_no_order(self):
        """Test when guest user without assigned device and without order visits checkout"""

        response = self.client_no_cookies.get(reverse("order:checkout"))

        self.assertFalse(Order.objects.all().exists())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("store:products"))

    def test_checkout_guest_user_without_order(self):
        """Test when guest user without order visits checkout"""

        response = self.client.get(reverse("order:checkout"))

        self.assertFalse(Order.objects.all().exists())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("store:products"))

    def test_checkout_guest_user_with_order_no_items(self):
        """Test when guest user with order but no order items visits checkout"""

        # create order for guest user
        Order.objects.create(customer=self.customer)

        response = self.client.get(reverse("order:checkout"))

        self.assertTrue(Order.objects.all().exists())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("store:products"))

    def test_checkout_guest_success_product_no_variants(self):
        """ "Test successful visit of checkout page for guest with order with product without variants"""
        # create order for guest user
        order = Order.objects.create(customer=self.customer)
        order_items = OrderItem.objects.create(
            order=order, product=self.product, quantity=10
        )

        response = self.client.get(reverse("order:checkout"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "order/checkout.html")
        self.assertIn("order", response.context)
        self.assertIn("coupon_form", response.context)
        self.assertIn("stripe_publishable_key", response.context)

        self.assertEqual(response.context["order"], order)

    def test_checkout_guest_success_product_with_variants(self):
        """ "Test successful visit of checkout page for guest with order with product with variants"""
        # create order for guest user
        order = Order.objects.create(customer=self.customer)
        order_items = OrderItem.objects.create(
            order=order,
            product=self.product_with_variant,
            variation=self.variant_1,
            quantity=10,
        )

        response = self.client.get(reverse("order:checkout"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "order/checkout.html")
        self.assertIn("order", response.context)
        self.assertIn("coupon_form", response.context)
        self.assertIn("stripe_publishable_key", response.context)

        self.assertEqual(response.context["order"], order)


class TestCashCheckoutGuest(TestCase):
    """Test cash checkout by a guest user"""

    @classmethod
    def setUpTestData(cls):
        # Set up data for the whole TestCase
        cls.customer, created = Customer.objects.get_or_create(device="TestDeviceId")
        # upload a test image
        with open("functional_tests/test_image.jpg", "rb") as image:
            image = SimpleUploadedFile(
                "test_image.jpg", image.read(), content_type="image/jpg"
            )

        cls.product = Product.objects.create(name="Test Product", price=15, image=image)

        # create a product with 2 variants
        cls.product_with_variant = Product.objects.create(
            name="Test Product with Variant", image=image
        )
        size_1 = Size.objects.create(name="Test Size 1")
        size_2 = Size.objects.create(name="Test Size 2")
        cls.variant_1 = ProductVariant.objects.create(
            title="Test Variant 1",
            product=cls.product_with_variant,
            size=size_1,
            price=10,
        )
        cls.variant_2 = ProductVariant.objects.create(
            title="Test Variant 2",
            product=cls.product_with_variant,
            size=size_2,
            price=20,
        )

        cls.order = Order.objects.create(customer=cls.customer)
        OrderItem.objects.create(order=cls.order, product=cls.product, quantity=10)
        OrderItem.objects.create(
            order=cls.order,
            product=cls.product_with_variant,
            variation=cls.variant_1,
            quantity=10,
        )
        OrderItem.objects.create(
            order=cls.order,
            product=cls.product_with_variant,
            variation=cls.variant_2,
            quantity=10,
        )

    def setUp(self):
        self.client = Client()
        # set test cookies
        self.client.cookies = SimpleCookie({"device": "TestDeviceId"})

        self.cash_checkout_url = reverse(
            "order:cash-checkout", args=[self.order.transaction_id]
        )

    def tearDown(self):
        self.product.image.delete()
        self.product_with_variant.image.delete()

    def test_cash_checkout_no_params_404(self):
        """Test Cash checkout view with no data passed -> returns 404 response"""

        # url = reverse('order:cash-checkout', args=[self.order.transaction_id])
        response = self.client.post(self.cash_checkout_url)

        self.assertEqual(response.status_code, 404)
        # order complete is False
        self.assertFalse(Order.objects.all()[0].complete)

    def test_cash_checkout_delivery_invalid_address_form_ajax(self):
        """Test Cash checkout for delivery when invalid ShippingAddress data is passed"""

        data = json.dumps(
            {
                "delivery": True,
                "email": "test@example.com",
                "phone": "1234567",
                "address_1": "address 1",
            }
        )
        response = self.client.post(
            self.cash_checkout_url, data, content_type="application/json"
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("errors", str(response.content))
        # order complete is False
        self.assertFalse(Order.objects.all()[0].complete)

    def test_cash_checkout_delivery_invalid_phone_ajax(self):
        """Test Cash checkout for delivery when invalid phone data is passed"""

        data = json.dumps(
            {
                "delivery": True,
                "email": "test@example.com",
                "phone": "12345671234567123456712345671234567123",  # too long
                "first_name": "first name",
                "last_name": "last name",
                "address_1": "address 1",
                "city": "city",
                "state": "state",
                "country": "country",
            }
        )
        response = self.client.post(
            self.cash_checkout_url, data, content_type="application/json"
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("errors", str(response.content))
        # order complete is False
        self.assertFalse(Order.objects.all()[0].complete)

    def test_cash_checkout_delivery_invalid_email_ajax(self):
        """Test Cash checkout for delivery when invalid email data is passed"""

        data = json.dumps(
            {
                "delivery": True,
                "email": "testtesttesttesttestesttestestteststteststtestesttesttesttesttettest@example.com",  # too long
                "phone": "1234567",
                "first_name": "first name",
                "last_name": "last name",
                "address_1": "address 1",
                "city": "city",
                "state": "state",
                "country": "country",
            }
        )
        response = self.client.post(
            self.cash_checkout_url, data, content_type="application/json"
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("errors", str(response.content))
        # order complete is False
        self.assertFalse(Order.objects.all()[0].complete)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_cash_checkout_delivery_valid_form_ajax(self):
        """Test Cash checkout for delivery when valid ShippingAddress data is passed"""

        data = json.dumps(
            {
                "delivery": True,
                "email": "test@example.com",
                "phone": "12345678",
                "first_name": "first name",
                "last_name": "last name",
                "address_1": "address 1",
                "city": "city",
                "state": "state",
                "country": "country",
            }
        )
        response = self.client.post(
            self.cash_checkout_url, data, content_type="application/json"
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("success", str(response.url))
        # check order complete is True
        self.assertTrue(Order.objects.all()[0].complete)

    def test_cash_checkout_carryout_custom_invalid_form(self):
        """Test Cash checkout for carryout when invalid PickUpDetail data is passed"""

        data = json.dumps(
            {
                "delivery": False,
                "email": "test@example.com",
                "phone": "12345678",
                "urgency": "wrong urgency",  # must be either asap or custom
                "pickup_date": "wrong date",  # wrong data passed
            }
        )

        response = self.client.post(
            self.cash_checkout_url, data, content_type="application/json"
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("errors", str(response.content))
        # order complete is False
        self.assertFalse(Order.objects.all()[0].complete)

    def test_cash_checkout_carryout_custom_invalid_date_ajax(self):
        """Test Cash checkout for carryout when invalid pickup_date passed for custom order"""

        data = json.dumps(
            {
                "delivery": False,
                "email": "test@example.com",
                "phone": "12345678",
                "urgency": "custom",  # must be either asap or custom
                "pickup_date": "wrong date",  # wrong data passed
            }
        )
        response = self.client.post(
            self.cash_checkout_url, data, content_type="application/json"
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("errors", str(response.content))
        # order complete is False
        self.assertFalse(Order.objects.all()[0].complete)

    def test_cash_checkout_carryout_custom_no_date_ajax(self):
        """Test Cash checkout for carryout when no pickup_date passed for custom order"""

        data = json.dumps(
            {
                "delivery": False,
                "email": "test@example.com",
                "phone": "12345678",
                "urgency": "custom",  # must be either asap or custom
            }
        )
        response = self.client.post(
            self.cash_checkout_url, data, content_type="application/json"
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("errors", str(response.content))
        # order complete is False
        self.assertFalse(Order.objects.all()[0].complete)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_cash_checkout_carryout_asap_success_ajax(self):
        """Test sucessful Cash checkout for carryout for asap order"""

        data = json.dumps(
            {
                "delivery": False,
                "email": "test@example.com",
                "phone": "12345678",
                "urgency": "asap",  # must be either asap or custom
            }
        )
        response = self.client.post(
            self.cash_checkout_url, data, content_type="application/json"
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("success", str(response.url))
        # check order complete is True
        self.assertTrue(Order.objects.all()[0].complete)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_cash_checkout_carryout_custom_success_ajax(self):
        """Test sucessful Cash checkout for carryout for custom order"""

        data = json.dumps(
            {
                "delivery": False,
                "email": "test@example.com",
                "phone": "12345678",
                "urgency": "custom",
                "pickup_date": "2023-02-02 2:00 PM",
            }
        )
        response = self.client.post(
            self.cash_checkout_url, data, content_type="application/json"
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("success", str(response.url))
        # check order complete is True
        self.assertTrue(Order.objects.all()[0].complete)


class TestStripeCheckoutGuest(TestCase):
    """Test Stripe checkout session by a guest user"""

    stripe_secret_key = settings.STRIPE_SECRET_KEY
    stripe_coupon_id = settings.STRIPE_COUPON_ID_PERCENT

    @classmethod
    def setUpTestData(cls):
        # Set up data for the whole TestCase
        cls.customer, created = Customer.objects.get_or_create(device="TestDeviceId")
        # upload a test image
        with open("functional_tests/test_image.jpg", "rb") as image:
            image = SimpleUploadedFile(
                "test_image.jpg", image.read(), content_type="image/jpg"
            )

        cls.product = Product.objects.create(name="Test Product", price=15, image=image)

        # create a product with 2 variants
        cls.product_with_variant = Product.objects.create(
            name="Test Product with Variant", image=image
        )
        size_1 = Size.objects.create(name="Test Size 1")
        size_2 = Size.objects.create(name="Test Size 2")
        cls.variant_1 = ProductVariant.objects.create(
            title="Test Variant 1",
            product=cls.product_with_variant,
            size=size_1,
            price=10,
        )
        cls.variant_2 = ProductVariant.objects.create(
            title="Test Variant 2",
            product=cls.product_with_variant,
            size=size_2,
            price=20,
        )

        cls.order = Order.objects.create(customer=cls.customer)
        OrderItem.objects.create(order=cls.order, product=cls.product, quantity=10)
        OrderItem.objects.create(
            order=cls.order,
            product=cls.product_with_variant,
            variation=cls.variant_1,
            quantity=10,
        )
        OrderItem.objects.create(
            order=cls.order,
            product=cls.product_with_variant,
            variation=cls.variant_2,
            quantity=10,
        )

    def setUp(self):
        self.client = Client()
        # set test cookies
        self.client.cookies = SimpleCookie({"device": "TestDeviceId"})
        self.stripe_checkout_url = reverse(
            "order:api_checkout_session", args=[self.order.transaction_id]
        )

    def tearDown(self):
        self.product.image.delete()
        self.product_with_variant.image.delete()

    def test_stripe_checkout_no_params_404(self):
        """Test Stripe checkout view with no data passed -> returns 404 response"""

        response = self.client.post(self.stripe_checkout_url)

        self.assertEqual(response.status_code, 404)

    def test_stripe_checkout_delivery_invalid_address_form_ajax(self):
        """Test Stripe checkout for delivery when invalid ShippingAddress data is passed"""

        data = json.dumps(
            {
                "delivery": True,
                "email": "test@example.com",
                "phone": "1234567",
                "address_1": "address 1",
            }
        )
        response = self.client.post(
            self.stripe_checkout_url, data, content_type="application/json"
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("errors", str(response.content))
        # order complete is False
        self.assertFalse(Order.objects.all()[0].complete)

    def test_stripe_checkout_delivery_invalid_phone_ajax(self):
        """Test Stripe checkout for delivery when invalid phone data is passed"""

        data = json.dumps(
            {
                "delivery": True,
                "email": "test@example.com",
                "phone": "12345671234567123456712345671234567123",  # too long
                "first_name": "first name",
                "last_name": "last name",
                "address_1": "address 1",
                "city": "city",
                "state": "state",
                "country": "country",
            }
        )
        response = self.client.post(
            self.stripe_checkout_url, data, content_type="application/json"
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("errors", str(response.content))
        # order complete is False
        self.assertFalse(Order.objects.all()[0].complete)

    def test_stripe_checkout_delivery_invalid_email_ajax(self):
        """Test Stripe checkout for delivery when invalid email data is passed"""

        data = json.dumps(
            {
                "delivery": True,
                "email": "testtesttesttesttestesttestestteststteststtestesttesttesttesttettest@example.com",  # too long
                "phone": "1234567",
                "first_name": "first name",
                "last_name": "last name",
                "address_1": "address 1",
                "state": "state",
                "country": "country",
            }
        )
        response = self.client.post(
            self.stripe_checkout_url, data, content_type="application/json"
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("errors", str(response.content))
        # order complete is False
        self.assertFalse(Order.objects.all()[0].complete)

    # skip the test if no STRIPE SECRET KEY is provided
    @skipIf(not stripe_secret_key, "No Stripe Secret Key is Provided")
    def test_stripe_checkout_delivery_success_ajax(self):
        """Test Stripe checkout for delivery when valid ShippingAddress data is passed"""

        data = json.dumps(
            {
                "delivery": True,
                "email": "test@example.com",
                "phone": "12345678",
                "first_name": "first name",
                "last_name": "last name",
                "address_1": "address 1",
                "city": "city",
                "state": "state",
                "country": "country",
            }
        )
        response = self.client.post(
            self.stripe_checkout_url, data, content_type="application/json"
        )

        self.assertIn("sessionId", str(response.content))
        self.assertEqual(response.status_code, 200)

    def test_stripe_checkout_carryout_custom_invalid_form(self):
        """Test Stripe checkout for carryout when invalid PickUpDetail data is passed"""

        data = json.dumps(
            {
                "delivery": False,
                "email": "test@example.com",
                "phone": "12345678",
                "urgency": "wrong urgency"  # must be either asap or custom
                # pickup_date is not checked initially in this view
            }
        )

        response = self.client.post(
            self.stripe_checkout_url, data, content_type="application/json"
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("errors", str(response.content))

    @skipIf(not stripe_secret_key, "No Stripe Secret Key is Provided")
    def test_stripe_checkout_carryout_asap_success_ajax(self):
        """Test sucessful Stripe checkout for carryout asap order"""

        data = json.dumps(
            {
                "delivery": False,
                "email": "test@example.com",
                "phone": "12345678",
                "urgency": "asap",
            }
        )
        response = self.client.post(
            self.stripe_checkout_url, data, content_type="application/json"
        )

        self.assertIn("sessionId", str(response.content))
        self.assertEqual(response.status_code, 200)

    @skipIf(
        not stripe_secret_key or not stripe_coupon_id,
        "No Stripe Secret Key or Coupon Code is Provided",
    )
    def test_stripe_checkout_carryout_asap_with_coupon_success_ajax(self):
        """Test sucessful Stripe checkout for carryout asap order with coupon"""

        # create a test coupon and add it to order
        now = timezone.now()
        tom = timezone.make_aware(datetime.datetime.now() + datetime.timedelta(days=1))
        coupon = Coupon.objects.create(
            code="winter",
            active=True,
            discount_type="Percent",
            discount_amount=50,
            valid_from=now,
            valid_to=tom,
            stripe_coupon_id=self.stripe_coupon_id,
        )
        self.order.coupon = coupon
        self.order.save()  # save to apply changes

        data = json.dumps(
            {
                "delivery": False,
                "email": "test@example.com",
                "phone": "12345678",
                "urgency": "asap",
            }
        )
        response = self.client.post(
            self.stripe_checkout_url, data, content_type="application/json"
        )

        self.assertIn("sessionId", str(response.content))
        self.assertEqual(response.status_code, 200)

    @skipIf(not stripe_secret_key, "No Stripe Secret Key is Provided")
    def test_stripe_checkout_carryout_custom_success_ajax(self):
        """Test sucessful Stripe checkout for carryout custom order"""

        data = json.dumps(
            {
                "delivery": False,
                "email": "test@example.com",
                "phone": "12345678",
                "urgency": "custom",
                "pickup_date": "2023-02-02 2:00 PM",
            }
        )
        response = self.client.post(
            self.stripe_checkout_url, data, content_type="application/json"
        )

        self.assertIn("sessionId", str(response.content))
        self.assertEqual(response.status_code, 200)

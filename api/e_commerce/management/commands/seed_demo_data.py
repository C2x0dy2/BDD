"""
Populates PostgreSQL (via the ORM) and MongoDB (via pymongo) with a
demo e-commerce dataset -- a few thousand rows/documents so joins,
aggregates, and the cross-database endpoint have something real to show.

Idempotent: does nothing if categories already exist.

Run after `migrate --database=migration` and `setup_relational_extras`
(the trigger needs to exist before order items are inserted, so
Order.total_amount comes out correct without any Python-side recomputation).
"""
import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.utils import timezone
from django.utils.text import slugify
from faker import Faker

from e_commerce.models import Category, Order, OrderItem, Product, Tag, User, Wishlist
from reviews.services import upsert_product_specs, upsert_review

CATEGORY_NAMES = [
    "Électronique", "Livres", "Vêtements", "Maison & Cuisine",
    "Sport & Plein air", "Jeux & Jouets", "Beauté", "Jardin",
    "Automobile", "Épicerie",
]
TAG_NAMES = [
    "promo", "nouveau", "bestseller", "eco", "edition-limitee",
    "fait-main", "import", "local", "premium", "soldes",
]
COLORS = ["noir", "blanc", "rouge", "bleu", "vert", "argent", "beige"]
ORDER_STATUSES = ["pending", "confirmed", "shipped", "delivered", "cancelled"]
PAYMENT_METHODS = ["cash", "mobile_money", "bank_transfer", "credit_card", "wave"]

# Product.image's model default ("products/default.jpg") doesn't actually
# exist as a file -- it was never part of the media fixtures that shipped
# with SIKA. Cycle seeded products through the real photos that *do* exist
# (api/media/products/) instead, so product cards aren't all broken images.
PRODUCT_IMAGES = [
    "1.jpg", "1_2.jpg", "2.jpg",
    "71XGIukqAkL._AC_UF10001000_QL80_.jpg", "71dRiD4rOHL.jpg",
    "71jYntm8tpL._UF10001000_QL80_.jpg", "Boutique_brosse_dents.jpg",
    "images_1.jpeg", "images_17.jpeg", "images_18.jpeg",
    "images_1_agnRaYT.jpeg", "images_1_k4Vw2es.jpeg", "images_1_l4RMFZi.jpeg",
    "images_1_ltRUub4.jpeg", "images_1_xijac8A.jpeg", "images_21.jpeg",
    "images_26.jpeg", "images_27.jpeg", "images_29.jpeg", "oriental-01_1.jpg",
    "s-l1200.jpg", "samsung-galaxy-a54-8gb-ram-128gb-5g.jpg",
    "service_de_table_-_set_de_12pcs_2_.jpg",
    "sujet-africain-en-bois-elephant-sculpture-dans-la-masse-belle-patine-l1136_imgx1200_106.jpg",
    "téléchargement_38.jpeg", "téléchargement_40.jpeg", "téléchargement_43.jpeg",
    "téléchargement_47.jpeg", "téléchargement_48.jpeg", "unnamed.png",
]

SELLER_COUNT = 30
CUSTOMER_COUNT = 970
PRODUCT_COUNT = 2000
ORDER_COUNT = 3000
DEMO_PASSWORD = "DemoPass123!"


class Command(BaseCommand):
    help = "Seed PostgreSQL + MongoDB with demo e-commerce data (idempotent)."

    def handle(self, *args, **options):
        if Category.objects.exists():
            self.stdout.write("seed_demo_data: data already present, skipping.")
            return

        fake = Faker("fr_FR")
        Faker.seed(42)
        random.seed(42)

        with transaction.atomic():
            categories = self._seed_categories()
            tags = self._seed_tags()
            sellers = self._seed_users(fake, is_seller=True, count=SELLER_COUNT, start_id=1)
            customers = self._seed_users(
                fake, is_seller=False, count=CUSTOMER_COUNT, start_id=SELLER_COUNT + 1
            )
            users = sellers + customers
            products = self._seed_products(fake, categories, tags, sellers)
            orders, order_items = self._seed_orders(fake, users, products)
            self._seed_wishlist(users, products)

        self.stdout.write(self.style.SUCCESS(
            f"PostgreSQL: {len(categories)} categories, {len(tags)} tags, "
            f"{len(users)} users, {len(products)} products, {len(orders)} orders, "
            f"{len(order_items)} order items."
        ))

        review_count = self._seed_mongo(fake, products, order_items)
        self.stdout.write(self.style.SUCCESS(
            f"MongoDB: {len(products)} product_specs, {review_count} reviews."
        ))

    # -- PostgreSQL -----------------------------------------------------

    def _seed_categories(self):
        # bulk_create() does not call Model.save(), so auto_now_add fields
        # like created_at must be set explicitly or they'd insert NULL.
        now = timezone.now()
        categories = [
            Category(name=name, slug=slugify(name), description=f"Catégorie {name}", created_at=now)
            for name in CATEGORY_NAMES
        ]
        return Category.objects.bulk_create(categories)

    def _seed_tags(self):
        tags = [Tag(name=name, slug=slugify(name)) for name in TAG_NAMES]
        return Tag.objects.bulk_create(tags)

    def _seed_users(self, fake, is_seller, count, start_id):
        hashed_password = make_password(DEMO_PASSWORD)
        now = timezone.now()
        users = []
        for i in range(start_id, start_id + count):
            first_name = fake.first_name()
            last_name = fake.last_name()
            users.append(User(
                username=f"user{i}",
                email=f"user{i}@example.com",
                first_name=first_name,
                last_name=last_name,
                password=hashed_password,
                phone=fake.phone_number()[:20],
                address=fake.address(),
                is_seller=is_seller,
                is_seller_approved=is_seller,
                is_email_verified=True,
                created_at=now,
                store_name=f"Boutique {last_name}" if is_seller else "",
                store_description=fake.catch_phrase() if is_seller else "",
                store_phone=fake.phone_number()[:20] if is_seller else "",
                store_address=fake.address() if is_seller else "",
            ))
        return User.objects.bulk_create(users)

    def _seed_products(self, fake, categories, tags, sellers):
        now = timezone.now()
        products = []
        for i in range(1, PRODUCT_COUNT + 1):
            category = categories[i % len(categories)]
            seller = sellers[i % len(sellers)]
            name = f"{category.name} {fake.word().capitalize()} {i}"
            products.append(Product(
                name=name,
                slug=f"{slugify(name)}-{i}",
                description=fake.paragraph(nb_sentences=4),
                price=Decimal(random.randint(500, 50000)) / 100,
                image=f"products/{PRODUCT_IMAGES[i % len(PRODUCT_IMAGES)]}",
                category=category,
                seller=seller,
                stock=random.randint(0, 200),
                is_active=True,
                created_at=now,
                updated_at=now,
            ))
        created = Product.objects.bulk_create(products)

        # Tags: a lightweight many-to-many assignment pass (bulk_create
        # doesn't populate M2M, so this needs a second step).
        through_model = Product.tags.through
        links = []
        for product in created:
            for tag in random.sample(tags, k=random.randint(0, 3)):
                links.append(through_model(product_id=product.id, tag_id=tag.id))
        through_model.objects.bulk_create(links, ignore_conflicts=True)

        return created

    def _seed_orders(self, fake, users, products):
        now = timezone.now()
        orders = []
        intended_dates = []
        for i in range(1, ORDER_COUNT + 1):
            user = users[random.randrange(len(users))]
            status = random.choice(ORDER_STATUSES)
            payment_status = "paid" if status in ("confirmed", "shipped", "delivered") else (
                "failed" if status == "cancelled" and random.random() < 0.3 else "pending"
            )
            order_created_at = now - timedelta(days=random.randint(0, 365))
            intended_dates.append(order_created_at)
            orders.append(Order(
                order_number=f"ORD-{i:08X}",
                user=user,
                status=status,
                payment_method=random.choice(PAYMENT_METHODS),
                payment_status=payment_status,
                delivery_address=fake.address(),
                phone=fake.phone_number()[:20],
            ))
        created_orders = Order.objects.bulk_create(orders)

        # bulk_create's INSERT still runs each field's pre_save(), so
        # auto_now_add silently overwrites created_at with the real
        # current time no matter what was set above -- spread the orders
        # back out over the last year with a direct UPDATE so
        # monthly_revenue has more than one month to group by.
        with connection.cursor() as cursor:
            cursor.executemany(
                "UPDATE e_commerce_order SET created_at = %s, updated_at = %s WHERE id = %s",
                [(d, d, o.id) for o, d in zip(created_orders, intended_dates)],
            )
        for order, date in zip(created_orders, intended_dates):
            order.created_at = date

        order_items = []
        for order in created_orders:
            for product in random.sample(products, k=random.randint(1, 4)):
                order_items.append(OrderItem(
                    order=order,
                    product=product,
                    quantity=random.randint(1, 5),
                    price=product.price,
                    created_at=order.created_at,
                ))
        # PostgreSQL fires a FOR EACH ROW trigger once per row even for a
        # single batched multi-row INSERT, so bulk_create still leaves
        # every order's total_amount correctly recalculated by
        # trg_recalc_order_total -- no Python-side recomputation needed.
        created_items = OrderItem.objects.bulk_create(order_items)

        return created_orders, created_items

    def _seed_wishlist(self, users, products):
        now = timezone.now()
        links = []
        for _ in range(500):
            user = users[random.randrange(len(users))]
            product = products[random.randrange(len(products))]
            links.append(Wishlist(user=user, product=product, created_at=now))
        Wishlist.objects.bulk_create(links, ignore_conflicts=True)

    # -- MongoDB ----------------------------------------------------------

    def _seed_mongo(self, fake, products, order_items):
        for product in products:
            upsert_product_specs(
                product_id=product.id,
                category=product.category.name if product.category_id else "",
                attributes={
                    "color": random.choice(COLORS),
                    "weight_kg": round(random.uniform(0.1, 10), 2),
                    "warranty_months": random.choice([0, 6, 12, 24]),
                },
                media=[
                    f"https://picsum.photos/seed/product{product.id}-1/600/400",
                    f"https://picsum.photos/seed/product{product.id}-2/600/400",
                ],
                tags=["demo-data"],
            )

        # Reviews only for (product, user) pairs that actually ordered --
        # mirrors the HTML submit_review rule (api/e_commerce/views.py).
        review_count = 0
        seen = set()
        random.shuffle(order_items)
        for item in order_items:
            key = (item.product_id, item.order.user_id)
            if key in seen or random.random() > 0.4:
                continue
            seen.add(key)
            upsert_review(
                product_id=item.product_id,
                user_id=item.order.user_id,
                rating=random.randint(1, 5),
                comment=fake.sentence(nb_words=12),
            )
            review_count += 1

        return review_count

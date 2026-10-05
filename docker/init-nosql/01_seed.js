// MongoDB schema + seed for the e-commerce project.
// Executed once, automatically, by the official mongo image on first
// container start (docker-entrypoint-initdb.d), via mongosh.
//
// product_id / customer_id values are plain integers that mirror the
// PostgreSQL products(1..PRODUCT_COUNT) / customers(1..CUSTOMER_COUNT) ids
// seeded by docker/init-sql/02_seed.sql -- Postgres stays the source of
// truth for those identities, Mongo only references them.

const database = db.getSiblingDB("commerce");

const PRODUCT_COUNT = 2000;
const CUSTOMER_COUNT = 1500;
const CATEGORY_NAMES = [
    "Electronics", "Books", "Clothing", "Home & Kitchen", "Sports & Outdoors",
    "Toys & Games", "Beauty", "Garden", "Automotive", "Grocery",
];
const COLORS = ["black", "white", "red", "blue", "green", "silver", "beige"];

function randInt(min, max) {
    return min + Math.floor(Math.random() * (max - min + 1));
}

function pick(arr) {
    return arr[randInt(0, arr.length - 1)];
}

function daysAgo(n) {
    const d = new Date();
    d.setDate(d.getDate() - n);
    return d;
}

// ---------------------------------------------------------------------
// product_specs: one document per product, embedding the flexible,
// category-dependent attributes/media/tags that don't fit a fixed set of
// SQL columns. product_id is a reference back to PostgreSQL products.id.
// ---------------------------------------------------------------------

database.product_specs.drop();

let specsBatch = [];
for (let productId = 1; productId <= PRODUCT_COUNT; productId++) {
    const category = CATEGORY_NAMES[productId % CATEGORY_NAMES.length];
    specsBatch.push({
        product_id: productId,
        category: category,
        attributes: {
            color: pick(COLORS),
            weight_kg: Math.round((0.1 + Math.random() * 10) * 100) / 100,
            warranty_months: pick([0, 6, 12, 24]),
        },
        media: [
            `https://picsum.photos/seed/product${productId}-1/600/400`,
            `https://picsum.photos/seed/product${productId}-2/600/400`,
        ],
        tags: [category.toLowerCase().replace(/[^a-z]+/g, "-"), "demo-data"],
        updated_at: daysAgo(randInt(0, 300)),
    });

    if (specsBatch.length === 500) {
        database.product_specs.insertMany(specsBatch);
        specsBatch = [];
    }
}
if (specsBatch.length > 0) {
    database.product_specs.insertMany(specsBatch);
}

database.product_specs.createIndex({ product_id: 1 }, { unique: true });

// ---------------------------------------------------------------------
// reviews: 0-5 reviews per product. replies are embedded (small, bounded,
// always displayed with their parent review); product_id/customer_id are
// references to PostgreSQL.
// ---------------------------------------------------------------------

database.reviews.drop();

let reviewsBatch = [];
let totalReviews = 0;
for (let productId = 1; productId <= PRODUCT_COUNT; productId++) {
    const reviewCount = randInt(0, 5);
    for (let i = 0; i < reviewCount; i++) {
        const replyCount = Math.random() < 0.3 ? randInt(1, 2) : 0;
        const replies = [];
        for (let r = 0; r < replyCount; r++) {
            replies.push({
                author: "support-team",
                body: "Thanks for your feedback, we'll look into it.",
                created_at: daysAgo(randInt(0, 60)),
            });
        }

        reviewsBatch.push({
            product_id: productId,
            customer_id: randInt(1, CUSTOMER_COUNT),
            rating: randInt(1, 5),
            title: pick([
                "Great value", "Not what I expected", "Works as advertised",
                "Would buy again", "Disappointed", "Exceeded expectations",
            ]),
            body: "Demo review content generated for the EFREI BDD project.",
            created_at: daysAgo(randInt(0, 300)),
            replies: replies,
        });
        totalReviews++;

        if (reviewsBatch.length === 500) {
            database.reviews.insertMany(reviewsBatch);
            reviewsBatch = [];
        }
    }
}
if (reviewsBatch.length > 0) {
    database.reviews.insertMany(reviewsBatch);
}

database.reviews.createIndex({ product_id: 1, created_at: -1 });

print(`Seeded ${PRODUCT_COUNT} product_specs and ${totalReviews} reviews.`);

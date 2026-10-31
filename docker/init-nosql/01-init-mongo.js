// 01-init-mongo.js : creates the MongoDB collections, their validation rules
// and indexes. Run once, by the mongo image itself, the first time the data
// volume is initialised (mounted in /docker-entrypoint-initdb.d).
//
// The documents are loaded afterwards by the api container
// (`manage.py seed_demo_data`), which keeps PostgreSQL ids and Mongo
// product_id / user_id consistent. The same indexes are also declared in
// api/reviews/services.py (ensure_indexes) so an already-existing volume
// gets them too; both definitions must stay identical.

const sika = db.getSiblingDB("sika");

// Flexible product sheet: `attributes` varies by category, so only the
// fields every document must have are enforced.
sika.createCollection("product_specs", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["product_id", "category", "attributes"],
      properties: {
        product_id: { bsonType: ["int", "long"], description: "id of e_commerce_product in PostgreSQL" },
        category: { bsonType: "string" },
        attributes: { bsonType: "object" },
        media: { bsonType: "array" },
        tags: { bsonType: "array" },
      },
    },
  },
});

// Customer reviews: product_id / user_id reference PostgreSQL rows
// (no native foreign key between engines), replies are embedded.
sika.createCollection("reviews", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["product_id", "user_id", "rating", "comment", "created_at"],
      properties: {
        product_id: { bsonType: ["int", "long"] },
        user_id: { bsonType: ["int", "long"] },
        rating: { bsonType: ["int", "long"], minimum: 1, maximum: 5 },
        comment: { bsonType: "string" },
        replies: { bsonType: "array" },
      },
    },
  },
});

// One sheet per product; also the lookup key of GET /products/{id}/specs/.
sika.product_specs.createIndex({ product_id: 1 }, { unique: true });
// "Reviews of a product, newest first" without an in-memory sort.
sika.reviews.createIndex({ product_id: 1, created_at: -1 });

print("init-mongo: collections, validators and indexes created.");

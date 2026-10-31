# Document de présentation -- SÎKÂ (EFREI M1 Dev, Projet BDD)

## 1. Le projet

**SÎKÂ** est une marketplace e-commerce : des vendeurs y publient des
produits organisés par catégories et tags, des clients parcourent le
catalogue, ajoutent au panier, passent commande, et laissent des avis sur
les produits qu'ils ont achetés. Le projet part d'une base Django déjà
construite (authentification, panier, checkout, espace vendeur, templates)
à laquelle ont été ajoutées les exigences du cours : une seconde base non
relationnelle, une API, et les éléments avancés relationnels.

Utilisateurs : des **clients** (navigation, panier, commande, avis), des
**vendeurs** (gestion de leur catalogue, suivi de leurs commandes), et un
**administrateur** (validation des demandes vendeur, back-office Jazzmin).

Fonctionnalités principales :
- Inscription/connexion, avec demande de statut vendeur soumise à validation.
- Catalogue produits filtrable par catégorie/tag, fiches produit enrichies.
- Panier, checkout, suivi de commande, liste de souhaits.
- Avis clients (une note + un commentaire par produit et par client ayant
  commandé), stockés dans MongoDB et affichés en temps réel sur la fiche
  produit.
- Tableau de bord vendeur (produits, commandes reçues, statistiques).
- Rapports de vente avancés et endpoint croisé exposés via une API JSON.

## 2. Architecture

```
                 ┌─────────────────────────────┐
                 │   Navigateur (site HTML)      │
                 │ ou client API (curl/Postman)   │
                 └──────────────┬────────────────┘
                                │ HTTP
                                ▼
                 ┌─────────────────────────────┐
                 │   Django (container `api`)     │
                 │  e_commerce/  (vues HTML)       │
                 │  reviews/     (pymongo direct)  │
                 │  reports/     (SQL brut)         │
                 └──────┬───────────────┬─────────┘
          ORM Django    │               │  pymongo
          (default =    │               │  (reviews/mongo_client.py)
          rôle restreint)▼               ▼
        ┌─────────────────────┐ ┌─────────────────────┐
        │    PostgreSQL 16      │ │      MongoDB 7        │
        │   (container `db`)    │ │   (container `mongo`)  │
        │                        │ │                        │
        │ e_commerce_user        │ │ product_specs          │
        │ e_commerce_category    │ │ reviews                │
        │ e_commerce_product     │ │                        │
        │ e_commerce_order       │ │                        │
        │ e_commerce_orderitem   │ │                        │
        │ e_commerce_cart(item)  │ │                        │
        │ e_commerce_wishlist    │ │                        │
        │ + vue, index, trigger, │ │                        │
        │   rôle restreint       │ │                        │
        └─────────────────────┘ └─────────────────────┘
```

Deux rôles PostgreSQL distincts : un rôle *owner* (bootstrap, utilisé
uniquement par l'entrypoint pour `migrate` et pour créer la vue/l'index/le
trigger/le rôle restreint) et `commerce_app` (DML seulement, utilisé par
l'application à l'exécution -- voir section 5). Les tables sont créées par
les migrations Django (le projet SÎKÂ existant avait déjà un historique de
migrations cohérent) ; la vue, l'index, le trigger et le rôle restreint
sont ajoutés par-dessus par `docker/init-sql/01-extras.sql`, appliqué à chaque
démarrage du conteneur (idempotent) par la commande `setup_relational_extras`.

`api/reviews/services.py` centralise tout l'accès à MongoDB : le site HTML
(`e_commerce/views.py`) et l'API JSON (`reviews/views.py`) appellent les
mêmes fonctions, il n'y a pas deux implémentations de la même logique.

## 3. Modèle relationnel

### MCD (description)

- Un **Vendeur** (un `User` avec `is_seller=True`) publie plusieurs
  **Produits** (1,N).
- Une **Catégorie** regroupe plusieurs **Produits** (1,N) ; un **Produit**
  porte plusieurs **Tags** (N,N).
- Un **Client** passe plusieurs **Commandes** (1,N) ; une **Commande**
  contient plusieurs **Lignes de commande**, chacune référençant un
  **Produit** (association N,N entre Commande et Produit, portée par
  `OrderItem`).
- Un **Client** a un **Panier** avec plusieurs **Lignes de panier**, et une
  **Liste de souhaits** (produits favoris).

### MLD (tables réellement utilisées, noms générés par Django)

```
e_commerce_user(id, username, email, first_name, last_name, is_seller, is_seller_approved, ...)
e_commerce_category(id, name, slug, description, created_at)
e_commerce_tag(id, name, slug)
e_commerce_product(id, name, slug, description, price, category_id -> category.id,
                    seller_id -> user.id, stock, is_active, created_at, updated_at)
e_commerce_product_tags(id, product_id -> product.id, tag_id -> tag.id)
e_commerce_order(id, order_number, user_id -> user.id, status, payment_method,
                  payment_status, total_amount, delivery_address, created_at, updated_at)
e_commerce_orderitem(id, order_id -> order.id, product_id -> product.id, quantity, price)
e_commerce_wishlist(id, user_id -> user.id, product_id -> product.id, created_at)
```

### MPD (script de création commenté)

Les tables sont créées par les migrations Django
(`api/e_commerce/migrations/0001_initial.py` et suivantes). Le script
ci-dessous est le DDL PostgreSQL équivalent pour les tables principales
(reconstitué à partir de `models.py`, colonnes secondaires omises ; les noms
d'index et de contraintes générés par Django sont simplifiés). Schémas
graphiques : [`schemas/mld.svg`](schemas/mld.svg) et
[`schemas/architecture.svg`](schemas/architecture.svg).

```sql
-- Catégories : slug unique pour des URL stables
CREATE TABLE e_commerce_category (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    slug        VARCHAR(100) NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL
);

-- Utilisateurs (clients, vendeurs, admin) : email unique
CREATE TABLE e_commerce_user (
    id                 BIGSERIAL PRIMARY KEY,
    username           VARCHAR(150) NOT NULL UNIQUE,
    email              VARCHAR(254) NOT NULL UNIQUE,
    password           VARCHAR(128) NOT NULL,   -- hash, jamais en clair
    is_seller          BOOLEAN NOT NULL,
    is_seller_approved BOOLEAN NOT NULL,
    created_at         TIMESTAMPTZ NOT NULL
    -- + first_name, last_name, phone, address, store_* ...
);

-- Produits : prix décimal (pas de float pour l'argent), stock >= 0.
-- Catégorie supprimée -> produit conservé (SET NULL) ;
-- vendeur supprimé -> ses produits le sont aussi (CASCADE).
CREATE TABLE e_commerce_product (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(200) NOT NULL,
    slug        VARCHAR(220) NOT NULL UNIQUE,
    description TEXT NOT NULL,
    price       NUMERIC(10,2) NOT NULL,
    stock       INTEGER NOT NULL CHECK (stock >= 0),
    is_active   BOOLEAN NOT NULL,
    category_id BIGINT REFERENCES e_commerce_category(id) ON DELETE SET NULL,
    seller_id   BIGINT NOT NULL REFERENCES e_commerce_user(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX ON e_commerce_product (category_id);   -- index FK auto Django
CREATE INDEX ON e_commerce_product (seller_id);

-- Commandes : numéro unique ; total_amount maintenu par trigger (voir plus bas)
CREATE TABLE e_commerce_order (
    id             BIGSERIAL PRIMARY KEY,
    order_number   VARCHAR(20) NOT NULL UNIQUE,
    user_id        BIGINT NOT NULL REFERENCES e_commerce_user(id) ON DELETE CASCADE,
    status         VARCHAR(20) NOT NULL,
    payment_status VARCHAR(20) NOT NULL,
    total_amount   NUMERIC(10,2) NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL,
    updated_at     TIMESTAMPTZ NOT NULL
    -- + payment_method, delivery_address, phone, notes ...
);

-- Lignes de commande : le prix est copié au moment de l'achat (historique
-- stable même si le prix du produit change). Produit supprimé -> SET NULL.
CREATE TABLE e_commerce_orderitem (
    id         BIGSERIAL PRIMARY KEY,
    order_id   BIGINT NOT NULL REFERENCES e_commerce_order(id) ON DELETE CASCADE,
    product_id BIGINT REFERENCES e_commerce_product(id) ON DELETE SET NULL,
    quantity   INTEGER NOT NULL CHECK (quantity >= 0),
    price      NUMERIC(10,2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

-- Panier et liste de souhaits : un seul enregistrement par (panier, produit)
-- et par (utilisateur, produit)
CREATE TABLE e_commerce_cartitem (
    id         BIGSERIAL PRIMARY KEY,
    cart_id    BIGINT NOT NULL,       -- FK e_commerce_cart ON DELETE CASCADE
    product_id BIGINT NOT NULL REFERENCES e_commerce_product(id) ON DELETE CASCADE,
    quantity   INTEGER NOT NULL CHECK (quantity >= 0),
    UNIQUE (cart_id, product_id)
);
CREATE TABLE e_commerce_wishlist (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES e_commerce_user(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES e_commerce_product(id) ON DELETE CASCADE,
    UNIQUE (user_id, product_id)
);
-- + e_commerce_tag, e_commerce_product_tags (N-N), e_commerce_productimage,
--   e_commerce_cart, e_commerce_sellerrequest
```

Par-dessus, `docker/init-sql/01-extras.sql` (appliqué à chaque démarrage par
`setup_relational_extras`, idempotent) ajoute :

```sql
-- CHECK explicite : un prix ne peut pas être négatif
ALTER TABLE e_commerce_product
    ADD CONSTRAINT product_price_non_negative CHECK (price >= 0);

-- Index choisi volontairement (mesuré en section 7)
CREATE INDEX IF NOT EXISTS idx_order_created_at ON e_commerce_order (created_at);

-- Vue utilisée par GET /api/reports/sales-by-category/
CREATE OR REPLACE VIEW category_sales_view AS ...;   -- LEFT JOIN + GROUP BY

-- Logique serveur : total_amount recalculé à chaque changement de ligne
CREATE OR REPLACE FUNCTION recalc_order_total() RETURNS TRIGGER AS $$ ... $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_recalc_order_total
AFTER INSERT OR UPDATE OR DELETE ON e_commerce_orderitem
FOR EACH ROW EXECUTE FUNCTION recalc_order_total();

-- Rôle applicatif : DML uniquement, pas de DDL, pas superutilisateur.
-- Le mot de passe vient de POSTGRES_APP_PASSWORD (.env), pas du script.
CREATE ROLE commerce_app LOGIN;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO commerce_app;
```

Le corps complet de la vue et du trigger est dans
`docker/init-sql/01-extras.sql`. Le schéma exact produit par les migrations
puis ce script est dans `docker/init-sql/reference/schema.sql` (sortie de
`pg_dump --schema-only`, à titre de documentation).

## 4. Modèle non relationnel (MongoDB)

Deux collections, peuplées par `seed_demo_data` et gérées par
`api/reviews/services.py` :

### `product_specs`

```json
{
  "_id": "...",
  "product_id": 1,
  "category": "Livres",
  "attributes": { "color": "vert", "weight_kg": 5.15, "warranty_months": 24 },
  "media": ["https://.../product1-1.jpg", "https://.../product1-2.jpg"],
  "tags": ["demo-data"],
  "updated_at": "2026-10-30T09:10:22Z"
}
```

`attributes`/`media`/`tags` sont **embarqués** : toujours lus avec la
fiche produit, de forme variable selon la catégorie (le poids n'a pas de
sens pour un ebook, par exemple). `product_id` est une **référence** vers
`e_commerce_product.id`, qui reste la source de vérité pour l'identité, le
prix et le stock du produit.

### `reviews`

```json
{
  "_id": "...",
  "product_id": 1002,
  "user_id": 31,
  "rating": 5,
  "comment": "Excellent produit, livraison rapide, je recommande fortement !",
  "created_at": "2026-10-30T09:15:47Z",
  "replies": []
}
```

`product_id` et `user_id` sont des **références** vers PostgreSQL
(identifiants partagés) ; `replies` est **embarqué** (borné, toujours
affiché avec son avis parent). La règle métier "un avis par produit et par
client, modifiable" est appliquée par un `update_one(..., upsert=True)`
sur la paire `(product_id, user_id)` (`upsert_review` dans
`reviews/services.py`), et toute écriture vérifie d'abord l'existence du
produit côté Postgres (`_require_product`).

Création : `docker/init-nosql/01-init-mongo.js`, exécuté par l'image `mongo`
au premier démarrage. Il crée les deux collections avec une validation
`$jsonSchema` (champs obligatoires, note entière entre 1 et 5 : une note de 9
est refusée par la base elle-même) et les index.

Index créés :
- `product_specs` : unique sur `product_id`.
- `reviews` : composé sur `{product_id: 1, created_at: -1}`.

CRUD complet exposé par l'API : lecture, création/mise à jour (`PUT`,
`POST`) et suppression (`DELETE`) sur les deux collections.

Pipeline d'agrégation : `$group` par `product_id` pour la note moyenne et
le nombre d'avis (`rating_stats`), variante `$group`/`$sort` pour la
distribution des notes 1 à 5 étoiles (`rating_distribution`).

## 5. Justification des choix techniques

**Pourquoi garder les migrations Django plutôt que du SQL écrit à la
main ?** Le projet SÎKÂ existait déjà avec un historique de migrations
cohérent sur 10 modèles et ~2000 lignes de vues/formulaires qui en
dépendent. Réécrire le schéma à la main aurait dupliqué ce travail sans
valeur ajoutée et risqué des incohérences. Les éléments explicitement
demandés par le sujet (vue, index, trigger, rôle restreint) sont ajoutés
par-dessus dans un script dédié (`setup_relational_extras`), ce qui
sépare clairement "ce que Django gère" de "ce qui répond au sujet BDD".

**Comment le rôle restreint cohabite avec les migrations Django ?** Deux
alias de connexion sur la même base (`sika/settings.py`) : `migration`
(rôle propriétaire, utilisé uniquement par l'entrypoint pour `migrate` et
`setup_relational_extras`) et `default` (rôle `commerce_app`, utilisé par
toute l'application -- site HTML et API -- à l'exécution). `commerce_app`
n'a que des droits `SELECT/INSERT/UPDATE/DELETE`, jamais de DDL ni de
superutilisateur ; vérifié en section 7.

**Pourquoi MongoDB pour les avis et les fiches techniques ?** Les
attributs produit varient selon la catégorie (incompatible avec des
colonnes SQL fixes sans tomber dans une table EAV peu lisible), et les
avis sont des documents indépendants, à forte volumétrie de lecture
(affichage public), jamais mis à jour en même temps qu'une commande.

**Comment les deux bases sont reliées ?** Par les identifiants entiers
`product_id`/`user_id`, jamais par une clé étrangère native (impossible
entre deux moteurs). PostgreSQL reste la source de vérité sur l'existence
de ces identifiants : toute écriture Mongo passant par l'API ou le site
vérifie d'abord que le produit existe côté Postgres avant d'écrire. La
cohérence entre les deux bases est donc assurée côté application, pas par
une contrainte native -- limite assumée, voir section 9.

## 6. Exemples de requêtes

1. **Vue + jointures** -- `GET /api/reports/sales-by-category/` lit
   `category_sales_view` (`LEFT JOIN` category/product/orderitem/order,
   filtré sur `payment_status='paid'`, `GROUP BY` catégorie). Intention :
   classer les catégories par chiffre d'affaires.

2. **Jointure interne + agrégat + tri** -- `GET
   /api/reports/top-selling-products/?limit=10` (`INNER JOIN`
   product/orderitem/order, `SUM()`, tri et limite). Intention : identifier
   les produits les plus vendus.

3. **`GROUP BY` / `HAVING`** -- `GET
   /api/reports/frequent-customers/?min_orders=3` : utilisateurs ayant
   passé plus de `min_orders` commandes.

4. **Sous-requête `NOT EXISTS`** -- `GET
   /api/reports/customers-without-orders/` : utilisateurs n'ayant jamais
   commandé.

5. **CTE + fonction fenêtrée** -- `GET /api/reports/monthly-revenue/` :
   `WITH monthly AS (...)` puis `SUM(revenue) OVER (ORDER BY month)` pour
   le cumul. Résultat réel sur le jeu de données de démo : 13 mois, de
   11 593 FCFA (octobre 2025) à 3 513 588 FCFA cumulés (octobre 2026).

6. **Agrégat `FILTER`** -- `GET /api/reports/order-status-breakdown/` :
   répartition des commandes par statut en une seule requête
   (`COUNT(*) FILTER (WHERE status = '...')`).

7. **Pipeline d'agrégation MongoDB** -- `GET
   /api/products/{id}/reviews/stats/` : note moyenne + nombre d'avis
   (`$group`), puis distribution des notes (`$group`/`$sort`).

8. **Filtres avec opérateurs sur champs imbriqués (MongoDB)** -- `GET
   /api/specs/search/?category=Électronique&min_weight=5&max_weight=8`
   (exact sur `attributes.color`, plage `$gte`/`$lte` sur
   `attributes.weight_kg`) ; `GET
   /api/products/{id}/reviews/?min_rating=4&has_replies=true` (`$gte` sur
   `rating`, présence (`$exists`) sur le tableau imbriqué `replies`).

9. **Écriture puis lecture croisée, en conditions réelles** -- un avis
   soumis depuis le formulaire HTML du site
   (`POST /products/{id}/review/`) est immédiatement visible à la fois sur
   la fiche produit HTML et via `GET /api/products/{id}/reviews/` : testé
   en conditions réelles (connexion, ajout panier, soumission d'avis via
   curl en simulant un navigateur), voir section 6 de la vidéo.

## 7. Index et performance

Index créé : `idx_order_created_at` sur `e_commerce_order(created_at)`.
Deux candidats ont été essayés et écartés avant celui-ci (détails en
commentaire dans `docker/init-sql/01-extras.sql`) :
- Un index sur `orderitem.product_id` s'est révélé redondant : Django crée
  automatiquement un index sur **toute** colonne de clé étrangère.
- Un index sur `order.payment_status` n'apportait rien : avec seulement 3
  valeurs possibles et ~60% des lignes à `'paid'`, le planificateur
  préfère toujours un balayage séquentiel, index ou non.

`created_at` est une colonne à forte cardinalité, pas une clé étrangère
(donc non indexée automatiquement), et sert aux requêtes par plage de
dates (reporting mensuel, tableaux de bord "commandes récentes"). Mesure
réelle sur `SELECT * FROM e_commerce_order WHERE created_at >= '2026-09-01'
AND created_at < '2026-10-01';` (3000 lignes dans `e_commerce_order`, ~256
lignes dans la plage) :

**Sans index** (`DROP INDEX idx_order_created_at;`) :
```
Seq Scan on e_commerce_order  (cost=0.00..340.00 rows=255 width=192)
                              (actual time=0.355..1.194 rows=256 loops=1)
  Filter: ((created_at >= ...) AND (created_at < ...))
  Rows Removed by Filter: 2744
  Buffers: shared hit=295
Execution Time: 1.343 ms
```

**Avec index** (`CREATE INDEX idx_order_created_at ...;`) :
```
Bitmap Heap Scan on e_commerce_order  (cost=...) (actual time=0.282..0.299 rows=256 loops=1)
  Recheck Cond: ((created_at >= ...) AND (created_at < ...))
  Heap Blocks: exact=134
  Buffers: shared hit=134 read=3
  ->  Bitmap Index Scan on idx_order_created_at
        (actual time=0.071..0.071 rows=256 loops=1)
        Buffers: shared read=3
Execution Time: 0.635 ms
```

Le plan passe d'un `Seq Scan` (295 buffers) à un `Bitmap Index Scan` (137
buffers), soit environ 2,1x plus rapide en temps d'exécution sur ce volume
de démonstration -- l'écart se creuserait avec un catalogue de commandes
plus proche d'un volume réel.

## 8. Stratégie de sauvegarde

- **PostgreSQL** : sauvegarde logique via `pg_dump` du volume nommé
  `pgdata` (ex. `docker compose exec db sh -c 'pg_dump -U $POSTGRES_USER
  sika' > backup.sql`), restauration via `docker compose exec -T db sh -c
  'psql -U $POSTGRES_USER sika' < backup.sql` sur une base vide.
- **MongoDB** : `docker compose exec mongo sh -c 'mongodump --archive
  -u $MONGO_INITDB_ROOT_USERNAME -p $MONGO_INITDB_ROOT_PASSWORD
  --authenticationDatabase admin --db sika' > mongo.archive`, restauration
  avec `mongorestore --archive` (mêmes options d'authentification) en
  redirigeant le fichier sur l'entrée standard.
- **Médias** (images produit/vendeur) : volume nommé `media_data`, à
  sauvegarder avec un simple `docker run --rm -v
  docker_media_data:/data -v $(pwd):/backup busybox tar czf
  /backup/media.tar.gz /data`.
- Pour ce projet de démonstration, ces sauvegardes ne sont pas
  automatisées (pas de cron) -- choix documenté : un volume Docker nommé
  suffit à persister les données entre `docker compose down`/`up`, et
  `seed_demo_data` (idempotent) permet de reconstruire un jeu de données
  de démonstration à l'identique en cas de perte totale.

## 9. Limites et pistes d'amélioration

- **Cohérence inter-bases non transactionnelle** : un produit supprimé
  côté Postgres ne purge pas automatiquement ses documents Mongo associés
  (`product_specs`, `reviews`). Une tâche de nettoyage périodique ou un
  flux d'événements (CDC) serait nécessaire en production.
- **MongoDB avec un seul compte administrateur** : l'authentification est
  activée (identifiants dans `.env`), mais l'application utilise le compte
  root de l'instance. Un utilisateur applicatif limité à la base `sika`
  (rôle `readWrite`), symétrique de `commerce_app`, serait la suite logique.
- **Authentification par jeton simple** : l'API utilise les jetons DRF
  (`/api/auth/token/`) : un jeton par utilisateur, sans expiration ni
  rotation. Une mise en production utiliserait des jetons à durée limitée
  (JWT) et du HTTPS. Les lectures du catalogue restent publiques par choix.
- **`total_amount` recalculé par trigger, pas par le code applicatif** :
  volontaire (voir section 5), mais signifie que toute modification
  directe en SQL d'une ligne de commande doit passer par de vraies
  requêtes SQL (pas de bypass du trigger) pour rester cohérente -- déjà le
  cas avec `bulk_create`, qui déclenche bien le trigger ligne par ligne.
- **Emails en mode console par défaut** : pas de vrai envoi SMTP sans
  configuration explicite (`.env`) -- choix assumé pour ne pas exiger de
  compte email réel pour faire tourner ou corriger le projet.

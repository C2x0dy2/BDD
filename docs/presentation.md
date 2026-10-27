# Document de présentation -- Commerce (EFREI M1 Dev, Projet BDD)

## 1. Le projet

Application e-commerce de démonstration : un catalogue de produits organisés
par catégories, des clients, des commandes avec leurs lignes, des avis
clients et des fiches produit enrichies. L'objectif pédagogique est de
répartir ces données entre deux familles de bases selon la nature de
chaque donnée, et de les exposer via une seule API.

Utilisateurs cibles (fictifs, pour la démonstration) : des clients qui
consultent le catalogue, lisent des avis, et passent commande ; une équipe
interne qui consulte des rapports de ventes.

Fonctionnalités principales :
- Catalogue produits/catégories avec CRUD complet.
- Clients et commandes (avec lignes de commande), total recalculé
  automatiquement côté base.
- Avis clients et fiches produit enrichies (specs flexibles par catégorie).
- Un endpoint qui fusionne les deux bases pour la fiche produit complète.
- Des rapports SQL avancés (ventes par catégorie, clients fréquents,
  chiffre d'affaires mensuel cumulé, etc.).

## 2. Architecture

```
                          ┌───────────────────────┐
                          │        Client          │
                          │ (curl / navigateur /    │
                          │  Adminer / Mongo Express)│
                          └───────────┬───────────┘
                                      │ HTTP (JSON)
                                      ▼
                          ┌───────────────────────┐
                          │   API Django + DRF      │
                          │   (container `api`)     │
                          └──────┬───────────┬──────┘
                                 │           │
                     ORM Django  │           │  pymongo (accès direct,
                     (lecture/   │           │  pas d'ORM)
                     écriture)   ▼           ▼
                     ┌─────────────────┐ ┌─────────────────┐
                     │   PostgreSQL 16  │ │    MongoDB 7     │
                     │  (container `db`)│ │ (container `mongo`)│
                     │                  │ │                  │
                     │ categories       │ │ product_specs    │
                     │ products         │ │ reviews          │
                     │ customers        │ │                  │
                     │ orders           │ │                  │
                     │ order_items      │ │                  │
                     │ + vue, index,    │ │                  │
                     │   trigger, rôle  │ │                  │
                     │   restreint      │ │                  │
                     └─────────────────┘ └─────────────────┘
```

L'API ne connaît jamais les deux bases comme un bloc monolithique : chaque
app Django a une responsabilité unique (`catalog`/`orders` -> ORM Postgres,
`reviews` -> pymongo direct, `reports` -> SQL brut en lecture). L'endpoint
croisé (`/api/products/{id}/details/`) est le seul point du code qui
interroge explicitement les deux bases pour construire une réponse.

## 3. Modèle relationnel

### MCD (description)

- Une **Catégorie** possède plusieurs **Produits** (1,N).
- Un **Client** passe plusieurs **Commandes** (1,N).
- Une **Commande** contient plusieurs **Lignes de commande**, chacune
  référençant un **Produit** et une quantité (association N,N entre
  Commande et Produit, portée par `order_items`).

### MLD

```
categories(id, name, slug)
products(id, sku, name, category_id -> categories.id, price, stock_quantity, created_at)
customers(id, email, first_name, last_name, created_at)
orders(id, customer_id -> customers.id, status, total_amount, created_at)
order_items(id, order_id -> orders.id, product_id -> products.id, quantity, unit_price)
```

### MPD (script de création commenté)

Voir [`docker/init-sql/01_schema.sql`](../docker/init-sql/01_schema.sql).
Points clés :
- Clés primaires `BIGSERIAL`, clés étrangères avec `ON DELETE
  RESTRICT`/`CASCADE` selon le sens métier (on ne supprime pas une catégorie
  encore référencée ; les lignes de commande disparaissent avec leur
  commande).
- Contraintes `NOT NULL`, `UNIQUE` (email client, SKU produit, slug
  catégorie), `CHECK` (prix et stock non négatifs, statut de commande dans
  une liste fermée, quantité strictement positive).
- `order_items` a une contrainte `UNIQUE(order_id, product_id)` : un produit
  n'apparaît qu'une fois par commande.
- Les modèles Django correspondants (`catalog/models.py`, `orders/models.py`)
  sont déclarés `managed = False` : ce script SQL est la seule source de
  vérité du schéma, Django ne fait jamais de `migrate` sur ces tables.

## 4. Modèle non relationnel (MongoDB)

Deux collections, peuplées et indexées par
[`docker/init-nosql/01_seed.js`](../docker/init-nosql/01_seed.js) :

### `product_specs`

```json
{
  "_id": "...",
  "product_id": 1,
  "category": "Books",
  "attributes": { "color": "green", "weight_kg": 9.29, "warranty_months": 24 },
  "media": ["https://.../product1-1.jpg", "https://.../product1-2.jpg"],
  "tags": ["books", "demo-data"],
  "updated_at": "2026-01-07T14:01:27Z"
}
```

`attributes`, `media` et `tags` sont **embarqués** : ils sont toujours lus
avec la fiche produit, et leur forme varie selon la catégorie (un vêtement
n'a pas les mêmes attributs qu'un livre) -- un schéma SQL figé imposerait
soit des colonnes toujours vides, soit une table clé/valeur peu lisible.
`product_id` est une **référence** vers `products.id` dans PostgreSQL, qui
reste la source de vérité pour l'identité, le prix et le stock du produit.

### `reviews`

```json
{
  "_id": "...",
  "product_id": 5,
  "customer_id": 1,
  "rating": 5,
  "title": "Great",
  "body": "Loved it",
  "created_at": "2026-10-05T14:04:34Z",
  "replies": [
    { "author": "support-team", "body": "Thanks for your feedback...", "created_at": "..." }
  ]
}
```

`replies` est **embarqué** : borné (quelques réponses par avis au plus),
toujours affiché avec son avis parent, jamais interrogé seul. `product_id`
et `customer_id` sont des **références** vers PostgreSQL (identifiants
partagés), qui reste la source de vérité sur l'identité des produits et des
clients.

Index créés :
- `product_specs`: unique sur `product_id` (une fiche specs par produit).
- `reviews`: composé sur `{product_id: 1, created_at: -1}` (tri des avis
  récents par produit, le pattern d'accès le plus fréquent).

## 5. Justification des choix techniques

**Pourquoi PostgreSQL pour le catalogue/clients/commandes ?** Ces données
sont fortement structurées et relationnelles (une commande référence un
client et des produits existants ; un total doit rester cohérent avec ses
lignes) : les contraintes d'intégrité référentielle, les transactions, et
les jointures sont exactement ce pour quoi un SGBDR est fait.

**Pourquoi MongoDB pour les specs produit et les avis ?** Les attributs
produit varient selon la catégorie (poids pour un livre n'a pas de sens pour
un logiciel, par exemple), et les avis sont des documents indépendants,
jamais mis à jour en même temps qu'une autre table, dont le volume de
lecture (affichage public) dépasse largement le volume d'écriture. Forcer
ces données dans des colonnes SQL fixes aurait nécessité soit une table EAV
(peu lisible, peu performante), soit des colonnes `NULL` à la majorité.

**Comment les deux bases sont reliées ?** Par des identifiants entiers
partagés (`product_id`, `customer_id`), jamais par une clé étrangère native
(impossible entre deux moteurs différents). PostgreSQL est la source de
vérité sur l'existence de ces identifiants : tout écrit Mongo passant par
l'API (`POST /reviews/`, `PUT /specs/`) vérifie d'abord que le produit
existe côté Postgres (`_require_product`, voir `api/reviews/views.py`) avant
d'écrire, pour éviter des documents Mongo orphelins. La cohérence entre les
deux bases est donc assurée côté application, pas par une contrainte native
-- c'est la limite assumée d'une architecture polyglotte (voir section 9).

## 6. Exemples de requêtes

1. **Vue + jointures** -- `GET /api/reports/sales-by-category/` lit
   `category_sales_view`, qui fait un `LEFT JOIN` categories/products/
   order_items/orders puis un `GROUP BY` catégorie, pour inclure même les
   catégories sans aucune vente. Intention : classer les catégories par
   chiffre d'affaires.

2. **Jointure interne + agrégat + tri** -- `GET
   /api/reports/top-selling-products/?limit=10` fait un `INNER JOIN`
   products/order_items/orders filtré sur les commandes payées/expédiées,
   `SUM()` les quantités et le revenu, trie et limite. Intention :
   identifier les produits les plus vendus.

3. **`GROUP BY` / `HAVING`** -- `GET
   /api/reports/frequent-customers/?min_orders=3` renvoie les clients ayant
   passé strictement plus de `min_orders` commandes. Intention : repérer
   les clients fidèles.

4. **Sous-requête `NOT EXISTS`** -- `GET
   /api/reports/customers-without-orders/` renvoie les clients n'ayant
   jamais commandé. Intention : cibler une relance marketing.

5. **CTE + fonction fenêtrée** -- `GET /api/reports/monthly-revenue/`
   calcule le revenu mensuel dans un `WITH monthly AS (...)`, puis une
   colonne de cumul avec `SUM(revenue) OVER (ORDER BY month)`. Intention :
   suivre la trajectoire de chiffre d'affaires.

6. **Agrégat `FILTER`** -- `GET /api/reports/order-status-breakdown/`
   compte les commandes par statut en une seule requête
   (`COUNT(*) FILTER (WHERE status = '...')`) plutôt qu'une requête par
   statut. Intention : tableau de bord opérationnel.

7. **Pipeline d'agrégation MongoDB** -- `GET
   /api/products/{id}/reviews/stats/` fait un `$group` pour la note
   moyenne et le nombre d'avis, puis un second `$group`/`$sort` pour la
   distribution des notes (1 à 5 étoiles). Intention : afficher la note
   moyenne et son détail sur la fiche produit.

8. **Filtres avec opérateurs sur champs imbriqués (MongoDB)** -- `GET
   /api/specs/search/?category=Electronics&min_weight=5&max_weight=8`
   filtre `product_specs` sur un champ imbriqué exact (`attributes.color`)
   et une plage sur un autre champ imbriqué (`attributes.weight_kg` avec
   `$gte`/`$lte`). De même, `GET
   /api/products/{id}/reviews/?min_rating=4&has_replies=true` combine un
   opérateur `$gte` sur `rating` et un filtre de présence (`$exists`) sur le
   tableau imbriqué `replies`. Intention : retrouver des produits par
   caractéristique physique, ou des avis notables avec suivi du support.

## 7. Index et performance

Index créé : `idx_order_items_product_id` sur `order_items(product_id)`,
justifié par les lookups fréquents "commandes contenant le produit X" et les
rapports de revenu par produit (`top-selling-products`,
`category_sales_view`).

Mesure réelle, requête `SELECT * FROM order_items WHERE product_id = 500;`
sur le jeu de données de démonstration (7 500 lignes dans `order_items`) :

**Sans index** (`DROP INDEX idx_order_items_product_id;`) :
```
Seq Scan on order_items  (cost=0.00..156.75 rows=4 width=34)
                         (actual time=0.136..0.427 rows=5 loops=1)
  Filter: (product_id = 500)
  Rows Removed by Filter: 7497
  Buffers: shared hit=63
Execution Time: 0.460 ms
```

**Avec index** (`CREATE INDEX idx_order_items_product_id ...;`) :
```
Bitmap Heap Scan on order_items  (cost=4.31..17.34 rows=4 width=34)
                                 (actual time=0.075..0.083 rows=5 loops=1)
  Recheck Cond: (product_id = 500)
  Heap Blocks: exact=5
  Buffers: shared hit=9 read=1
  ->  Bitmap Index Scan on idx_order_items_product_id
        (actual time=0.066..0.066 rows=5 loops=1)
        Buffers: shared hit=4 read=1
Execution Time: 0.121 ms
```

Le plan passe d'un `Seq Scan` (lecture des 7 500 lignes, 63 buffers) à un
`Bitmap Index Scan` (10 buffers), soit environ 3,8x plus rapide en temps
d'exécution sur ce volume de démonstration. L'écart se creuserait encore
avec un volume de données plus proche d'un catalogue réel.

## 8. Stratégie de sauvegarde

- **PostgreSQL** : sauvegarde logique quotidienne via `pg_dump` du volume
  nommé `pgdata` (ex. `docker compose exec db pg_dump -U postgres_admin
  commerce > backup.sql`), conservée 7 jours en rotation. Restauration via
  `psql -U postgres_admin commerce < backup.sql` sur une base vide.
- **MongoDB** : sauvegarde quotidienne via `mongodump --db commerce`,
  restauration via `mongorestore`.
- Pour ce projet de démonstration, ces sauvegardes ne sont pas automatisées
  (pas de cron) : c'est un choix documenté, pas un oubli -- un volume Docker
  nommé suffit à persister les données entre `docker compose down`/`up`,
  et un script de seed reproductible (`docker/init-sql`, `docker/init-nosql`)
  permet de reconstruire un jeu de données de démonstration à l'identique en
  cas de perte.

## 9. Limites et pistes d'amélioration

- **Cohérence inter-bases non transactionnelle** : un produit supprimé côté
  Postgres (actuellement impossible via l'API tant qu'il a des commandes ou
  specs, par `ON DELETE RESTRICT`) ne purge pas automatiquement ses
  documents Mongo associés. Une tâche de nettoyage périodique ou un flux
  d'événements (ex. Debezium/CDC) serait nécessaire pour une vraie
  synchronisation en production.
- **MongoDB sans authentification** : accepté pour ce projet académique où
  seul le réseau Docker interne y accède ; à corriger avant tout usage réel
  (`MONGO_INITDB_ROOT_USERNAME`/`PASSWORD` + utilisateur applicatif dédié,
  symétrique du rôle `commerce_app` déjà en place côté PostgreSQL).
- **API sans authentification** : choix délibéré pour simplifier la
  démonstration ; une vraie mise en production ajouterait une authentification
  par token et des permissions par rôle.
- **Pas de cache** : une troisième base (Redis) pourrait mettre en cache les
  endpoints de rapports les plus coûteux (sales-by-category,
  monthly-revenue), mais n'a pas été ajoutée car non nécessaire au volume de
  démonstration actuel -- c'est un bonus explicitement non exigé par le
  sujet.
- **Frontend** : non fourni (bonus non exigé par le sujet) ; l'API est
  démontrée via curl/Postman et les interfaces Adminer/Mongo Express.

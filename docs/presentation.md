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
sont ajoutés par-dessus par
`api/e_commerce/management/commands/setup_relational_extras.py`, exécutée
à chaque démarrage du conteneur (idempotente).

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

### MPD (script de création)

Les tables sont créées par les migrations Django
(`api/e_commerce/migrations/0001_initial.py` et suivantes) : clés primaires
auto-incrémentées, clés étrangères (`on_delete=PROTECT/CASCADE/SET_NULL`
selon le sens métier), `unique=True` (email, slug produit, numéro de
commande), et des contraintes `CHECK` générées automatiquement par Django
pour tous les champs `PositiveIntegerField` (stock, quantité). Par-dessus,
`setup_relational_extras.py` ajoute une contrainte `CHECK` explicite
supplémentaire (`price >= 0` sur `e_commerce_product`), une vue, un index,
et un trigger -- détaillés en section 7.

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

Index créés :
- `product_specs` : unique sur `product_id`.
- `reviews` : composé sur `{product_id: 1, created_at: -1}`.

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
Deux candidats ont été essayés et écartés avant celui-ci (détails dans
`api/e_commerce/management/commands/setup_relational_extras.py`) :
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
  `pgdata` (ex. `docker compose exec db pg_dump -U postgres_admin sika >
  backup.sql`), restauration via `psql -U postgres_admin sika <
  backup.sql` sur une base vide.
- **MongoDB** : `mongodump --db sika`, restauration via `mongorestore`.
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
- **MongoDB sans authentification** : accepté pour ce projet académique
  où seul le réseau Docker interne y accède ; à corriger avant tout usage
  réel (utilisateur applicatif dédié, symétrique de `commerce_app`).
- **API sans authentification** : les endpoints `/api/` sont ouverts (le
  site HTML, lui, a sa propre authentification par session) ; une vraie
  mise en production ajouterait une authentification par token sur l'API
  également.
- **`total_amount` recalculé par trigger, pas par le code applicatif** :
  volontaire (voir section 5), mais signifie que toute modification
  directe en SQL d'une ligne de commande doit passer par de vraies
  requêtes SQL (pas de bypass du trigger) pour rester cohérente -- déjà le
  cas avec `bulk_create`, qui déclenche bien le trigger ligne par ligne.
- **Emails en mode console par défaut** : pas de vrai envoi SMTP sans
  configuration explicite (`.env`) -- choix assumé pour ne pas exiger de
  compte email réel pour faire tourner ou corriger le projet.

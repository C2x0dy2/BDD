# Commerce -- Projet BDD relationnelles et non relationnelles (EFREI M1 Dev)

Application e-commerce de démonstration combinant **PostgreSQL** (catalogue,
clients, commandes) et **MongoDB** (fiches produit flexibles, avis clients),
exposées via une API Django REST Framework.

## Pile technique

| Composant       | Techno                                   | Rôle |
|-----------------|-------------------------------------------|------|
| Relationnelle   | PostgreSQL 16                              | Source de vérité : identité produit, prix, stock, clients, commandes |
| Non relationnelle | MongoDB 7                                | Specs produit flexibles (`product_specs`) et avis (`reviews`) |
| API             | Django 5 + Django REST Framework           | Expose les deux bases, endpoint croisé, rapports SQL avancés |
| Infra           | Docker Compose                             | Démarrage et peuplement en une commande |
| Confort démo    | Adminer, Mongo Express                     | Inspection visuelle des deux bases dans un navigateur |

Voir [`docs/presentation.md`](docs/presentation.md) pour l'architecture détaillée,
la justification des choix techniques, les modèles de données, et les mesures
de performance.

## Démarrage (< 5 minutes)

Prérequis : Docker + Docker Compose.

```bash
cp .env.example .env
cd docker
docker compose up -d --build
```

Au premier démarrage, PostgreSQL et MongoDB créent leur schéma et se peuplent
automatiquement (quelques milliers de lignes/documents) via les scripts dans
`docker/init-sql/` et `docker/init-nosql/`. Aucune manipulation manuelle
supplémentaire n'est nécessaire.

Vérifier que tout est en place :

```bash
docker compose ps
curl http://localhost:8000/api/products/
```

## URLs

| Service        | URL                              |
|----------------|-----------------------------------|
| API            | http://localhost:8000/api/        |
| Adminer (Postgres) | http://localhost:8080 (système : PostgreSQL, serveur : `db`, utilisateur : `postgres_admin`, mot de passe : `postgres_admin_pw`, base : `commerce`) |
| Mongo Express  | http://localhost:8081             |

Pas de comptes applicatifs : l'API est ouverte, sans authentification (voir
justification dans `docs/presentation.md`). Le rôle PostgreSQL utilisé par
l'API (`commerce_app`) est un rôle restreint, sans droits DDL.

## Endpoints principaux

Relationnel (PostgreSQL, CRUD) :
- `GET/POST /api/categories/`, `GET/PUT/PATCH/DELETE /api/categories/{id}/`
- `GET/POST /api/products/` (`?category=<id>`), `.../{id}/`
- `GET/POST /api/customers/`, `.../{id}/`
- `GET/POST /api/orders/` (`?customer=<id>`), `.../{id}/` -- création avec
  `items_input: [{product, quantity}, ...]` ; `total_amount` est recalculé
  côté base par un trigger, jamais par l'application.

Non relationnel (MongoDB, CRUD) :
- `GET/PUT /api/products/{id}/specs/`
- `GET /api/specs/search/?category=&color=&min_weight=&max_weight=` -- filtre
  sur des champs imbriqués (`attributes.color`, `attributes.weight_kg`) avec
  des opérateurs (`$gte`/`$lte`).
- `GET/POST /api/products/{id}/reviews/` (`?min_rating=&has_replies=`) --
  filtre sur `rating` (`$gte`) et sur la présence de réponses imbriquées
  (`$exists`).
- `GET /api/products/{id}/reviews/stats/` (pipeline d'agrégation)

Endpoint croisé (PostgreSQL + MongoDB) :
- `GET /api/products/{id}/details/` -- fusionne identité/prix/stock (Postgres)
  avec specs et note moyenne (MongoDB).

Rapports (requêtes SQL avancées) :
- `GET /api/reports/sales-by-category/` (vue `category_sales_view`)
- `GET /api/reports/top-selling-products/?limit=10`
- `GET /api/reports/categories-with-product-counts/`
- `GET /api/reports/frequent-customers/?min_orders=3`
- `GET /api/reports/customers-without-orders/`
- `GET /api/reports/monthly-revenue/`
- `GET /api/reports/order-status-breakdown/`

## Arborescence

```
/api                 Code source de l'API (Django + DRF)
/docker               docker-compose.yml, scripts d'init SQL et NoSQL
/docker/init-sql       Schéma PostgreSQL : tables, vue, index, trigger, rôle restreint, seed
/docker/init-nosql     Collections MongoDB : seed + index
/docs                 Document de présentation, schémas, vidéo
```

## Outils IA utilisés

Ce projet a été construit avec l'assistance de Claude (Anthropic), via
Claude Code, pour la conception de l'architecture, l'écriture du code
(modèles Django, vues DRF, schéma SQL, scripts de seed, Docker Compose) et la
documentation. Chaque choix a été revu et validé avant d'être conservé.

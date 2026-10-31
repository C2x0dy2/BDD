# SÎKÂ -- Projet BDD relationnelles et non relationnelles (EFREI M1 Dev)

Marketplace e-commerce complète (clients, vendeurs, panier, commandes, avis)
combinant **PostgreSQL** (identité, catalogue, commandes) et **MongoDB**
(fiches produit flexibles, avis clients), exposée à la fois par un site
web Django traditionnel et par une API REST.

## Pile technique

| Composant       | Techno                                   | Rôle |
|-----------------|-------------------------------------------|------|
| Relationnelle   | PostgreSQL 16                              | Source de vérité : utilisateurs, produits, panier, commandes |
| Non relationnelle | MongoDB 7                                | Avis produits (`reviews`) et fiches techniques flexibles (`product_specs`) |
| Application     | Django 5 (site HTML + templates)           | Inscription, panier, checkout, espace vendeur, avis |
| API             | Django REST Framework (`/api/`)            | Endpoint croisé, rapports SQL avancés, CRUD Mongo |
| Infra           | Docker Compose                             | Démarrage, migration, peuplement en une commande |
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

Au premier démarrage, l'entrypoint du conteneur `api`
(`api/entrypoint.sh`) exécute dans l'ordre : `migrate` (avec le rôle
propriétaire), la création de la vue/index/trigger/rôle restreint
(`setup_relational_extras`), le peuplement de démonstration
(`seed_demo_data`, PostgreSQL **et** MongoDB), puis démarre le serveur.
Aucune manipulation manuelle supplémentaire n'est nécessaire.

Vérifier que tout est en place :

```bash
docker compose ps
curl http://localhost:8000/api/reports/sales-by-category/
```

## URLs

| Service        | URL                              |
|----------------|-----------------------------------|
| Site e-commerce | http://localhost:8000/            |
| Admin Django (Jazzmin) | http://localhost:8000/admin/ |
| API            | http://localhost:8000/api/        |
| Adminer (Postgres) | http://localhost:8090 (système : PostgreSQL, serveur : `db`, base : `sika`, utilisateur et mot de passe : `POSTGRES_USER` / `POSTGRES_PASSWORD` de votre `.env`) |
| Mongo Express  | http://localhost:8091             |

Aucun mot de passe n'est versionné : tous les identifiants (PostgreSQL,
MongoDB avec authentification activée) viennent du fichier `.env`, copié
depuis `.env.example`. Si vous aviez déjà lancé une version précédente de
la pile (MongoDB sans authentification), repartez de zéro avec
`docker compose down -v`.

Comptes de démonstration : tous les comptes créés par `seed_demo_data`
(`user1@example.com` à `user1000@example.com`, les 30 premiers étant des
vendeurs) utilisent le mot de passe `DemoPass123!`. Un superutilisateur
Django doit être créé séparément si besoin (`docker compose exec api
python manage.py createsuperuser --database=migration`) : l'API et le
site n'exigent pas de compte admin pour fonctionner.

Le rôle PostgreSQL utilisé par l'application (`commerce_app`) est un rôle
restreint (DML uniquement, pas de DDL) -- voir
`api/e_commerce/management/commands/setup_relational_extras.py`.

## Endpoints API principaux

PostgreSQL (CRUD) :
- `GET/POST /api/products/` (`?seller=<id>`), `GET/PUT/PATCH/DELETE /api/products/{id}/`
- `PATCH /api/orders/{id}/status/`

Rapports (requêtes SQL avancées, lecture seule) :
- `GET /api/reports/sales-by-category/` (vue `category_sales_view`)
- `GET /api/reports/top-selling-products/?limit=10`
- `GET /api/reports/categories-with-product-counts/`
- `GET /api/reports/frequent-customers/?min_orders=3`
- `GET /api/reports/customers-without-orders/`
- `GET /api/reports/monthly-revenue/`
- `GET /api/reports/order-status-breakdown/`

MongoDB (CRUD + filtres sur champs imbriqués) :
- `GET/PUT/DELETE /api/products/{id}/specs/`
- `GET /api/specs/search/?category=&color=&min_weight=&max_weight=`
- `GET/POST /api/products/{id}/reviews/` (`?min_rating=&has_replies=`)
- `GET/PUT/DELETE /api/products/{id}/reviews/{user_id}/` (un avis = une paire produit/utilisateur)
- `GET /api/products/{id}/reviews/stats/` (pipeline d'agrégation)

Endpoint croisé (PostgreSQL + MongoDB) :
- `GET /api/products/{id}/details/` -- fusionne identité/prix/stock
  (Postgres) avec specs et note moyenne (MongoDB).

## Arborescence

```
/api                  Code source (Django + DRF)
/api/sika              Projet Django (settings, urls)
/api/e_commerce         App principale : modèles, vues HTML, templates, commandes de management
/api/reviews             MongoDB (pymongo direct) : specs produit + avis, utilisé par le site ET l'API
/api/reports              Rapports SQL avancés (lecture seule), exposés en API
/docker                docker-compose.yml
/docs                  Document de présentation, schémas (docs/schemas), vidéo (docs/video)
```

Écart assumé avec l'arborescence type du sujet : il n'y a pas de dossiers
`docker/init-sql` et `docker/init-nosql`. La création et le peuplement des
deux bases sont faits par des commandes Django exécutées automatiquement
par `api/entrypoint.sh` :

| Rôle | Fichier |
|------|---------|
| Tables, clés, contraintes (SQL) | `api/e_commerce/migrations/` |
| Vue, index, trigger, CHECK, rôle restreint (SQL) | `api/e_commerce/management/commands/setup_relational_extras.py` |
| Index MongoDB | `api/reviews/services.py` (`ensure_indexes`) |
| Peuplement PostgreSQL + MongoDB | `api/e_commerce/management/commands/seed_demo_data.py` |

Le script SQL complet (MPD) est reproduit dans `docs/presentation.md` §3.

## Outils IA utilisés

Ce projet a été construit avec l'assistance de Claude (Anthropic), via
Claude Code : adaptation du projet Django SÎKÂ existant pour fonctionner
sur PostgreSQL + MongoDB, écriture des commandes de management
(`setup_relational_extras`, `seed_demo_data`), de la couche API, de
l'infrastructure Docker, et de la documentation. Chaque choix a été revu
et validé avant d'être conservé.

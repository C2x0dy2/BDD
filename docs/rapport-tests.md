# Rapport de tests — SÎKÂ (PostgreSQL + MongoDB)

Date : 31/10/2026. Tests exécutés en réel sur la pile Docker démarrée à
vide (`docker compose down -v` puis `up -d --build`), avec des requêtes
`curl`, `psql`, `mongosh` et des scripts Python dans le conteneur `api`.

## Résultat global

| Domaine | Résultat |
|---|---|
| Démarrage d'une pile vierge, une commande | OK (21 s, images en cache) |
| PostgreSQL : schéma, contraintes, vue, index, trigger, rôle | OK |
| MongoDB : collections, index, filtres imbriqués, agrégation, authentification | OK |
| API : lecture/écriture sur les deux bases, endpoint croisé, erreurs | OK après 1 correction |
| Site HTML : pages et parcours d'écriture d'un avis | OK |
| Secrets versionnés | OK (uniquement des valeurs `change-me` dans `.env.example`) |
| Tests unitaires automatisés | **Absents (0 test)** |

## 1. Démarrage

- 5 conteneurs : `db` (healthy), `mongo` (healthy), `api`, `adminer`, `mongo-express`.
- L'entrypoint exécute `migrate`, `setup_relational_extras`, `seed_demo_data`, `collectstatic`, puis gunicorn : aucune manipulation manuelle.
- Le démarrage mesuré n'inclut pas le téléchargement des images Docker. Sur une machine vierge, le premier lancement sera plus long.

## 2. PostgreSQL

**Volumétrie** : 1000 utilisateurs, 10 catégories, 10 tags, 2000 produits, 3000 commandes, 7488 lignes de commande, 500 favoris. (Paniers vides au démarrage.)

**Contraintes** : 14 clés primaires, 18 clés étrangères. Violations testées et refusées par la base :

| Test | Résultat |
|---|---|
| `price = -1` | refusé (`product_price_non_negative`) |
| `stock = -1` | refusé (CHECK Django) |
| email dupliqué | refusé (`UNIQUE`) |
| slug produit dupliqué | refusé (`UNIQUE`) |
| ligne de commande avec commande inexistante | refusé (clé étrangère) |

**Trigger `recalc_order_total`** (dans une transaction annulée) : commande 1 à 1777,26 ; après insertion d'une ligne 2 × 10 → 1797,26 ; après suppression → 1777,26. Le total suit les lignes.

**Vue `category_sales_view`** : existe et renvoie les revenus par catégorie (ex. Livres : 2360 unités, 628 652,65).

**Index `idx_order_created_at`** — `EXPLAIN (ANALYZE, BUFFERS)` sur 256 lignes de 3000 :

| | Plan | Buffers | Temps d'exécution |
|---|---|---|---|
| Sans index | Seq Scan | 295 | 0,709 ms |
| Avec index | Bitmap Index Scan | 137 | 0,162 ms |

**Rôle applicatif `commerce_app`** (non superutilisateur) : `SELECT` et `UPDATE` autorisés ; `CREATE TABLE`, `DROP TABLE`, `ALTER TABLE`, `CREATE ROLE` refusés.
Remarque : le rôle de bootstrap `postgres_admin` est superutilisateur, mais il ne sert qu'à `migrate` et `setup_relational_extras`.

## 3. MongoDB

- Authentification active : une requête sans identifiants est refusée (`requires authentication`).
- Collections : `reviews` (3003 documents), `product_specs` (2000).
- Index : `reviews(product_id, created_at)` ; `product_specs(product_id)` unique. L'insertion d'un doublon est refusée.
- `explain` sur `reviews` pour un produit : 1 clé et 1 document examinés pour 1 résultat (l'index est utilisé).
- Filtre avec opérateurs sur champs imbriqués (`attributes.weight_kg` entre 5 et 8, catégorie Livres) : 70 documents.
- Pipeline d'agrégation : distribution des notes (597 / 587 / 628 / 631 / 560 pour 1 à 5 étoiles).

## 4. API

Tous les endpoints documentés dans le README ont été appelés.

| Groupe | Résultats |
|---|---|
| 7 rapports SQL | 200 |
| CRUD produits | création 201, lecture 200, `PATCH` 200, `DELETE` 204 ; ligne vérifiée en base ; inexistant 404 ; champs manquants ou prix négatif 400 |
| Statut de commande | valide 200, valeur inconnue 400, commande absente 404 |
| Fiches Mongo | `GET`/`PUT`/`DELETE` ; produit absent 404 ; corps invalide 400 |
| Avis Mongo | `POST` 201, `GET` 200, `PUT` 200, `DELETE` 204 puis 404 ; note hors 1–5 400 ; produit absent 404 |
| Recherche et stats Mongo | 200 |
| Endpoint croisé `/details/` | 200 (données PostgreSQL + MongoDB) ; produit absent 404 |
| JSON invalide | 400 |

**Parcours croisé réel** : connexion en tant que client (`user147`), avis soumis via le formulaire HTML, retrouvé immédiatement par `GET /api/products/904/reviews/147/` (note 5) ; les statistiques passent de 2 à 3 avis.

**Défaut trouvé et corrigé pendant les tests** : cinq paramètres de requête invalides provoquaient une erreur 500 au lieu d'un 400 (`limit=abc`, `limit=-5`, `min_orders=abc`, `min_weight=abc`, `min_rating=abc`). Corrigé dans `reports/views.py` et `reviews/views.py` ; les 5 cas renvoient maintenant 400, les valeurs valides renvoient toujours 200.

### Authentification et droits (ajoutés après la première série de tests)

Jeton obtenu via `POST /api/auth/token/` (mauvais mot de passe refusé). 31 cas testés :

| Cas | Résultat |
|---|---|
| Lectures (produits, détails, rapport de ventes) sans jeton | 200 |
| Écritures sans jeton (produit, commande, avis, specs) | 401 |
| Jeton invalide | 401 |
| Rapports contenant des emails clients : anonyme / client / admin | 401 / 403 / 200 |
| Client non vendeur crée un produit | 403 |
| Vendeur crée un produit en indiquant un autre vendeur | 201, vendeur réel = lui-même |
| Un vendeur modifie ou supprime le produit d'un autre | 403 |
| Un vendeur tente de changer le vendeur de son produit | ignoré |
| Admin supprime un produit | 204 |
| Statut de commande : client / vendeur concerné / admin | 403 / 200 / 200 |
| Avis posté en indiquant un autre `user_id` | 201, auteur réel = utilisateur connecté |
| Supprimer l'avis d'un autre | 403 |
| Modifier / supprimer son propre avis | 200 / 204 |
| Specs : client / vendeur du produit | 403 / 200 |

Le site HTML (accueil, catalogue, connexion) reste fonctionnel. Un compte
`admin` est créé par le peuplement (mot de passe de démonstration).

## 5. Site HTML

`/`, `/products/`, `/login/`, `/register/`, `/about/`, `/contact/`, `/admin/login/` : 200. `/cart/` sans connexion : 302 (redirection vers la connexion). Connexion avec le compte de démonstration : 302, puis accès au profil. Adminer et Mongo Express : 200.

## 6. Autres vérifications

- Persistance : après `docker compose restart api`, les données sont conservées.
- Secrets : `.env` n'est pas versionné ; seules des valeurs `change-me` figurent dans `.env.example`. Le mot de passe de démonstration `DemoPass123!` des comptes seed est documenté dans le README.

## 7. Ce qui n'est pas couvert

- **Aucun test automatisé** : `manage.py test` exécute 0 test (les fichiers `tests.py` sont vides). Les tests ci-dessus sont manuels. Ajouter quelques tests d'API serait la suite logique.
- Non testé : paiement, envoi d'emails, espace vendeur côté navigateur, inscription complète.
- Les tests ont modifié les données de démonstration (statut de la commande 1, un avis ajouté sur le produit 904, fiche produit 3 modifiée). Pour retrouver l'état initial avant la vidéo : `docker compose down -v` puis `docker compose up -d --build`.
- Les jetons n'expirent pas (limite documentée dans la présentation §9).

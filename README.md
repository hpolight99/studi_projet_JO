# Projet minimal JO — Réservation de tickets (FastAPI + PostgreSQL, HTML/CSS)

## Démarrage
1. Créez la base PostgreSQL et définissez `DATABASE_URL` (voir `.env.example`).
2. Appliquez le schéma :
   ```bash
   psql "$DATABASE_URL" -f db/init_db.sql
   ```
3. Installez et lancez :
   ```bash
   pip install -r requirements.txt
   uvicorn app:app --reload
   ```

## Pages
- Accueil `/`
- Offres `/offers`
- Connexion `/login`
- Inscription `/register`
- Admin (ajout d'offres) `/admin`

## Simplifications pédagogiques
- Paiement **mock** (aucun vrai débit).
- "QR code" = affichage de la **clé finale** (à encoder en image plus tard).
- Cookie de session simpliste (pas de JWT).

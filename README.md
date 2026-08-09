# Système de Pointage - Backend

Backend FastAPI pour un système de pointage.

## Installation

1. **Créer l'environnement virtuel** (si pas déjà fait)
   ```bash
   python -m venv env
   ```

2. **Activer l'environnement virtuel**
   ```bash
   # Windows
   .\env\Scripts\activate
   
   # Linux/Mac
   source env/bin/activate
   ```

3. **Installer les dépendances**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurer les variables d'environnement**
   - Créer/modifier le fichier `.env` avec vos credentials

## Lancer l'application

```bash
uvicorn main:app --reload
```

L'API sera disponible sur `http://localhost:8000`

## Documentation API

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Structure du projet

```
backend/
├── main.py              # Point d'entrée de l'application
├── requirements.txt     # Dépendances Python
├── .env                 # Variables d'environnement (à créer)
├── database/
│   └── database.py      # Configuration SQLAlchemy
├── models/              # Modèles de données
│
├── routes/              # Routes décrivants fonctionnalités
├── shemas/              # Types de données manipulés
├── services/            # Logique métier
├── auth/                # Authentification
└── assets/              # Fichiers ML et ressources
```

## Technologies

- **FastAPI** - Framework web moderne
- **SQLAlchemy** - ORM pour base de données
- **PyMySQL** - Driver MySQL
- **Pydantic** - Validation de données
- **Alembic** - création et mise à jour des tables de la bd

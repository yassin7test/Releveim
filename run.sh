#!/bin/bash

# ========================================
# Bank Statement Processor - Relevés Bancaires Marocains
# ========================================

echo "========================================"
echo "  Bank Statement Processor"
echo "  Relevés Bancaires Marocains"
echo "========================================"
echo ""

# Vérifier si Python est installé
if ! command -v python3 &> /dev/null; then
    echo "[ERREUR] Python 3 n'est pas installé"
    echo "Veuillez installer Python 3.8+ depuis https://python.org"
    exit 1
fi

# Créer l'environnement virtuel si nécessaire
if [ ! -d "venv" ]; then
    echo "Création de l'environnement virtuel..."
    python3 -m venv venv
fi

# Activer l'environnement
source venv/bin/activate

# Installer les dépendances si nécessaire
if [ ! -f "venv/installed" ]; then
    echo "Installation des dépendances..."
    pip install -r requirements.txt
    touch venv/installed
fi

# Exécuter le programme avec les arguments passés
python3 main.py "$@"

# Désactiver l'environnement
deactivate

# Bank Statement Processor - Relevés Bancaires Marocains

Application Python pour extraire automatiquement les transactions des relevés bancaires PDF des banques marocaines et les convertir en formats d'import pour **Sage Comptabilité**.

## Banques Supportées

| Banque | Statut | Détection Auto |
|--------|--------|----------------|
| **Attijariwafa Bank** | ✅ Opérationnel | ✅ Oui |
| **CIH Bank** | ✅ Opérationnel | ✅ Oui |
| **Banque Populaire (BCP)** | ✅ Opérationnel | ✅ Oui |

## Formats Sage Supportés

| Format | Extension | Description |
|--------|-----------|-------------|
| **Sage 100** | `.txt` | Fichier texte tabulé (tabulation) |
| **Sage 100** | `.csv` | CSV avec délimiteur `\|` |
| **Sage i7** | `.txt` | Format ASCII délimité par `;` |
| **CSV Simple** | `.csv` | Export simple des transactions |

---

## Installation

### Prérequis

- Python 3.8+
- pip (gestionnaire de packages Python)

### Étapes

```bash
# 1. Cloner ou télécharger le projet
cd bank-statement-processor

# 2. Créer un environnement virtuel (recommandé)
python -m venv venv

# 3. Activer l'environnement virtuel
# Sur Windows :
venv\Scripts\activate
# Sur macOS/Linux :
source venv/bin/activate

# 4. Installer les dépendances
pip install -r requirements.txt
```

---

## Utilisation

### Commande de base

```bash
python main.py -i releve_bancaire.pdf -o ./output
```

### Options disponibles

| Option | Description | Défaut |
|--------|-------------|--------|
| `-i, --input` | Chemin du PDF ou répertoire (avec `--batch`) | **Requis** |
| `-o, --output` | Répertoire de sortie | `./output` |
| `-b, --bank` | Banque : `auto`, `attijari`, `cih`, `bp` | `auto` |
| `-f, --format` | Format : `sage100_txt`, `sage100_csv`, `sage_i7`, `simple_csv` | `sage100_txt` |
| `--journal` | Code journal comptable | `BNK` |
| `--compte-bancaire` | N° compte bancaire (plan comptable) | `514100` |
| `--compte-fournisseur` | N° compte fournisseurs | `441100` |
| `--compte-client` | N° compte clients | `342100` |
| `--compte-charges` | N° compte frais bancaires | `613400` |
| `--batch` | Mode traitement par lot | `False` |

### Exemples

#### 1. Détection automatique + export Sage 100

```bash
python main.py -i releve_attijari.pdf -o ./output
```

#### 2. Spécifier la banque et le format

```bash
python main.py -i releve_cih.pdf -b cih -f sage100_txt -o ./output
```

#### 3. Traitement par lot (plusieurs PDF)

```bash
python main.py -i ./dossier_releves/ --batch -b auto -f sage100_txt -o ./output
```

#### 4. Paramètres comptables personnalisés

```bash
python main.py -i releve_bp.pdf -b bp -f sage100_csv \
    --journal BNK --compte-bancaire 514100 \
    --compte-fournisseur 441100 --compte-client 342100 \
    -o ./output
```

#### 5. Export simple CSV (pour vérification)

```bash
python main.py -i releve.pdf -f simple_csv -o ./output
```

---

## Structure des Fichiers Générés

### Pour chaque relevé traité, le programme génère :

1. **Fichier d'import Sage** (selon le format choisi)
   - Contient les écritures comptables prêtes à importer
   - Double écriture (débit/crédit) pour chaque transaction

2. **Rapport de traitement** (`*_RAPPORT.txt`)
   - Résumé du relevé (banque, période, soldes)
   - Statistiques des transactions
   - Liste détaillée des opérations

### Exemple de structure générée :

```
output/
├── Attijariwafa_Bank_1234567890_SAGE100.txt    ← Import Sage
├── Attijariwafa_Bank_1234567890_RAPPORT.txt    ← Résumé
├── CIH_Bank_9876543210_SAGE100.txt
├── CIH_Bank_9876543210_RAPPORT.txt
└── ...
```

---

## Format des Écritures Comptables

### Principe de double écriture

Pour chaque transaction bancaire, le programme génère **2 lignes** d'écriture comptable :

| Transaction | Ligne 1 (Débit) | Ligne 2 (Crédit) |
|-------------|-----------------|------------------|
| **Décaissement** | Compte de charge (613400) | Compte bancaire (514100) |
| **Encaissement** | Compte bancaire (514100) | Compte client (342100) |

### Exemple concret

Pour un virement reçu de **5 000,00 DH** :

```
BNK | 514100 | | 15/01/2024 | 5000.00 | 0.00 | | VIREMENT RECU - CR | | 0001 |
BNK | 342100 | | 15/01/2024 | 0.00 | 5000.00 | | VIREMENT RECU - CR | | 0001 |
```

Pour un retrait de **200,00 DH** :

```
BNK | 613400 | | 10/01/2024 | 200.00 | 0.00 | | RETRAIT GAB - DB | | 0002 |
BNK | 514100 | | 10/01/2024 | 0.00 | 200.00 | | RETRAIT GAB - DB | | 0002 |
```

---

## Import dans Sage

### Sage 100

1. **Créer un format d'import** (une seule fois) :
   - Menu : `Fichier > Format import/export paramétrable`
   - Cliquer sur `Nouveau`
   - Type : `Écritures comptables`
   - Délimiteur : `Tabulation` (pour .txt) ou `Autre` → `|` (pour .csv)
   - Format date : `jj/mm/aaaa`
   - Nombre de décimales : `2`

2. **Importer le fichier** :
   - Menu : `Fichier > Importer > Format paramétrable`
   - Sélectionner votre format d'import
   - Choisir le fichier `.txt` ou `.csv` généré

### Sage i7

1. **Préparer le fichier** :
   - Le fichier généré est au format `journal;date;compte;libellé;débit;crédit`

2. **Importer** :
   - Menu : `Utilitaires > Import de données`
   - Sélectionner le fichier `.txt` généré

---

## Plan Comptable Marocain Standard

Les numéros de compte par défaut suivent le **plan comptable marocain** :

| Compte | Libellé |
|--------|---------|
| **5141** | Banques |
| **3421** | Clients |
| **4411** | Fournisseurs |
| **6134** | Frais bancaires |
| **6142** | Transport du courrier |

Vous pouvez modifier ces comptes avec les options `--compte-*`.

---

## Utilisation en tant que Module Python

```python
from extractor import extract_statement
from sage_converter import convert_statement

# Extraire les transactions
extractor = extract_statement("releve.pdf", bank="auto")

# Voir les transactions
df = extractor.to_dataframe()
print(df)

# Convertir vers Sage
files = convert_statement(
    extractor,
    output_dir="./output",
    output_format="sage100_txt",
    journal_code="BNK",
    compte_bancaire="514100"
)

print(files)
```

---

## Dépannage

### Erreur : "Banque non détectée"
- Spécifiez manuellement la banque avec `-b attijari`, `-b cih`, ou `-b bp`

### Caractères accentués incorrects dans Sage
- Vérifiez que l'encodage est bien `Windows-1252` (défaut pour Sage 100)
- Pour l'import, utilisez le format `.txt` plutôt que `.csv`

### Transactions manquantes
- Certains relevés PDF scannés (images) nécessitent un OCR préalable
- Vérifiez que le PDF contient bien du texte sélectionnable

---

## Sécurité et Confidentialité

⚠️ **Avertissement important** :
- Les relevés bancaires contiennent des **données sensibles**
- Ne partagez jamais les fichiers générés sur des canaux non sécurisés
- Respectez les lois marocaines sur la protection des données (LOI 09-08)
- Stockez les fichiers de sortie dans un répertoire sécurisé

---

## Développement Futur

- [ ] Support de la **BMCE Bank**
- [ ] Support de la **SGMB** (Société Générale Maroc)
- [ ] Interface graphique (GUI)
- [ ] Support des relevés scannés (OCR)
- [ ] Catégorisation automatique des transactions
- [ ] Génération de rapprochement bancaire

---

## Licence

Ce projet est distribué sous licence MIT. Utilisation à vos propres risques.

---

## Auteur

Développé pour faciliter le travail des cabinets comptables et des comptables marocains.

Pour toute question ou suggestion, n'hésitez pas à ouvrir une issue.

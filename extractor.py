"""
Module d'extraction des transactions à partir des relevés bancaires marocains (PDF).
Supporte : Attijariwafa Bank, CIH Bank, Banque Populaire.
Version production — corrections complètes.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import warnings
warnings.filterwarnings("ignore")

import pdfplumber
import pandas as pd


# ── Constantes ────────────────────────────────────────────────────────────────

CURRENT_YEAR = datetime.now().year

# Mots-clés pour classification crédit/débit
CREDIT_KEYWORDS = [
    "RECU", "VIREMENT RECU", "VIRT RECU", "VIR SEPA RECU",
    "VERSEMENT ESPECE", "VERSEMENT ESPECES", "REMISE CHEQUE",
    "REMISE ESP", "ENCAISSEMENT", "INTERETS CREDITEURS",
    "INTERETS CREDIT", "CREDIT", "REMISE",
]
DEBIT_KEYWORDS = [
    "EMIS", "VIREMENT EMIS", "VIRT EMIS", "VIR.EMIS",
    "PAIEMENT", "PRELEVEMENT", "RETRAIT", "ARRETE",
    "FRAIS", "COMMISSION", "LOYER", "TVA", "CNSS", "AMO",
    "SALAIRE", "TAXE", "OPERATION AU DEBIT",
]

# Catégorisation pour plan comptable marocain
CATEGORIES = {
    "salaires":              {"keywords": ["SALAIRE", "PAIE", "SAL-"], "compte": "6171"},
    "cotisations_sociales":  {"keywords": ["CNSS", "AMO", "COTISATION"], "compte": "6174"},
    "impots_taxes":          {"keywords": ["TVA", "DGI", "IMPOT", "FISC"], "compte": "4456"},
    "loyers":                {"keywords": ["LOYER", "LOCATION"], "compte": "6131"},
    "frais_bancaires":       {"keywords": ["COMMISSION", "FRAIS", "TENUE", "ARRETE", "RETRAIT GAB"], "compte": "6347"},
    "encaissement_client":   {"keywords": CREDIT_KEYWORDS, "compte": "3421"},
    "paiement_fournisseur":  {"keywords": ["FOURNISSEUR", "FACTURE"], "compte": "4411"},
}


# ── Classe Transaction ────────────────────────────────────────────────────────

class Transaction:
    """Représente une transaction bancaire."""

    def __init__(self, date: str, date_valeur: str = "", description: str = "",
                 reference: str = "", debit: float = 0.0, credit: float = 0.0,
                 balance: float = 0.0, reference_facture: str = "", categorie: str = ""):
        self.date = date
        self.date_valeur = date_valeur
        self.description = description
        self.reference = reference
        self.debit = debit
        self.credit = credit
        self.balance = balance
        self.reference_facture = reference_facture
        self.categorie = categorie
        self.compte_comptable = self._determine_compte()

    def _determine_compte(self) -> str:
        """Détermine le compte PCM selon le libellé."""
        up = (self.description + " " + self.reference).upper()
        for cat, cfg in CATEGORIES.items():
            if any(k in up for k in cfg["keywords"]):
                self.categorie = cat
                return cfg["compte"]
        return "3421" if self.credit > 0 else "6141"

    def to_dict(self) -> Dict:
        return {
            "date": self.date,
            "date_valeur": self.date_valeur,
            "description": self.description,
            "reference": self.reference,
            "debit": self.debit,
            "credit": self.credit,
            "balance": self.balance,
            "reference_facture": self.reference_facture,
            "categorie": self.categorie,
            "compte_comptable": self.compte_comptable,
        }

    @property
    def montant(self) -> float:
        return self.credit - self.debit


# ── Utilitaires ───────────────────────────────────────────────────────────────

def parse_date(value: str, year: int = CURRENT_YEAR) -> str:
    """
    Parse toute forme de date marocaine vers DD/MM/YYYY.
    Gère : DD/MM/YYYY, DD/MM/YY, DD/MM, DD MM YYYY, DD MM, "01/020 1/02" (CIH malformé)
    """
    if not value:
        return ""
    value = str(value).strip()

    # Format complet DD/MM/YYYY
    m = re.search(r'(\d{2})[/\-](\d{2})[/\-](\d{4})', value)
    if m:
        return f"{m.group(1)}/{m.group(2)}/{m.group(3)}"

    # Format DD/MM/YY
    m = re.search(r'(\d{2})[/\-](\d{2})[/\-](\d{2})\b', value)
    if m:
        return f"{m.group(1)}/{m.group(2)}/20{m.group(3)}"

    # Format court DD/MM (CIH) — avec éventuels chiffres parasites
    m = re.search(r'^(\d{2})/(\d{2})', value)
    if m:
        return f"{m.group(1)}/{m.group(2)}/{year}"

    # Format BP : DD MM YYYY
    m = re.search(r'^(\d{2})\s+(\d{2})\s+(\d{4})', value)
    if m:
        return f"{m.group(1)}/{m.group(2)}/{m.group(3)}"

    # Format court DD MM (sans année)
    m = re.search(r'^(\d{2})\s+(\d{2})\s*$', value)
    if m:
        return f"{m.group(1)}/{m.group(2)}/{year}"

    return ""


def parse_amount(value: str) -> float:
    """
    Parse un montant MAD robuste.
    Gère : "10 800,00", "10800,00", "10800.00", "1 300,00", montants découpés.
    """
    if not value:
        return 0.0
    value = str(value).strip()

    # PRIORITÉ 1 : montant avec séparateur espace "1 300,00", "10 800,00"
    m = re.search(r'\b(\d{1,3}(?:\s\d{3})+),(\d{2})\b', value)
    if m:
        return float(m.group(1).replace(" ", "") + "." + m.group(2))

    # PRIORITÉ 2 : montant simple "10800,00" ou "10800.00" (2-7 chiffres)
    m = re.search(r'(?<![,\d])(\d{2,7})[,\.](\d{2})(?!\d)', value)
    if m:
        return float(m.group(1) + "." + m.group(2))

    return 0.0


def detect_type(description: str) -> str:
    """Détecte si la transaction est un crédit ou débit."""
    up = description.upper()
    for k in CREDIT_KEYWORDS:
        if k in up:
            return "credit"
    for k in DEBIT_KEYWORDS:
        if k in up:
            return "debit"
    return "debit"  # défaut conservateur


def extract_facture_ref(text: str) -> str:
    """Extrait un numéro de facture du libellé."""
    patterns = [
        r'FAC[-\s]?\d{4}[-\s]?\d{3,6}',
        r'F\d{4}[-\s]?\d{3,6}',
        r'INV[-\s]?\d{4,10}',
        r'FACT[-\s]?\d{4,10}',
    ]
    for pat in patterns:
        m = re.search(pat, text.upper())
        if m:
            return m.group(0)
    return ""


def is_excluded_line(line: str) -> bool:
    """Vérifie si la ligne est un en-tête ou pied de page à ignorer."""
    EXCL = [
        'solde depart', 'solde reporte', 'ancien solde',
        'nouveau solde', 'total des mouvements', 'total mouvements',
        'sauf erreur', 'releve de compte', "releve d'identite",
        'banque ville', 'devise :', 'nous avons l\'honneur',
        'votre conseiller', 'agence :', 'n° tel', 'n° tél',
        'operation-reference', 'oper valeur', 'date op', 'date val',
        'mediateur', 'centre relation', 'www.', 'sa au capital',
        'rc:', 'cnss:', ' if:', 'patente:', 'ice:', 'tel. :',
        'banque populaire', 'attijariwafa bank', 'bmce', 'bmci',
        'page n°', 'page n', 'credit immobilier',
        'titulaire :', 'n° compte :', 'agence :', 'periode :',
        'code journal', 'libelle', 'debit credit', 'montant debit',
        'date operation', 'date valeur', 'reference',
    ]
    low = line.lower().strip()
    if not low:
        return True
    # Lignes arabes pures
    if re.match(r'^[\u0600-\u06FF\s,\.]+$', line):
        return True
    return any(e in low for e in EXCL)


# ── Classe de base ────────────────────────────────────────────────────────────

class BankStatementExtractor:
    """Classe de base pour les extracteurs de relevés bancaires."""

    def __init__(self, pdf_path: str):
        self.pdf_path = Path(pdf_path)
        self.bank_name = ""
        self.account_number = ""
        self.account_holder = ""
        self.currency = "MAD"
        self.period_start = ""
        self.period_end = ""
        self.opening_balance = 0.0
        self.closing_balance = 0.0
        self.transactions: List[Transaction] = []

    def extract(self) -> List[Transaction]:
        raise NotImplementedError

    def to_dataframe(self) -> pd.DataFrame:
        if not self.transactions:
            self.extract()
        return pd.DataFrame([t.to_dict() for t in self.transactions])

    def get_summary(self) -> Dict:
        df = self.to_dataframe()
        return {
            "banque": self.bank_name,
            "titulaire": self.account_holder,
            "numero_compte": self.account_number,
            "devise": self.currency,
            "periode_debut": self.period_start,
            "periode_fin": self.period_end,
            "solde_ouverture": self.opening_balance,
            "solde_cloture": self.closing_balance,
            "total_debit": float(df["debit"].sum()) if not df.empty else 0.0,
            "total_credit": float(df["credit"].sum()) if not df.empty else 0.0,
            "nombre_transactions": len(self.transactions),
        }

    def _extract_full_text(self) -> str:
        """Extrait tout le texte du PDF page par page."""
        full_text = ""
        with pdfplumber.open(self.pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                full_text += text + "\n"
        return full_text

    def _is_scanned_pdf(self) -> bool:
        """Vérifie si le PDF est une image scannée (pas de texte extractible)."""
        with pdfplumber.open(self.pdf_path) as pdf:
            total_chars = sum(len(page.chars) for page in pdf.pages)
        return total_chars < 50

    def _try_ocr(self, page) -> str:
        """Tente l'OCR sur une page via pytesseract (si installé)."""
        try:
            import pytesseract
            from PIL import Image
            import io
            img = page.to_image(resolution=300).original
            return pytesseract.image_to_string(img, lang="fra")
        except ImportError:
            return ""
        except Exception:
            return ""

    def _try_ocr_full(self) -> str:
        """OCR complet sur toutes les pages."""
        try:
            import pytesseract
            with pdfplumber.open(self.pdf_path) as pdf:
                texts = []
                for page in pdf.pages:
                    texts.append(self._try_ocr(page))
                return "\n".join(texts)
        except Exception:
            return ""

    def _merge_multiline(self, lines: List[str], date_pattern) -> List[str]:
        """
        Fusionne les lignes orphelines (libellés sur plusieurs lignes).
        Une ligne orpheline = pas de date en début → se colle à la précédente.
        """
        merged = []
        for line in lines:
            if is_excluded_line(line):
                continue
            # Lignes arabes
            if re.match(r'^[\u0600-\u06FF\s,\.]+$', line):
                continue
            if date_pattern.match(line):
                merged.append(line)
            elif merged:
                # Chiffre isolé ou ",xx" = suite d'un montant découpé → coller sans espace
                if re.match(r'^[\d]+$', line.strip()) or re.match(r'^,\d+', line.strip()):
                    merged[-1] += line.strip()
                else:
                    merged[-1] += " " + line
        return merged

    def _parse_transaction_line(self, line: str, date_fmt: str = "cih") -> Optional[Transaction]:
        """Parse une ligne fusionnée et retourne une Transaction ou None."""
        # Réparer les montants découpés "10800,0 0" → "10800,00"
        line = re.sub(r'(\d+,\d)\s+(\d)\b', r'\1\2', line)

        # Extraire montant
        amount = parse_amount(line)
        if amount <= 0 or amount >= 100_000_000:
            return None

        # Extraire date et libellé selon le format
        date = ""
        libelle = line

        if date_fmt == "bp":
            m = re.match(r'^(\d{2})\s+(\d{2})\s+(\d{4})', line)
            if m:
                date = f"{m.group(1)}/{m.group(2)}/{m.group(3)}"
                libelle = re.sub(r'^\d{2}\s+\d{2}\s+\d{4}\s+\d{2}\s+\d{2}\s+\d{4}\s+', '', libelle)
                libelle = re.sub(r'^[A-Z0-9]{4,10}\s+', '', libelle)

        elif date_fmt == "attijari":
            m = re.match(r'^[0-9A-Z]{5,7}\s+(\d{2})\s+(\d{2})\s+', line)
            if m:
                date = f"{m.group(1)}/{m.group(2)}/{CURRENT_YEAR}"
                libelle = re.sub(r'^[0-9A-Z]{5,7}\s+\d{2}\s+\d{2}\s+', '', libelle)

        else:  # CIH — 3 formats possibles
            # Format 1 : DD/MM/YYYY DD/MM/YYYY (double date complète — PDF test)
            m = re.match(r'^(\d{2})[/\-](\d{2})[/\-](\d{4})\s+\d{2}[/\-]\d{2}[/\-]\d{4}\s+', line)
            if m:
                date = f"{m.group(1)}/{m.group(2)}/{m.group(3)}"
                libelle = re.sub(r'^\d{2}[/\-]\d{2}[/\-]\d{4}\s+\d{2}[/\-]\d{2}[/\-]\d{4}\s+', '', libelle)
            else:
                # Format 2 : DD/MM chiffres parasites (vrai CIH)
                m = re.match(r'^(\d{2})[/\-](\d{2})\d?\s+\d?\s*\d{0,2}[/\-]\d{2}', line)
                if m:
                    date = f"{m.group(1)}/{m.group(2)}/{CURRENT_YEAR}"
                    libelle = re.sub(r'^\d{2}[/\-]\d{2}\d?\s+\d?\s*\d{0,2}[/\-]\d{2}\s+', '', libelle)
                else:
                    # Format 3 : DD/MM/YYYY simple
                    m = re.match(r'^(\d{2})[/\-](\d{2})[/\-](\d{4})\s+', line)
                    if m:
                        date = f"{m.group(1)}/{m.group(2)}/{m.group(3)}"
                        libelle = re.sub(r'^\d{2}[/\-]\d{2}[/\-]\d{4}\s+', '', libelle)

        if not date:
            return None

        # Supprimer les montants du libellé
        libelle = re.sub(r'\b\d{1,3}(?:\s\d{3})+,\d{2}\b', '', libelle)
        libelle = re.sub(r'(?<![,\d])\d{2,7}[,\.]\d{2}(?!\d)', '', libelle)
        libelle = re.sub(r'\s{2,}', ' ', libelle).strip()

        # Extraire référence interne si présente
        ref_match = re.search(r'\b([A-Z]{2,8}-?\d{3,10})\b', line)
        reference = ref_match.group(1) if ref_match else ""

        # Détecter type et référence facture
        typ = detect_type(line)
        ref_facture = extract_facture_ref(line)

        debit = amount if typ == "debit" else 0.0
        credit = amount if typ == "credit" else 0.0

        tx = Transaction(
            date=date,
            description=libelle[:100],
            reference=reference,
            debit=debit,
            credit=credit,
            reference_facture=ref_facture,
        )
        return tx


# ── CIH Bank ──────────────────────────────────────────────────────────────────

class CIHExtractor(BankStatementExtractor):
    """Extracteur pour les relevés CIH Bank."""

    # Pattern date CIH : "01/02", "01/020 1/02" (malformé), ou "01/01/2024 01/01/2024"
    DATE_PATTERN = re.compile(r'^(\d{2})[/\-](\d{2})')

    def extract(self) -> List[Transaction]:
        self.bank_name = "CIH Bank"
        self.transactions = []

        is_scanned = self._is_scanned_pdf()
        if is_scanned:
            text = self._try_ocr_full()
            if not text:
                print("⚠️  PDF CIH scanné sans OCR disponible. Installez pytesseract+poppler.")
                return self.transactions
        else:
            text = self._extract_full_text()
        self._extract_account_info(text)

        lines = [l.strip() for l in text.split('\n') if l.strip()]
        merged = self._merge_multiline(lines, self.DATE_PATTERN)

        for line in merged:
            tx = self._parse_transaction_line(line, date_fmt="cih")
            if tx:
                self.transactions.append(tx)

        return self.transactions

    def _extract_account_info(self, text: str):
        # Numéro de compte
        m = re.search(r'N°\s*COMPTE\s*:?\s*([\d\s]+)', text, re.IGNORECASE)
        if m:
            self.account_number = m.group(1).strip().replace(" ", "")

        # Titulaire
        m = re.search(r'TITULAIRE\s*:?\s*(.+)', text, re.IGNORECASE)
        if m:
            self.account_holder = m.group(1).strip()[:50]

        # Période
        m = re.search(r'PERIODE\s*:?\s*(\d{2}/\d{2}/\d{4})\s*(?:AU|A)\s*(\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
        if m:
            self.period_start = m.group(1)
            self.period_end = m.group(2)

        # Solde départ
        m = re.search(r'SOLDE\s+DEPART\s+AU\s*:?\s*[\d/]+\s*:?\s*([\d\s,\.]+)', text, re.IGNORECASE)
        if m:
            self.opening_balance = parse_amount(m.group(1))

        # Solde final
        m = re.search(r'NOUVEAU\s+SOLDE\s+AU\s*[\d/]+\s*:?\s*([\d\s,\.]+)', text, re.IGNORECASE)
        if m:
            self.closing_balance = parse_amount(m.group(1))

        # Devise
        m = re.search(r'DEVISE\s*:?\s*([\w\s]+)', text, re.IGNORECASE)
        if m:
            self.currency = m.group(1).strip()[:20]


# ── Attijariwafa Bank ─────────────────────────────────────────────────────────

class AttijariwafaExtractor(BankStatementExtractor):
    """
    Extracteur pour les relevés Attijariwafa Bank.
    Format : CODE(5-7 alphanum) DATE(DD MM) LIBELLE VALEUR MONTANT
    Colonnes DEBIT et CAPITAUX séparées.
    """

    # Pattern : code alphanum + date DD MM
    DATE_PATTERN = re.compile(r'^([0-9A-Z]{5,7})\s+(\d{2}\s+\d{2})\s+')

    def extract(self) -> List[Transaction]:
        self.bank_name = "Attijariwafa Bank"
        self.transactions = []

        is_scanned = self._is_scanned_pdf()

        text = self._extract_full_text()
        self._extract_account_info(text)

        # Attijariwafa a des colonnes DEBIT et CAPITAUX distinctes
        # On utilise l'extraction par tableau si possible, sinon texte
        with pdfplumber.open(self.pdf_path) as pdf:
            for page in pdf.pages:
                # Tenter OCR natif si PDF scanné
                if is_scanned:
                    page_text = self._try_ocr(page)
                else:
                    # Essayer d'abord les tableaux (colonnes DEBIT/CAPITAUX séparées)
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            self._process_attijari_table(table)
                        if self.transactions:
                            continue
                    page_text = page.extract_text() or ""

                if page_text:
                    lines = [l.strip() for l in page_text.split('\n') if l.strip()]
                    merged = self._merge_multiline(lines, self.DATE_PATTERN)
                    for line in merged:
                        tx = self._parse_attijari_line(line)
                        if tx:
                            self.transactions.append(tx)

        if is_scanned and not self.transactions:
            print("⚠️  PDF scanné sans OCR disponible. Installez pytesseract+poppler pour les PDFs image.")

        return self.transactions

    def _process_attijari_table(self, table: list):
        """
        Traite un tableau Attijariwafa avec colonnes distinctes.
        Colonnes attendues : CODE | DATE | LIBELLE | VALEUR | DEBIT | CAPITAUX(CREDIT)
        """
        for row in table:
            if not row or len(row) < 4:
                continue
            try:
                values = [str(v).strip() if v else "" for v in row]

                # Chercher la date (colonne 1 = date courte "02 02")
                date = parse_date(values[1]) if len(values) > 1 else ""
                if not date:
                    continue

                description = values[2] if len(values) > 2 else ""
                if is_excluded_line(description):
                    continue

                # Colonnes débit et crédit séparées (indices 4 et 5)
                debit = parse_amount(values[4]) if len(values) > 4 else 0.0
                credit = parse_amount(values[5]) if len(values) > 5 else 0.0

                # Si les deux sont à 0, essayer de détecter via le libellé
                if debit == 0.0 and credit == 0.0:
                    # Chercher un montant dans la ligne et classifier par mots-clés
                    all_text = " ".join(values)
                    amount = parse_amount(all_text)
                    if amount > 0:
                        if detect_type(description) == "credit":
                            credit = amount
                        else:
                            debit = amount

                if debit == 0.0 and credit == 0.0:
                    continue

                ref_valeur = values[3] if len(values) > 3 else ""
                ref_facture = extract_facture_ref(description)

                tx = Transaction(
                    date=date,
                    date_valeur=parse_date(ref_valeur),
                    description=description[:100],
                    debit=debit,
                    credit=credit,
                    reference_facture=ref_facture,
                )
                self.transactions.append(tx)
            except Exception:
                continue

    def _parse_attijari_line(self, line: str) -> Optional[Transaction]:
        """Parse une ligne texte Attijariwafa (fallback si pas de tableau)."""
        m = self.DATE_PATTERN.match(line)
        if not m:
            return None

        # Extraire date depuis le groupe 2 "DD MM"
        date_str = m.group(2).strip()
        date_parts = date_str.split()
        date = f"{date_parts[0]}/{date_parts[1]}/{CURRENT_YEAR}" if len(date_parts) >= 2 else ""
        if not date:
            return None

        # Réparer montants découpés
        line = re.sub(r'(\d+,\d)\s+(\d)\b', r'\1\2', line)

        # Chercher dernier montant
        amount = parse_amount(line)
        if amount <= 0:
            return None

        # Libellé
        libelle = re.sub(r'^[0-9A-Z]{5,7}\s+\d{2}\s+\d{2}\s+', '', line)
        libelle = re.sub(r'\b\d{1,3}(?:\s\d{3})+,\d{2}\b', '', libelle)
        libelle = re.sub(r'(?<![,\d])\d{2,7}[,\.]\d{2}(?!\d)', '', libelle)
        libelle = re.sub(r'\d{2}\s+\d{2}\s+\d{4}\s*$', '', libelle)
        libelle = re.sub(r'\s{2,}', ' ', libelle).strip()

        typ = detect_type(line)
        ref_facture = extract_facture_ref(line)

        return Transaction(
            date=date,
            description=libelle[:100],
            debit=amount if typ == "debit" else 0.0,
            credit=amount if typ == "credit" else 0.0,
            reference_facture=ref_facture,
        )

    def _extract_account_info(self, text: str):
        # Numéro de compte (format Attijari : "00 0176N000001280 21110")
        m = re.search(r'COMPTE\s*:?\s*([\dA-Z\s]{10,25})', text, re.IGNORECASE)
        if m:
            self.account_number = m.group(1).strip()[:25]

        # RIB
        m = re.search(r'(\d{3}\s+\d{3}\s+\d{10,20}\s+\d{2})', text)
        if m:
            self.account_number = m.group(1).strip()

        # Titulaire
        m = re.search(r'(?:HM|STE|SOCIETE|SA|SARL|SNC)\s+([A-Z\s\.]+)', text)
        if m:
            self.account_holder = m.group(0).strip()[:50]

        # Soldes
        m = re.search(r'SOLDE\s+DEPART\s+AU\s+[\d/\s]+\s+([\d\s,\.]+)\s+CREDITEUR', text, re.IGNORECASE)
        if m:
            self.opening_balance = parse_amount(m.group(1))

        m = re.search(r'SOLDE\s+FINAL\s+AU\s+[\d/\s]+\s+([\d\s,\.]+)', text, re.IGNORECASE)
        if m:
            self.closing_balance = parse_amount(m.group(1))

        # Période
        m = re.search(r'(\d{2}\s+\d{2}\s+\d{4})', text)
        if m:
            d = m.group(1).split()
            self.period_start = f"{d[0]}/{d[1]}/{d[2]}"

        self.currency = "MAD"


# ── Banque Populaire ──────────────────────────────────────────────────────────

class BanquePopulaireExtractor(BankStatementExtractor):
    """
    Extracteur pour les relevés Banque Populaire.
    Format : DATE_OP(DD MM YYYY) DATE_VAL(DD MM YYYY) REF LIBELLE DEBIT/CREDIT
    """

    # Pattern BP : DD MM YYYY au début
    DATE_PATTERN = re.compile(r'^(\d{2})\s+(\d{2})\s+(\d{4})\s+')

    def extract(self) -> List[Transaction]:
        self.bank_name = "Banque Populaire"
        self.transactions = []

        is_scanned = self._is_scanned_pdf()
        if is_scanned:
            text = self._try_ocr_full()
            if not text:
                print("⚠️  PDF BP scanné sans OCR disponible. Installez pytesseract+poppler.")
                return self.transactions
        else:
            text = self._extract_full_text()
        self._extract_account_info(text)

        lines = [l.strip() for l in text.split('\n') if l.strip()]
        merged = self._merge_multiline(lines, self.DATE_PATTERN)

        for line in merged:
            tx = self._parse_bp_line(line)
            if tx:
                self.transactions.append(tx)

        return self.transactions

    def _parse_bp_line(self, line: str) -> Optional[Transaction]:
        """Parse une ligne BP."""
        m = self.DATE_PATTERN.match(line)
        if not m:
            return None

        date = f"{m.group(1)}/{m.group(2)}/{m.group(3)}"

        # Réparer montants découpés
        line = re.sub(r'(\d+,\d)\s+(\d)\b', r'\1\2', line)

        # Montant = dernier de la ligne (priorité espace > simple)
        amount = parse_amount(line)
        if amount <= 0:
            return None

        # Libellé : supprimer les 2 dates + code référence
        libelle = re.sub(r'^\d{2}\s+\d{2}\s+\d{4}\s+\d{2}\s+\d{2}\s+\d{4}\s+', '', line)
        libelle = re.sub(r'^[A-Z0-9]{4,10}\s+', '', libelle)  # code ref BP (ex: "858597")
        libelle = re.sub(r'\b\d{1,3}(?:\s\d{3})+,\d{2}\b', '', libelle)
        libelle = re.sub(r'(?<![,\d])\d{2,7}[,\.]\d{2}(?!\d)', '', libelle)
        libelle = re.sub(r'\s{2,}', ' ', libelle).strip()

        # Date valeur (2ème date dans la ligne)
        m2 = re.search(r'^\d{2}\s+\d{2}\s+\d{4}\s+(\d{2})\s+(\d{2})\s+(\d{4})', line)
        date_val = f"{m2.group(1)}/{m2.group(2)}/{m2.group(3)}" if m2 else ""

        typ = detect_type(line)
        ref_facture = extract_facture_ref(line)

        return Transaction(
            date=date,
            date_valeur=date_val,
            description=libelle[:100],
            debit=amount if typ == "debit" else 0.0,
            credit=amount if typ == "credit" else 0.0,
            reference_facture=ref_facture,
        )

    def _extract_account_info(self, text: str):
        # Numéro de compte BP format "190 780 0001234567890 12"
        m = re.search(r'(\d{3})\s+(\d{3})\s+([\d\s]+)\s+(\d{2})', text)
        if m:
            self.account_number = f"{m.group(1)} {m.group(2)} {m.group(3).strip()} {m.group(4)}"

        # Agence
        m = re.search(r'Agence\s*:?\s*(.+)', text, re.IGNORECASE)
        if m:
            self.account_holder = m.group(1).strip()[:50]

        # Solde départ
        m = re.search(r'SOLDE\s+DEPART\s+AU\s*:?\s*[\d/]+\s+([\d\s,\.]+)', text, re.IGNORECASE)
        if m:
            self.opening_balance = parse_amount(m.group(1))

        # Solde final
        m = re.search(r'SOLDE\s+A\s+REPORTER\s*:?\s*([\d\s,\.]+)', text, re.IGNORECASE)
        if m:
            self.closing_balance = parse_amount(m.group(1))

        # Période
        m = re.search(r'AU\s+(\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
        if m:
            self.period_end = m.group(1)

        self.currency = "MAD"


# ── Détection automatique ─────────────────────────────────────────────────────

def detect_bank(pdf_path: str) -> str:
    """Détecte automatiquement la banque. Retourne 'attijari', 'cih', 'bp', ou 'unknown'."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for page in pdf.pages[:2]:
                text += (page.extract_text() or "") + "\n"

        text_lower = text.lower()

        if any(k in text_lower for k in ["attijariwafa", "attijari", "wafa bank", "التجاري وفا"]):
            return "attijari"
        elif any(k in text_lower for k in ["cih bank", "crédit immobilier", "credit immobilier", "cih"]):
            return "cih"
        elif any(k in text_lower for k in ["banque populaire", "bcp", "البنك الشعبي"]):
            return "bp"
        elif any(k in text_lower for k in ["bmce", "bank of africa"]):
            return "bmce"
        elif any(k in text_lower for k in ["bmci", "bnp"]):
            return "bmci"
        elif any(k in text_lower for k in ["societe generale", "sgmb"]):
            return "sgmb"
        else:
            return "unknown"

    except Exception as e:
        print(f"Erreur détection banque : {e}")
        return "unknown"


def extract_statement(pdf_path: str, bank: str = "auto") -> BankStatementExtractor:
    """
    Fonction principale d'extraction.
    bank : 'attijari', 'cih', 'bp', ou 'auto'
    """
    if bank == "auto":
        bank = detect_bank(pdf_path)

    extractors = {
        "attijari": AttijariwafaExtractor,
        "cih":      CIHExtractor,
        "bp":       BanquePopulaireExtractor,
    }

    if bank not in extractors:
        # Fallback CIH générique pour banques inconnues (format le plus commun)
        print(f"⚠️  Banque '{bank}' non reconnue, utilisation du parser générique CIH")
        extractor = CIHExtractor(pdf_path)
    else:
        extractor = extractors[bank](pdf_path)

    extractor.extract()
    return extractor

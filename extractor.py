"""
Module d'extraction des transactions à partir des relevés bancaires marocains (PDF).
Supporte : Attijariwafa Bank, CIH Bank, Banque Populaire.
"""

import re
import subprocess
import warnings
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

import pdfplumber
import pandas as pd

warnings.filterwarnings("ignore")


class Transaction:
    """Représente une transaction bancaire."""

    def __init__(self, date: str, date_valeur: str = "", description: str = "",
                 reference: str = "", debit: float = 0.0, credit: float = 0.0,
                 balance: float = 0.0):
        self.date = date
        self.date_valeur = date_valeur
        self.description = description
        self.reference = reference
        self.debit = debit
        self.credit = credit
        self.balance = balance

    def to_dict(self) -> Dict:
        return {
            "date": self.date,
            "date_valeur": self.date_valeur,
            "description": self.description,
            "reference": self.reference,
            "debit": self.debit,
            "credit": self.credit,
            "balance": self.balance
        }

    @property
    def montant(self) -> float:
        return self.credit - self.debit


class BankStatementExtractor:
    """Classe de base pour les extracteurs de relevés bancaires."""

    def __init__(self, pdf_path: str):
        self.pdf_path = Path(pdf_path)
        self.bank_name = ""
        self.account_number = ""
        self.account_holder = ""
        self.currency = ""
        self.period_start = ""
        self.period_end = ""
        self.opening_balance = 0.0
        self.closing_balance = 0.0
        self.transactions: List[Transaction] = []

    def extract(self) -> List[Transaction]:
        """Méthode principale d'extraction à surcharger."""
        raise NotImplementedError

    def to_dataframe(self) -> pd.DataFrame:
        """Convertit les transactions en DataFrame pandas."""
        if not self.transactions:
            self.extract()
        data = [t.to_dict() for t in self.transactions]
        return pd.DataFrame(data)

    def get_summary(self) -> Dict:
        """Retourne un résumé du relevé."""
        df = self.to_dataframe()
        total_debit = df["debit"].sum()
        total_credit = df["credit"].sum()
        return {
            "banque": self.bank_name,
            "titulaire": self.account_holder,
            "numero_compte": self.account_number,
            "devise": self.currency,
            "periode_debut": self.period_start,
            "periode_fin": self.period_end,
            "solde_ouverture": self.opening_balance,
            "solde_cloture": self.closing_balance,
            "total_debit": total_debit,
            "total_credit": total_credit,
            "nombre_transactions": len(self.transactions)
        }


class AttijariwafaExtractor(BankStatementExtractor):
    """Extracteur pour les relevés Attijariwafa Bank."""

    def extract(self) -> List[Transaction]:
        """Extrait les transactions d'un relevé Attijariwafa Bank."""
        self.bank_name = "Attijariwafa Bank"
        self.transactions = []

        try:
            # Essayer d'utiliser tabula-py d'abord (comme openbk)
            self._extract_with_tabula()
        except Exception:
            # Fallback sur pdfplumber
            self._extract_with_pdfplumber()

        return self.transactions

    def _extract_with_tabula(self):
        """Extraction via tabula-py (même méthode qu'openbk)."""
        try:
            import tabula
            tables = tabula.read_pdf(
                str(self.pdf_path),
                pages="all",
                multiple_tables=True,
                pandas_options={"header": None}
            )

            for table in tables:
                if table is None or table.empty:
                    continue
                self._process_attijari_table(table)

        except ImportError:
            raise Exception("tabula-py non installé")

    def _extract_with_pdfplumber(self):
        """Extraction via pdfplumber (fallback)."""
        with pdfplumber.open(self.pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if table:
                        df = pd.DataFrame(table[1:], columns=table[0] if table else None)
                        self._process_attijari_table(df)

                # Extraction des infos du compte depuis le texte
                text = page.extract_text() or ""
                self._extract_account_info(text)

    def _process_attijari_table(self, df: pd.DataFrame):
        """Traite un DataFrame de transactions Attijari."""
        for _, row in df.iterrows():
            try:
                values = row.astype(str).tolist()
                if len(values) < 4:
                    continue

                # Détecter les colonnes : date, opération, référence, débit, crédit
                date_match = re.search(r'(\d{2}/\d{2}/\d{4})', values[0])
                if not date_match:
                    continue

                date_str = date_match.group(1)
                description = ""
                reference = ""
                debit = 0.0
                credit = 0.0

                # Rechercher les montants
                for val in values:
                    val = val.replace(" ", "").replace(",", ".")
                    # Débit
                    if re.match(r'^\d+\.?\d*$', val):
                        num = float(val)
                        if num > 0:
                            # Déterminer si c'est un débit ou crédit selon la position
                            if values.index(val) > len(values) // 2:
                                credit = num
                            else:
                                debit = num

                description = " ".join([v for v in values[1:-2] if v and v != "nan"])

                transaction = Transaction(
                    date=date_str,
                    description=description,
                    reference=reference,
                    debit=debit,
                    credit=credit
                )
                self.transactions.append(transaction)

            except Exception:
                continue

    def _extract_account_info(self, text: str):
        """Extrait les informations du compte depuis le texte."""
        # Numéro de compte
        account_match = re.search(r'N°\s*compte\s*:\s*([\d\s]+)', text, re.IGNORECASE)
        if account_match:
            self.account_number = account_match.group(1).strip()

        # Période
        period_match = re.search(r'(?:Du|Period)\s+(\d{2}/\d{2}/\d{4})\s+(?:Au|to)\s+(\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
        if period_match:
            self.period_start = period_match.group(1)
            self.period_end = period_match.group(2)


class CIHExtractor(BankStatementExtractor):
    """Extracteur pour les relevés CIH Bank."""

    def extract(self) -> List[Transaction]:
        """Extrait les transactions d'un relevé CIH Bank."""
        self.bank_name = "CIH Bank"
        self.transactions = []

        with pdfplumber.open(self.pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                tables = page.extract_tables()

                # Extraire les infos du compte
                self._extract_account_info(text)

                # Extraire les transactions des tables
                for table in tables:
                    if table and len(table) > 1:
                        self._process_cih_table(table)

        return self.transactions

    def _process_cih_table(self, table: list):
        """Traite une table de transactions CIH."""
        for row in table[1:]:  # Skip header
            if not row or len(row) < 5:
                continue

            try:
                # Format CIH : Date Op | Date Val | Opération | Référence | Débit | Crédit
                date_op = self._parse_date(row[0])
                date_val = self._parse_date(row[1]) if len(row) > 1 else ""
                description = str(row[2]) if len(row) > 2 else ""
                reference = str(row[3]) if len(row) > 3 else ""

                debit = self._parse_amount(row[4]) if len(row) > 4 else 0.0
                credit = self._parse_amount(row[5]) if len(row) > 5 else 0.0

                if not date_op and not description:
                    continue

                transaction = Transaction(
                    date=date_op,
                    date_valeur=date_val,
                    description=description,
                    reference=reference,
                    debit=debit,
                    credit=credit
                )
                self.transactions.append(transaction)

            except Exception:
                continue

    def _extract_account_info(self, text: str):
        """Extrait les informations du compte depuis le texte."""
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if 'COMPTE' in line.upper() or 'N°' in line:
                # Chercher le numéro de compte sur la ligne suivante
                if i + 1 < len(lines):
                    account_match = re.search(r'(\d{10,})', lines[i + 1])
                    if account_match:
                        self.account_number = account_match.group(1)

            if 'SOLDE' in line.upper() and 'DEPART' in line.upper():
                balance_match = re.search(r'(\d+[\s,]*\d*\.?\d*)', line)
                if balance_match:
                    self.opening_balance = self._parse_amount(balance_match.group(1))

    def _parse_date(self, value) -> str:
        """Parse une date au format DD/MM/YYYY."""
        if not value:
            return ""
        value_str = str(value).strip()
        # Format DD/MM/YYYY
        match = re.search(r'(\d{2}/\d{2}/\d{4})', value_str)
        if match:
            return match.group(1)
        return ""

    def _parse_amount(self, value) -> float:
        """Parse un montant."""
        if not value:
            return 0.0
        value_str = str(value).replace(" ", "").replace(",", ".")
        match = re.search(r'(\d+\.?\d*)', value_str)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return 0.0
        return 0.0


class BanquePopulaireExtractor(BankStatementExtractor):
    """Extracteur pour les relevés Banque Populaire (BCP)."""

    def extract(self) -> List[Transaction]:
        """Extrait les transactions d'un relevé Banque Populaire."""
        self.bank_name = "Banque Populaire"
        self.transactions = []

        with pdfplumber.open(self.pdf_path) as pdf:
            all_text = ""
            for page in pdf.pages:
                text = page.extract_text() or ""
                all_text += text + "\n"
                tables = page.extract_tables()

                # Extraire les infos du compte
                self._extract_account_info(text)

                # Extraire les transactions
                for table in tables:
                    if table and len(table) > 1:
                        self._process_bp_table(table)

            # Si aucune transaction n'a été trouvée via les tables, essayer l'extraction par regex
            if not self.transactions:
                self._extract_by_regex(all_text)

        return self.transactions

    def _process_bp_table(self, table: list):
        """Traite une table de transactions Banque Populaire."""
        for row in table[1:]:
            if not row or len(row) < 4:
                continue

            try:
                # Format BP : DATES | OPERATION | REFERENCE | DEBIT | CREDIT
                date_str = self._parse_date(str(row[0]))
                description = str(row[1]) if len(row) > 1 else ""
                reference = str(row[2]) if len(row) > 2 else ""

                debit = 0.0
                credit = 0.0

                # Les montants sont généralement dans les dernières colonnes
                if len(row) >= 5:
                    debit = self._parse_amount(str(row[3]))
                    credit = self._parse_amount(str(row[4]))
                elif len(row) == 4:
                    # Essayer de déterminer si c'est un débit ou crédit
                    val = str(row[3])
                    if "-" in val or "D" in val:
                        debit = self._parse_amount(val)
                    else:
                        credit = self._parse_amount(val)

                if not date_str and not description.strip():
                    continue

                transaction = Transaction(
                    date=date_str,
                    description=description,
                    reference=reference,
                    debit=debit,
                    credit=credit
                )
                self.transactions.append(transaction)

            except Exception:
                continue

    def _extract_by_regex(self, text: str):
        """Extraction alternative par expressions régulières."""
        # Pattern pour les transactions : date (DD/MM) + description + montant
        lines = text.split('\n')

        for line in lines:
            # Rechercher les lignes commençant par une date
            match = re.match(r'(\d{2}/\d{2})\s+(\d{2}/\d{2})?\s*(.+?)\s+([\d\s,]+\.?\d*)\s*([\d\s,]+\.?\d*)?', line)
            if match:
                try:
                    date_str = match.group(1)
                    # Ajouter l'année si nécessaire
                    if len(date_str.split('/')) == 2:
                        date_str += f"/{datetime.now().year}"

                    description = match.group(3).strip()
                    debit_str = match.group(4) if match.group(4) else "0"
                    credit_str = match.group(5) if match.group(5) else "0"

                    debit = self._parse_amount(debit_str)
                    credit = self._parse_amount(credit_str)

                    transaction = Transaction(
                        date=date_str,
                        description=description,
                        debit=debit,
                        credit=credit
                    )
                    self.transactions.append(transaction)
                except Exception:
                    continue

    def _extract_account_info(self, text: str):
        """Extrait les informations du compte."""
        # Numéro de compte
        account_match = re.search(r'N°\s*DE\s*COMPTE\s*:\s*([\d\s]+)', text, re.IGNORECASE)
        if account_match:
            self.account_number = account_match.group(1).strip().replace(" ", "")

        # Devise
        currency_match = re.search(r'DEVISE\s*:\s*(\w+)', text, re.IGNORECASE)
        if currency_match:
            self.currency = currency_match.group(1)

        # Solde départ
        solde_match = re.search(r'SOLDE\s*DEPART\s*AU\s*[:\s]*(\d{2}/\d{2}/\d{4})\s*:?\s*([\d\s,]+\.?\d*)', text, re.IGNORECASE)
        if solde_match:
            self.period_start = solde_match.group(1)
            self.opening_balance = self._parse_amount(solde_match.group(2))

        # Solde fin
        solde_fin_match = re.search(r'NOUVEAU\s*SOLDE\s*AU\s*[:\s]*(\d{2}/\d{2}/\d{4})\s*:?\s*([\d\s,]+\.?\d*)', text, re.IGNORECASE)
        if solde_fin_match:
            self.period_end = solde_fin_match.group(1)
            self.closing_balance = self._parse_amount(solde_fin_match.group(2))

    def _parse_date(self, value: str) -> str:
        """Parse une date."""
        value = value.strip()
        match = re.search(r'(\d{2}/\d{2}/\d{4})', value)
        if match:
            return match.group(1)
        # Format court DD/MM
        match = re.search(r'(\d{2}/\d{2})', value)
        if match:
            return f"{match.group(1)}/{datetime.now().year}"
        return ""

    def _parse_amount(self, value: str) -> float:
        """Parse un montant."""
        if not value:
            return 0.0
        value = value.replace(" ", "").replace(",", ".")
        numbers = re.findall(r'\d+\.?\d*', value)
        if numbers:
            try:
                return float(numbers[-1])
            except ValueError:
                return 0.0
        return 0.0


def detect_bank(pdf_path: str) -> str:
    """
    Détecte automatiquement la banque à partir du PDF.
    Retourne : 'attijari', 'cih', 'bp', ou 'unknown'
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for page in pdf.pages[:2]:  # Lire les 2 premières pages
                text += (page.extract_text() or "") + "\n"

            text_lower = text.lower()

            if any(keyword in text_lower for keyword in ["attijariwafa", "attijari", "wafa"]):
                return "attijari"
            elif any(keyword in text_lower for keyword in ["cih", "crédit immobilier", "credit immobilier"]):
                return "cih"
            elif any(keyword in text_lower for keyword in ["banque populaire", "bcp", "populaire"]):
                return "bp"
            else:
                return "unknown"

    except Exception as e:
        print(f"Erreur lors de la détection de la banque : {e}")
        return "unknown"


def extract_statement(pdf_path: str, bank: str = "auto") -> BankStatementExtractor:
    """
    Fonction principale d'extraction.

    Args:
        pdf_path : Chemin vers le fichier PDF
        bank : 'attijari', 'cih', 'bp', ou 'auto' pour détection automatique

    Returns:
        Instance de BankStatementExtractor avec les transactions extraites
    """
    if bank == "auto":
        bank = detect_bank(pdf_path)

    if bank == "attijari":
        extractor = AttijariwafaExtractor(pdf_path)
    elif bank == "cih":
        extractor = CIHExtractor(pdf_path)
    elif bank == "bp":
        extractor = BanquePopulaireExtractor(pdf_path)
    else:
        raise ValueError(f"Banque non reconnue : {bank}. Utilisez 'attijari', 'cih', 'bp', ou 'auto'.")

    extractor.extract()
    return extractor

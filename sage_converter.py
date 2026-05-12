"""
Module de conversion des transactions bancaires vers les formats d'import Sage.
Supporte : Sage 100, Sage i7, Sage 50 (Ciel).
"""

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from extractor import BankStatementExtractor


class SageConverter:
    """Convertisseur de transactions bancaires vers le format Sage."""

    def __init__(self, extractor: BankStatementExtractor):
        self.extractor = extractor
        self.transactions_df = extractor.to_dataframe()

    def to_sage_100_csv(
        self,
        output_path: str,
        journal_code: str = "BNK",
        compte_bancaire: str = "514100",  # Compte bancaire au plan comptable marocain
        compte_fournisseur: str = "441100",  # Fournisseurs - Effets à payer
        compte_client: str = "342100",  # Clients - Effets à recevoir
        compte_charges: str = "613400",  # Frais bancaires
        include_header: bool = True,
        delimiter: str = "|"
    ) -> str:
        """
        Génère un fichier CSV compatible avec Sage 100.

        Format Sage 100 attendu :
        Code journal | N° compte général | N° compte tiers | Date pièce |
        Montant débit | Montant crédit | N° facture | Libellé écriture |
        Date échéance | N° pièce | Type écriture

        Args:
            output_path : Chemin du fichier de sortie
            journal_code : Code du journal (ex: BNK pour banque)
            compte_bancaire : Numéro du compte bancaire au plan comptable
            delimiter : Séparateur de champs

        Returns:
            Chemin du fichier généré
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=delimiter)

            if include_header:
                writer.writerow([
                    "Code journal", "N° compte général", "N° compte tiers",
                    "Date pièce", "Montant débit", "Montant crédit",
                    "N° facture", "Libellé écriture", "Date échéance",
                    "N° pièce", "Type écriture"
                ])

            for idx, row in self.transactions_df.iterrows():
                date_piece = self._format_date(row.get("date", ""))
                libelle = self._clean_label(row.get("description", ""))
                debit = row.get("debit", 0.0)
                credit = row.get("credit", 0.0)
                reference = row.get("reference", "")

                # Pour chaque transaction, créer l'écriture comptable
                if debit > 0:
                    # Décaissement (sortie d'argent)
                    # Débit : compte de charge/fournisseur
                    # Crédit : compte bancaire
                    writer.writerow([
                        journal_code,       # Code journal
                        compte_charges,     # N° compte général (charges/fournisseur)
                        "",                 # N° compte tiers
                        date_piece,         # Date pièce
                        f"{debit:.2f}",     # Montant débit
                        "0.00",             # Montant crédit
                        reference,          # N° facture
                        f"{libelle} - DB",  # Libellé
                        "",                 # Date échéance
                        f"{idx+1:04d}",     # N° pièce
                        ""                  # Type écriture
                    ])
                    # Ligne de contrepartie (crédit banque)
                    writer.writerow([
                        journal_code,
                        compte_bancaire,    # Compte bancaire
                        "",                 # N° compte tiers
                        date_piece,
                        "0.00",
                        f"{debit:.2f}",     # Montant crédit
                        reference,
                        f"{libelle} - DB",
                        "",
                        f"{idx+1:04d}",
                        ""
                    ])

                elif credit > 0:
                    # Encaissement (entrée d'argent)
                    # Débit : compte bancaire
                    # Crédit : compte client/produit
                    writer.writerow([
                        journal_code,
                        compte_bancaire,    # Compte bancaire
                        "",                 # N° compte tiers
                        date_piece,
                        f"{credit:.2f}",    # Montant débit
                        "0.00",             # Montant crédit
                        reference,          # N° facture
                        f"{libelle} - CR",  # Libellé
                        "",                 # Date échéance
                        f"{idx+1:04d}",     # N° pièce
                        ""                  # Type écriture
                    ])
                    # Ligne de contrepartie (crédit client/produit)
                    writer.writerow([
                        journal_code,
                        compte_client,      # Compte client
                        "",                 # N° compte tiers
                        date_piece,
                        "0.00",
                        f"{credit:.2f}",    # Montant crédit
                        reference,
                        f"{libelle} - CR",
                        "",
                        f"{idx+1:04d}",
                        ""
                    ])

        return str(output_path)

    def to_sage_100_txt(
        self,
        output_path: str,
        journal_code: str = "BNK",
        compte_bancaire: str = "514100",
        compte_fournisseur: str = "441100",
        compte_client: str = "342100",
        compte_charges: str = "613400",
        encoding: str = "windows-1252"
    ) -> str:
        """
        Génère un fichier TXT (tabulé) compatible avec Sage 100.
        Format standard : fichier texte avec séparateur tabulation.

        Args:
            output_path : Chemin du fichier .txt
            journal_code : Code du journal
            compte_bancaire : Compte bancaire au plan comptable
            encoding : Encodage (Windows-1252 par défaut pour Sage)

        Returns:
            Chemin du fichier généré
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding=encoding, newline='') as f:
            # Écrire les lignes d'écritures comptables
            for idx, row in self.transactions_df.iterrows():
                date_piece = self._format_date(row.get("date", ""))
                libelle = self._clean_label(row.get("description", ""))
                debit = float(row.get("debit", 0.0))
                credit = float(row.get("credit", 0.0))
                reference = str(row.get("reference", ""))

                if debit > 0:
                    # Ligne débit (charge)
                    f.write(f"{journal_code}\t{compte_charges}\t\t{date_piece}\t")
                    f.write(f"{debit:.2f}\t0.00\t{reference}\t{libelle} - DB\t\t{idx+1:04d}\t\n")
                    # Ligne crédit (banque)
                    f.write(f"{journal_code}\t{compte_bancaire}\t\t{date_piece}\t")
                    f.write(f"0.00\t{debit:.2f}\t{reference}\t{libelle} - DB\t\t{idx+1:04d}\t\n")

                elif credit > 0:
                    # Ligne débit (banque)
                    f.write(f"{journal_code}\t{compte_bancaire}\t\t{date_piece}\t")
                    f.write(f"{credit:.2f}\t0.00\t{reference}\t{libelle} - CR\t\t{idx+1:04d}\t\n")
                    # Ligne crédit (client)
                    f.write(f"{journal_code}\t{compte_client}\t\t{date_piece}\t")
                    f.write(f"0.00\t{credit:.2f}\t{reference}\t{libelle} - CR\t\t{idx+1:04d}\t\n")

        return str(output_path)

    def to_sage_i7_format(
        self,
        output_path: str,
        journal_code: str = "B",
        compte_bancaire: str = "5141",
        encoding: str = "windows-1252"
    ) -> str:
        """
        Génère un fichier compatible Sage i7 (format ASCII délimité).
        Format : Code journal;Date;Numéro compte;Libellé;Débit;Crédit

        Args:
            output_path : Chemin du fichier
            journal_code : Code journal (1 caractère pour i7)
            compte_bancaire : Racine du compte bancaire
            encoding : Encodage du fichier

        Returns:
            Chemin du fichier généré
        """
        output_path = Path(output_path)
        output_path.parent(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding=encoding, newline='') as f:
            for idx, row in self.transactions_df.iterrows():
                date_piece = self._format_date(row.get("date", ""), sep="/")
                libelle = self._clean_label(row.get("description", ""))
                debit = float(row.get("debit", 0.0))
                credit = float(row.get("credit", 0.0))

                if debit > 0:
                    # Écriture de décaissement
                    f.write(f"{journal_code};{date_piece};{compte_bancaire}00;")
                    f.write(f"{libelle};0.00;{debit:.2f}\n")

                elif credit > 0:
                    # Écriture d'encaissement
                    f.write(f"{journal_code};{date_piece};{compte_bancaire}00;")
                    f.write(f"{libelle};{credit:.2f};0.00\n")

        return str(output_path)

    def to_simple_csv(
        self,
        output_path: str,
        delimiter: str = ";"
    ) -> str:
        """
        Génère un CSV simple avec les transactions brutes.
        Utile pour import manuel ou traitement externe.

        Args:
            output_path : Chemin du fichier
            delimiter : Séparateur

        Returns:
            Chemin du fichier généré
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Préparer les données
        df = self.transactions_df.copy()
        df["montant"] = df["credit"] - df["debit"]
        df["type"] = df.apply(
            lambda row: "CREDIT" if row["credit"] > 0 else ("DEBIT" if row["debit"] > 0 else ""),
            axis=1
        )

        # Réorganiser les colonnes
        columns_order = [
            "date", "date_valeur", "description", "reference",
            "debit", "credit", "montant", "type"
        ]
        df = df[[col for col in columns_order if col in df.columns]]

        df.to_csv(output_path, index=False, sep=delimiter, encoding='utf-8-sig')
        return str(output_path)

    def generate_report(self, output_path: str):
        """
        Génère un rapport récapitulatif des transactions.

        Args:
            output_path : Chemin du fichier de rapport
        """
        output_path = Path(output_path)
        summary = self.extractor.get_summary()

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("RAPPORT DE TRAITEMENT DU RELEVE BANCAIRE\n")
            f.write("=" * 60 + "\n\n")

            f.write(f"Banque           : {summary['banque']}\n")
            f.write(f"Titulaire        : {summary['titulaire']}\n")
            f.write(f"Numero de compte : {summary['numero_compte']}\n")
            f.write(f"Devise           : {summary['devise']}\n")
            f.write(f"Periode du       : {summary['periode_debut']}\n")
            f.write(f"Periode au       : {summary['periode_fin']}\n")
            f.write(f"Solde ouverture  : {summary['solde_ouverture']:.2f}\n")
            f.write(f"Solde cloture    : {summary['solde_cloture']:.2f}\n\n")

            f.write("-" * 60 + "\n")
            f.write("STATISTIQUES DES TRANSACTIONS\n")
            f.write("-" * 60 + "\n")
            f.write(f"Nombre total de transactions : {summary['nombre_transactions']}\n")
            f.write(f"Total des debits             : {summary['total_debit']:.2f}\n")
            f.write(f"Total des credits            : {summary['total_credit']:.2f}\n")
            f.write(f"Balance (credits - debits)    : {summary['total_credit'] - summary['total_debit']:.2f}\n\n")

            f.write("-" * 60 + "\n")
            f.write("LISTE DES TRANSACTIONS\n")
            f.write("-" * 60 + "\n")

            for idx, row in self.transactions_df.iterrows():
                f.write(f"\n{idx+1:3d}. [{row.get('date', '')}] ")
                f.write(f"{row.get('description', '')[:40]:40s} ")
                debit = row.get("debit", 0.0)
                credit = row.get("credit", 0.0)
                if debit > 0:
                    f.write(f"DB: {debit:>10.2f}")
                elif credit > 0:
                    f.write(f"CR: {credit:>10.2f}")
                f.write("\n")

        return str(output_path)

    def _format_date(self, date_str: str, sep: str = "/") -> str:
        """Formate une date au format JJ/MM/AAAA."""
        if not date_str:
            return datetime.now().strftime(f"%d{sep}%m{sep}%Y")

        # Essayer différents formats
        for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%y"]:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime(f"%d{sep}%m{sep}%Y")
            except ValueError:
                continue

        return date_str

    def _clean_label(self, label: str) -> str:
        """Nettoie un libellé pour l'import Sage (retire tabulations, retours ligne)."""
        if not label:
            return ""
        label = str(label)
        # Retirer les caractères problématiques pour Sage
        label = label.replace("\t", " ")
        label = label.replace("\n", " ")
        label = label.replace("\r", " ")
        label = label.replace("|", " ")
        label = label.replace(";", " ")
        # Limiter à 35 caractères (limite Sage)
        label = label[:35].strip()
        return label


def convert_statement(
    extractor: BankStatementExtractor,
    output_dir: str,
    output_format: str = "sage100_txt",
    journal_code: str = "BNK",
    compte_bancaire: str = "514100",
    **kwargs
) -> Dict[str, str]:
    """
    Convertit un relevé bancaire extrait vers le format Sage souhaité.

    Args:
        extractor : Instance de BankStatementExtractor avec les données extraites
        output_dir : Répertoire de sortie
        output_format : 'sage100_txt', 'sage100_csv', 'sage_i7', 'simple_csv'
        journal_code : Code du journal
        compte_bancaire : Numéro du compte bancaire au plan comptable

    Returns:
        Dictionnaire avec les chemins des fichiers générés
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    converter = SageConverter(extractor)
    base_name = f"{extractor.bank_name.replace(' ', '_')}_{extractor.account_number}"

    generated_files = {}

    # Générer le fichier selon le format demandé
    if output_format == "sage100_txt":
        output_path = output_dir / f"{base_name}_SAGE100.txt"
        converter.to_sage_100_txt(
            str(output_path),
            journal_code=journal_code,
            compte_bancaire=compte_bancaire,
            **{k: v for k, v in kwargs.items() if k in ['compte_fournisseur', 'compte_client', 'compte_charges', 'encoding']}
        )
        generated_files["sage100_txt"] = str(output_path)

    elif output_format == "sage100_csv":
        output_path = output_dir / f"{base_name}_SAGE100.csv"
        converter.to_sage_100_csv(
            str(output_path),
            journal_code=journal_code,
            compte_bancaire=compte_bancaire,
            **{k: v for k, v in kwargs.items() if k in ['compte_fournisseur', 'compte_client', 'compte_charges', 'delimiter']}
        )
        generated_files["sage100_csv"] = str(output_path)

    elif output_format == "sage_i7":
        output_path = output_dir / f"{base_name}_SAGEi7.txt"
        converter.to_sage_i7_format(
            str(output_path),
            journal_code=journal_code,
            compte_bancaire=compte_bancaire,
            **{k: v for k, v in kwargs.items() if k in ['encoding']}
        )
        generated_files["sage_i7"] = str(output_path)

    elif output_format == "simple_csv":
        output_path = output_dir / f"{base_name}_transactions.csv"
        converter.to_simple_csv(str(output_path))
        generated_files["simple_csv"] = str(output_path)

    else:
        raise ValueError(f"Format non supporté : {output_format}")

    # Générer aussi le rapport
    report_path = output_dir / f"{base_name}_RAPPORT.txt"
    converter.generate_report(str(report_path))
    generated_files["rapport"] = str(report_path)

    return generated_files

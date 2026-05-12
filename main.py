#!/usr/bin/env python3
"""
Bank Statement Processor for Moroccan Banks
Extracts transactions from PDF bank statements and converts them to Sage import formats.

Supported banks:
    - Attijariwafa Bank
    - CIH Bank (Crédit Immobilier et Hôtelier)
    - Banque Populaire (BCP)

Supported Sage formats:
    - Sage 100 (.txt with tab delimiter)
    - Sage 100 (.csv with | delimiter)
    - Sage i7 (.txt with semicolon delimiter)
    - Simple CSV export

Usage:
    python main.py --input releve.pdf --bank auto --format sage100_txt --output ./output
    python main.py -i releve.pdf -b attijari -f sage100_csv -o ./output
    python main.py -i ./releves/ --batch -b auto -f sage100_txt -o ./output
"""

import argparse
import sys
import time
from pathlib import Path

from colorama import init, Fore, Style
from extractor import extract_statement, detect_bank
from sage_converter import convert_statement

init(autoreset=True)


def print_banner():
    """Affiche le banner du programme."""
    banner = f"""
{Fore.CYAN}╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     {Fore.WHITE}Bank Statement Processor - Relevés Bancaires Maroc{Fore.CYAN}      ║
║                                                              ║
║     {Fore.YELLOW}Attijariwafa Bank | CIH Bank | Banque Populaire{Fore.CYAN}        ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝{Style.RESET_ALL}
    """
    print(banner)


def print_success(message: str):
    """Affiche un message de succès."""
    print(f"{Fore.GREEN}✓ {message}{Style.RESET_ALL}")


def print_error(message: str):
    """Affiche un message d'erreur."""
    print(f"{Fore.RED}✗ {message}{Style.RESET_ALL}")


def print_info(message: str):
    """Affiche un message d'information."""
    print(f"{Fore.BLUE}ℹ {message}{Style.RESET_ALL}")


def print_warning(message: str):
    """Affiche un message d'avertissement."""
    print(f"{Fore.YELLOW}⚠ {message}{Style.RESET_ALL}")


def process_single_file(
    input_path: str,
    bank: str,
    output_format: str,
    output_dir: str,
    journal_code: str,
    compte_bancaire: str,
    **kwargs
) -> dict:
    """
    Traite un seul fichier PDF.

    Returns:
        Dictionnaire avec les chemins des fichiers générés
    """
    input_path = Path(input_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Fichier non trouvé : {input_path}")

    print(f"\n{Fore.CYAN}{'─' * 60}{Style.RESET_ALL}")
    print_info(f"Traitement du fichier : {input_path.name}")

    # Étape 1 : Détection de la banque
    if bank == "auto":
        print_info("Détection automatique de la banque...")
        detected_bank = detect_bank(str(input_path))
        if detected_bank != "unknown":
            bank_names = {
                "attijari": "Attijariwafa Bank",
                "cih": "CIH Bank",
                "bp": "Banque Populaire"
            }
            print_success(f"Banque détectée : {bank_names.get(detected_bank, detected_bank)}")
            bank = detected_bank
        else:
            print_error("Banque non détectée automatiquement.")
            print_warning("Veuillez spécifier la banque avec --bank : attijari | cih | bp")
            raise ValueError("Banque non détectée")

    # Étape 2 : Extraction des transactions
    print_info("Extraction des transactions du PDF...")
    start_time = time.time()

    try:
        extractor = extract_statement(str(input_path), bank=bank)
        summary = extractor.get_summary()

        elapsed = time.time() - start_time
        print_success(f"Extraction terminée en {elapsed:.2f}s")
        print(f"\n  {Fore.WHITE}Résumé du relevé :{Style.RESET_ALL}")
        print(f"  ── Banque           : {summary['banque']}")
        print(f"  ── Titulaire        : {summary['titulaire']}")
        print(f"  ── N° Compte        : {summary['numero_compte']}")
        print(f"  ── Devise           : {summary['devise']}")
        print(f"  ── Période          : {summary['periode_debut']} au {summary['periode_fin']}")
        print(f"  ── Solde ouverture  : {summary['solde_ouverture']:.2f}")
        print(f"  ── Solde clôture    : {summary['solde_cloture']:.2f}")
        print(f"  ── Transactions     : {summary['nombre_transactions']}")
        print(f"  ── Total Débits     : {summary['total_debit']:.2f}")
        print(f"  ── Total Crédits    : {summary['total_credit']:.2f}")

    except Exception as e:
        print_error(f"Erreur lors de l'extraction : {e}")
        raise

    # Étape 3 : Conversion vers le format Sage
    print_info(f"Conversion vers le format : {output_format}...")

    try:
        generated_files = convert_statement(
            extractor,
            output_dir=output_dir,
            output_format=output_format,
            journal_code=journal_code,
            compte_bancaire=compte_bancaire,
            **{k: v for k, v in kwargs.items() if v is not None}
        )

        print_success("Conversion terminée !")
        print(f"\n  {Fore.WHITE}Fichiers générés :{Style.RESET_ALL}")
        for file_type, file_path in generated_files.items():
            file_size = Path(file_path).stat().st_size
            print(f"  ── [{file_type:12s}] {file_path} ({file_size:,} octets)")

        return generated_files

    except Exception as e:
        print_error(f"Erreur lors de la conversion : {e}")
        raise


def process_batch(
    input_dir: str,
    bank: str,
    output_format: str,
    output_dir: str,
    journal_code: str,
    compte_bancaire: str,
    **kwargs
) -> list:
    """
    Traite plusieurs fichiers PDF dans un répertoire.

    Returns:
        Liste des résultats pour chaque fichier
    """
    input_dir = Path(input_dir)

    if not input_dir.is_dir():
        raise NotADirectoryError(f"Répertoire non trouvé : {input_dir}")

    # Chercher tous les fichiers PDF
    pdf_files = sorted(input_dir.glob("*.pdf"))

    if not pdf_files:
        print_warning(f"Aucun fichier PDF trouvé dans : {input_dir}")
        return []

    print_info(f"{len(pdf_files)} fichier(s) PDF trouvé(s) dans : {input_dir}")

    results = []
    for i, pdf_file in enumerate(pdf_files, 1):
        print(f"\n{Fore.CYAN}[{i}/{len(pdf_files)}]{Style.RESET_ALL}")
        try:
            result = process_single_file(
                str(pdf_file),
                bank=bank,
                output_format=output_format,
                output_dir=output_dir,
                journal_code=journal_code,
                compte_bancaire=compte_bancaire,
                **kwargs
            )
            results.append({"file": str(pdf_file), "status": "success", "output": result})
        except Exception as e:
            print_error(f"Échec du traitement de {pdf_file.name} : {e}")
            results.append({"file": str(pdf_file), "status": "error", "error": str(e)})

    # Résumé du batch
    print(f"\n{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}")
    print(f"{Fore.WHITE}RÉSUMÉ DU TRAITEMENT PAR LOT{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}")
    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = sum(1 for r in results if r["status"] == "error")
    print(f"  Total traités  : {len(results)}")
    print_success(f"  Succès         : {success_count}")
    if error_count > 0:
        print_error(f"  Échecs         : {error_count}")

    return results


def main():
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Extracteur de relevés bancaires marocains vers Sage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples d'utilisation :
  # Détection automatique et export Sage 100
  python main.py -i releve.pdf -o ./output

  # Spécifier la banque et le format
  python main.py -i releve.pdf -b cih -f sage100_txt -o ./output

  # Traitement par lot
  python main.py -i ./releves/ --batch -o ./output

  # Avec paramètres comptables personnalisés
  python main.py -i releve.pdf -b attijari -f sage100_csv \\
      --journal BNK --compte-bancaire 514100 \\
      --compte-fournisseur 441100 --compte-client 342100 -o ./output
        """
    )

    # Arguments principaux
    parser.add_argument("-i", "--input", required=True,
                        help="Chemin du fichier PDF ou répertoire (avec --batch)")
    parser.add_argument("-o", "--output", default="./output",
                        help="Répertoire de sortie (défaut: ./output)")

    # Options de banque
    parser.add_argument("-b", "--bank", default="auto",
                        choices=["auto", "attijari", "cih", "bp"],
                        help="Banque : auto, attijari, cih, bp (défaut: auto)")

    # Options de format
    parser.add_argument("-f", "--format", default="sage100_txt",
                        choices=["sage100_txt", "sage100_csv", "sage_i7", "simple_csv"],
                        help="Format de sortie Sage (défaut: sage100_txt)")

    # Options comptables
    parser.add_argument("--journal", default="BNK",
                        help="Code journal comptable (défaut: BNK)")
    parser.add_argument("--compte-bancaire", default="514100",
                        help="N° compte bancaire au plan comptable (défaut: 514100)")
    parser.add_argument("--compte-fournisseur", default="441100",
                        help="N° compte fournisseurs (défaut: 441100)")
    parser.add_argument("--compte-client", default="342100",
                        help="N° compte clients (défaut: 342100)")
    parser.add_argument("--compte-charges", default="613400",
                        help="N° compte frais bancaires (défaut: 613400)")

    # Options de traitement
    parser.add_argument("--batch", action="store_true",
                        help="Traitement par lot (le --input doit être un répertoire)")
    parser.add_argument("--delimiter", default="|",
                        help="Délimiteur pour CSV (défaut: |)")

    args = parser.parse_args()

    # Afficher le banner
    print_banner()

    try:
        if args.batch:
            # Mode batch
            process_batch(
                input_dir=args.input,
                bank=args.bank,
                output_format=args.format,
                output_dir=args.output,
                journal_code=args.journal,
                compte_bancaire=args.compte_bancaire,
                compte_fournisseur=args.compte_fournisseur,
                compte_client=args.compte_client,
                compte_charges=args.compte_charges,
                delimiter=args.delimiter
            )
        else:
            # Mode fichier unique
            process_single_file(
                input_path=args.input,
                bank=args.bank,
                output_format=args.format,
                output_dir=args.output,
                journal_code=args.journal,
                compte_bancaire=args.compte_bancaire,
                compte_fournisseur=args.compte_fournisseur,
                compte_client=args.compte_client,
                compte_charges=args.compte_charges,
                delimiter=args.delimiter
            )

        print(f"\n{Fore.GREEN}{'=' * 60}")
        print(f"Traitement terminé avec succès !")
        print(f"{'=' * 60}{Style.RESET_ALL}\n")

    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Interrompu par l'utilisateur.{Style.RESET_ALL}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Fore.RED}{'=' * 60}")
        print(f"ERREUR : {e}")
        print(f"{'=' * 60}{Style.RESET_ALL}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
##

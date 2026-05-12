"""
Module de conversion vers Sage. Version production.
"""
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict
import pandas as pd
from extractor import BankStatementExtractor

PCM = {"banque":"5141","client":"3421","fournisseur":"4411","frais":"6347","charges":"6141","salaires":"6171","cnss":"6174","tva":"4456","loyers":"6131"}
SAGE_MAX = 35

class SageConverter:
    def __init__(self, extractor, compte_bancaire="5141", compte_client="3421", compte_fournisseur="4411", compte_charges="6347"):
        self.extractor = extractor
        self.df = extractor.to_dataframe()
        self.cpt_banque = compte_bancaire
        self.cpt_client = compte_client
        self.cpt_fourn = compte_fournisseur
        self.cpt_charges = compte_charges

    def _contre(self, row):
        cat = str(row.get("categorie","")).lower()
        m = {"salaires":"6171","cotisations_sociales":"6174","cnss":"6174","impots_taxes":"4456","tva":"4456","loyers":"6131","frais_bancaires":"6347","encaissement_client":self.cpt_client,"encaissement":self.cpt_client,"paiement_fournisseur":self.cpt_fourn}
        if cat in m: return m[cat]
        return self.cpt_client if float(row.get("credit",0))>0 else self.cpt_charges

    def _lbl(self, s): return str(s or "").replace("\t"," ").replace("\n"," ").replace("|"," ").replace(";"," ")[:SAGE_MAX].strip()

    def _date(self, s, sep="/"):
        for fmt in ["%d/%m/%Y","%d-%m-%Y","%Y-%m-%d","%d/%m/%y"]:
            try: return datetime.strptime(str(s),fmt).strftime(f"%d{sep}%m{sep}%Y")
            except: pass
        return str(s) if s else datetime.now().strftime(f"%d{sep}%m{sep}%Y")

    def to_sage_100_txt(self, output_path, journal_code="BQ", encoding="windows-1252"):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path,'w',encoding=encoding,newline='') as f:
            for idx, row in self.df.iterrows():
                d=self._date(row.get("date","")); l=self._lbl(row.get("description",""))
                db=float(row.get("debit",0)); cr=float(row.get("credit",0))
                rf=str(row.get("reference_facture","") or row.get("reference","") or "")
                ct=self._contre(row); n=f"{idx+1:04d}"
                if db>0:
                    f.write(f"{journal_code}\t{ct}\t\t{d}\t{db:.2f}\t0.00\t{rf}\t{l}\t\t{n}\t\n")
                    f.write(f"{journal_code}\t{self.cpt_banque}\t\t{d}\t0.00\t{db:.2f}\t{rf}\t{l}\t\t{n}\t\n")
                elif cr>0:
                    f.write(f"{journal_code}\t{self.cpt_banque}\t\t{d}\t{cr:.2f}\t0.00\t{rf}\t{l}\t\t{n}\t\n")
                    f.write(f"{journal_code}\t{ct}\t\t{d}\t0.00\t{cr:.2f}\t{rf}\t{l}\t\t{n}\t\n")
        return output_path

    def to_sage_100_csv(self, output_path, journal_code="BQ", delimiter="|"):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path,'w',newline='',encoding='utf-8-sig') as f:
            w=csv.writer(f,delimiter=delimiter)
            w.writerow(["Code journal","N° compte général","N° compte tiers","Date pièce","Montant débit","Montant crédit","N° facture","Libellé écriture","Date échéance","N° pièce","Type écriture"])
            for idx, row in self.df.iterrows():
                d=self._date(row.get("date","")); l=self._lbl(row.get("description",""))
                db=float(row.get("debit",0)); cr=float(row.get("credit",0))
                rf=str(row.get("reference_facture","") or ""); ct=self._contre(row); n=f"{idx+1:04d}"
                if db>0:
                    w.writerow([journal_code,ct,"",d,f"{db:.2f}","0.00",rf,l,"",n,""])
                    w.writerow([journal_code,self.cpt_banque,"",d,"0.00",f"{db:.2f}",rf,l,"",n,""])
                elif cr>0:
                    w.writerow([journal_code,self.cpt_banque,"",d,f"{cr:.2f}","0.00",rf,l,"",n,""])
                    w.writerow([journal_code,ct,"",d,"0.00",f"{cr:.2f}",rf,l,"",n,""])
        return output_path

    def to_sage_i7_format(self, output_path, journal_code="B", encoding="windows-1252"):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path,'w',encoding=encoding,newline='') as f:
            for idx, row in self.df.iterrows():
                d=self._date(row.get("date",""),sep="/"); l=self._lbl(row.get("description",""))
                db=float(row.get("debit",0)); cr=float(row.get("credit",0))
                if db>0: f.write(f"{journal_code};{d};{self.cpt_banque};{l};0.00;{db:.2f}\n")
                elif cr>0: f.write(f"{journal_code};{d};{self.cpt_banque};{l};{cr:.2f};0.00\n")
        return output_path

    def to_simple_csv(self, output_path, delimiter=";"):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        df = self.df.copy()
        if df.empty:
            df.to_csv(output_path, index=False, sep=delimiter, encoding='utf-8-sig')
            return output_path
        df["montant"] = df["credit"] - df["debit"]
        df["type"] = df.apply(lambda r: "CREDIT" if float(r.get("credit",0))>0 else ("DEBIT" if float(r.get("debit",0))>0 else ""), axis=1)
        cols=["date","date_valeur","description","reference","reference_facture","debit","credit","montant","type","categorie","compte_comptable"]
        df[[c for c in cols if c in df.columns]].to_csv(output_path,index=False,sep=delimiter,encoding='utf-8-sig')
        return output_path

    def generate_report(self, output_path):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        s = self.extractor.get_summary()
        with open(output_path,'w',encoding='utf-8') as f:
            f.write("="*65+"\nRAPPORT RELEVÉ BANCAIRE\n"+"="*65+"\n\n")
            for k,v in [("Banque",s['banque']),("Titulaire",s['titulaire']),("N° Compte",s['numero_compte']),("Devise",s['devise']),("Période",f"{s['periode_debut']} → {s['periode_fin']}"),("Solde ouverture",f"{s['solde_ouverture']:.2f} MAD"),("Solde clôture",f"{s['solde_cloture']:.2f} MAD")]:
                f.write(f"{k:20}: {v}\n")
            f.write(f"\n{'-'*65}\nSTATISTIQUES\n{'-'*65}\n")
            f.write(f"Transactions     : {s['nombre_transactions']}\nTotal débits     : {s['total_debit']:.2f} MAD\nTotal crédits    : {s['total_credit']:.2f} MAD\nBalance          : {s['total_credit']-s['total_debit']:.2f} MAD\n\n")
            f.write(f"{'-'*65}\nTRANSACTIONS\n{'-'*65}\n")
            for idx, row in self.df.iterrows():
                db=float(row.get("debit",0)); cr=float(row.get("credit",0))
                rf=str(row.get("reference_facture","") or "")
                f.write(f"\n{idx+1:3d}. [{row.get('date','')}] {str(row.get('description',''))[:40]:40s} ")
                if db>0: f.write(f"DB:{db:>10.2f}  Cpt:{row.get('compte_comptable','')}")
                elif cr>0: f.write(f"CR:{cr:>10.2f}  Cpt:{row.get('compte_comptable','')}")
                if rf: f.write(f"  → {rf}")
                f.write("\n")
        return output_path


def convert_statement(extractor, output_dir, output_format="sage100_txt", journal_code="BQ",
                      compte_bancaire="5141", compte_client="3421", compte_fournisseur="4411",
                      compte_charges="6347", **kwargs):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    conv = SageConverter(extractor, compte_bancaire=compte_bancaire, compte_client=compte_client, compte_fournisseur=compte_fournisseur, compte_charges=compte_charges)
    base = f"{extractor.bank_name.replace(' ','_')}_{extractor.account_number.replace(' ','')[:15]}" or "releve"
    out = {}
    if output_format == "sage100_txt":
        p = str(output_dir/f"{base}_SAGE100.txt")
        conv.to_sage_100_txt(p, journal_code=journal_code, encoding=kwargs.get("encoding","windows-1252"))
        out["sage100_txt"] = p
    elif output_format == "sage100_csv":
        p = str(output_dir/f"{base}_SAGE100.csv")
        conv.to_sage_100_csv(p, journal_code=journal_code, delimiter=kwargs.get("delimiter","|"))
        out["sage100_csv"] = p
    elif output_format == "sage_i7":
        p = str(output_dir/f"{base}_SAGEi7.txt")
        conv.to_sage_i7_format(p, journal_code=journal_code, encoding=kwargs.get("encoding","windows-1252"))
        out["sage_i7"] = p
    elif output_format == "simple_csv":
        p = str(output_dir/f"{base}_transactions.csv")
        conv.to_simple_csv(p)
        out["simple_csv"] = p
    else:
        raise ValueError(f"Format non supporté: {output_format}")
    rp = str(output_dir/f"{base}_RAPPORT.txt")
    conv.generate_report(rp)
    out["rapport"] = rp
    return out

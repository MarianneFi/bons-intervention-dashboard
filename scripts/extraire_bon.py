#!/usr/bin/env python3
"""
Extrait les champs d'un bon d'intervention .docx vers le schéma du tableau de bord.

Les bons arrivent en .docx dans le dossier OneDrive « Bons dintervention », déposés
par un flux Power Automate. Deux mises en page coexistent :

  A. tableau étiqueté  -> l'étiquette est seule sur sa ligne, la valeur suit
  B. étiquettes en ligne -> « MOTIF DE L'INTERVENTION : ... »

Ce script gère les deux. Il ne renseigne PAS les champs qui ne figurent pas dans le
document : `urgence` et `action` sont éditoriaux, `gestionnaire*` vient du tableau
des secteurs.

Usage :  python3 scripts/extraire_bon.py <fichier.docx> [...]   -> JSON sur stdout
"""
import json, re, sys, unicodedata, zipfile
from pathlib import Path

ETIQUETTES = {
    "date":            ["date"],
    "heure_entree":    ["heure d'entree"],
    "heure_sortie":    ["heure de sortie"],
    "site":            ["denomination du site"],
    "adresse":         ["adresse"],
    "locataire":       ["nom du locataire"],
    "motif":           ["motif de l'intervention"],
    "constat":         ["actions menees"],
    "remarque":        ["commentaires"],
    "statut":          ["statut du dossier", "statut"],
    "astreinte_qui":   ["cadre d'astreinte appele"],
    "astreinte_heure": ["heure d'appel au cadre d'astreinte"],
}
VIDE = {"", "(non renseigne)", "(non renseigné)", "néant", "neant", "-", "/"}

# Titres de section : jamais une valeur, même s'ils suivent une étiquette vide.
TITRES = {
    "informations generales", "compte-rendu de l'intervention",
    "compte rendu de l'intervention", "detail de l'intervention",
    "client : semise",
}


def _pluck(p):
    """Texte brut du .docx, un paragraphe par ligne."""
    with zipfile.ZipFile(p) as z:
        xml = z.read("word/document.xml").decode("utf8")
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:tab/>", "\t", xml)
    txt = re.sub(r"<[^>]+>", "", xml)
    txt = txt.replace("&amp;", "&").replace("&apos;", "'").replace("&quot;", '"')
    return [l.strip() for l in txt.split("\n")]


def _plat(s):
    """Minuscules sans accents, pour comparer les étiquettes."""
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").strip()


def _champs(lignes):
    """Renvoie {cle: valeur} en gérant les deux mises en page."""
    out, n = {}, len(lignes)
    for i, ligne in enumerate(lignes):
        if not ligne:
            continue
        plat = _plat(ligne)
        for cle, formes in ETIQUETTES.items():
            if cle in out:
                continue
            for forme in formes:
                # mise en page B : « ETIQUETTE : valeur »
                m = re.match(rf"^{re.escape(forme)}\s*:\s*(.*)$", plat)
                if m:
                    valeur = ligne.split(":", 1)[1].strip()
                    if valeur:
                        out[cle] = valeur
                        break
                    # étiquette suivie de « : » mais valeur au paragraphe suivant
                    suite = lignes[i + 1].strip() if i + 1 < n else ""
                    if suite and _plat(suite) not in TITRES:
                        out[cle] = suite
                    break
                # mise en page A : étiquette seule, valeur à la ligne suivante
                if plat == forme and i + 1 < n:
                    suite = lignes[i + 1].strip()
                    connue = any(_plat(suite) == f for fs in ETIQUETTES.values() for f in fs)
                    if suite and not connue and _plat(suite) not in TITRES:
                        out[cle] = suite
                    break
    return out


def _propre(v):
    return "" if v is None or _plat(v) in VIDE else v.strip()


def _date_iso(v):
    m = re.search(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", v or "")
    return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else ""


def _heure(v):
    m = re.search(r"(\d{1,2})\s*[Hh:]\s*(\d{2})", v or "")
    return f"{int(m.group(1)):02d}h{m.group(2)}" if m else ""


def _titre(v):
    """TOURAINE -> Touraine ; MM NEROME -> M. Nerome."""
    v = re.sub(r"\s+", " ", (v or "").strip())
    if not v:
        return ""
    mots = []
    for mot in v.split(" "):
        p = _plat(mot).rstrip(".")
        if p in ("mm", "mr", "m"):
            mots.append("M."); continue
        if p in ("md", "mme", "mmd"):
            mots.append("Mme"); continue
        if p == "mlle":
            mots.append("Mlle"); continue
        mots.append(mot.capitalize() if mot.isupper() else mot)
    return " ".join(mots)


def extraire(chemin):
    chemin = Path(chemin)
    lignes = _pluck(chemin)
    c = {k: _propre(v) for k, v in _champs(lignes).items()}

    m = re.search(r"N°\s*([0-9.]+)", chemin.name)
    numero = m.group(1).rstrip(".") if m else ""

    site, loc = _titre(c.get("site", "")), _titre(c.get("locataire", ""))
    entree, sortie = _heure(c.get("heure_entree", "")), _heure(c.get("heure_sortie", ""))
    astreinte_qui = c.get("astreinte_qui", "")
    astreinte_h = _heure(c.get("astreinte_heure", ""))
    statut_brut = _plat(c.get("statut", ""))

    return {
        "numero": numero,
        "date": _date_iso(c.get("date", "")),
        "heure": f"{entree} - {sortie}" if entree and sortie else entree,
        "site": f"{site} &middot; {loc}" if loc else site,
        "urgence": None,                       # éditorial, absent du document
        "statut": "cloture" if "clotur" in statut_brut else "attente",
        "astreinte": "oui" if astreinte_qui else "non",
        "astreinteDetail": ", ".join(x for x in (_titre(astreinte_qui), astreinte_h) if x),
        "gestionnaire": "",                    # depuis le Tableau des secteurs SEV
        "gestionnaireTel": "",
        "gestionnaireEmail": "",
        "motif": c.get("motif", ""),
        "constat": c.get("constat", ""),
        "action": "",                          # éditorial, ajouté par Marianne
        "remarque": c.get("remarque", ""),
        "_fichier": chemin.name,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    print(json.dumps([extraire(a) for a in sys.argv[1:]], ensure_ascii=False, indent=2))

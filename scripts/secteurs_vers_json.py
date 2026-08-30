#!/usr/bin/env python3
"""
Convertit « Tableau des secteurs SEV <date>.xlsx » en secteurs.json.

Le tableau de bord a besoin, pour chaque bon, du gestionnaire de site du secteur
dont dépend la résidence : nom, téléphone, et adresse mail de la loge. Ces trois
champs ne figurent pas dans le bon d'intervention ; ils se déduisent de la
résidence via ce tableau.

Usage :  python3 scripts/secteurs_vers_json.py <fichier.xlsx> [> secteurs.json]
"""
import json, re, sys, unicodedata, zipfile
import xml.etree.ElementTree as ET

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
TEL = re.compile(r"\b0\d(?:[ .]\d{2}){4}\b")
# Le tableau est saisi sans accents ; la base, elle, en met.
ACCENTS = {"Ampere": "Ampère"}
MAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def _plat(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").strip()


def _titre(nom):
    """NOM DE FAMILLE -> Nom De Famille, en gardant les traits d'union."""
    mots = []
    for mot in re.split(r"(\s+)", (nom or "").strip()):
        if not mot.strip():
            mots.append(mot); continue
        mots.append("-".join(p.capitalize() for p in mot.split("-")) if mot.isupper() else mot)
    return "".join(mots)


def _grille(chemin):
    z = zipfile.ZipFile(chemin)
    partagees = [
        "".join(t.text or "" for t in si.iter(f"{NS}t"))
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(f"{NS}si")
    ]
    ws = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    g = {}
    for row in ws.iter(f"{NS}row"):
        r = int(row.get("r"))
        for c in row.findall(f"{NS}c"):
            col = re.match(r"([A-Z]+)", c.get("r")).group(1)
            v = c.find(f"{NS}v")
            if v is None:
                continue
            g[(r, col)] = partagees[int(v.text)] if c.get("t") == "s" else (v.text or "")
    return g


def _gestionnaire(bloc):
    """Extrait le gestionnaire de site d'une cellule « RS / CA »."""
    lignes = [l.strip() for l in (bloc or "").split("\n") if l.strip()]
    trouves = []
    for i, l in enumerate(lignes):
        if "gestionnaire de site" not in _plat(l):
            continue
        avant = re.sub(r"(?i)gestionnaire de site", "", l).strip(" -–\t")
        nom = avant or (lignes[i - 1] if i else "")
        tel = ""
        for suite in lignes[i + 1 : i + 3]:
            m = TEL.search(suite)
            if m:
                tel = m.group(0).replace(".", " "); break
        if nom:
            vacant = "recrutement" in _plat(nom)
            trouves.append({
                "nom": "" if vacant else _titre(nom),
                "tel": tel,
                "vacant": vacant,
            })
    # un poste vacant ne doit pas masquer un gestionnaire réellement nommé
    nommes = [t for t in trouves if not t["vacant"]]
    return (nommes or trouves or [{"nom": "", "tel": "", "vacant": True}])[0]


def convertir(chemin):
    g = _grille(chemin)
    lignes = sorted({r for (r, _) in g})
    secteurs, courant = {}, None

    for r in lignes:
        a = (g.get((r, "A")) or "").strip()
        b = (g.get((r, "B")) or "").strip()
        # un en-tête de secteur : seul en colonne A, sans programme en face
        if a and not b and r > 4 and not _plat(a).startswith("total"):
            if "/" not in a and not secteurs:
                continue
            if "/" not in a:
                continue
            courant = a
            secteurs[courant] = {
                "libelle": a,
                "nom": ACCENTS.get(_titre(a.split("/")[0].strip()),
                                   _titre(a.split("/")[0].strip())),
                "gestionnaireSite": _gestionnaire(g.get((r + 1, "G"))),
                "loge": {},
                "residences": [],
            }
            h = g.get((r + 1, "H")) or ""
            m = MAIL.search(h)
            if m:
                secteurs[courant]["loge"]["email"] = m.group(0)
            for l in h.split("\n"):
                if l.strip().startswith("*") and "adresse" not in secteurs[courant]["loge"]:
                    secteurs[courant]["loge"]["adresse"] = l.strip("* ").strip()
                    break
            continue
        if courant and b and not _plat(a).startswith("total"):
            if b not in secteurs[courant]["residences"]:
                secteurs[courant]["residences"].append(b)

    index = {}
    for s in secteurs.values():
        for res in s["residences"]:
            index[res] = s["nom"]

    return {
        "source": chemin.split("/")[-1],
        "secteurs": list(secteurs.values()),
        "residence_vers_secteur": dict(sorted(index.items())),
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    print(json.dumps(convertir(sys.argv[1]), ensure_ascii=False, indent=2))

# Mettre à jour le tableau de bord des bons d'intervention

**Destinataire : Claude, sur le poste de Marianne Finel (Claude Cowork).**
**À jour au 30 août 2026. Ce document se suffit à lui-même** — aucune connaissance
de l'ancienne tâche programmée n'est nécessaire, elle ne peut plus fonctionner.

---

## 1. Ce qui a changé, et pourquoi

Le tableau de bord affiche les bons d'intervention de la résidence AAF La Providence.
Jusqu'au 29 août 2026, les 49 bons étaient écrits **en dur** dans `index.html`, à la
racine d'un dépôt GitHub **public** : 37 noms de locataires, les téléphones des
gestionnaires et des descriptions de situations individuelles étaient lisibles par
n'importe qui. C'était une fuite de données personnelles.

Le 30 août 2026, les données ont été sorties du code.

| | Avant | Maintenant |
|---|---|---|
| Où vivent les données | dans `index.html`, versionné | dans **Cloudflare KV** |
| Qui peut les lire | tout le monde | un utilisateur authentifié par Cloudflare Access |
| Mise à jour | éditer le HTML, commit, push, attendre le build | lire KV, modifier, réécrire KV |
| Le dépôt contient | le code **et** les données | le code seul |

**Une mise à jour de données ne passe plus par git.** Ni commit, ni push, ni
déploiement. Le Worker relit KV à chaque visite : une écriture est visible aussitôt.

---

## 2. Trois règles absolues

**1. Aucune donnée de locataire dans le dépôt.**
Ni dans `public/index.html`, ni dans un fichier créé à la racine, ni dans un message
de commit. Le dépôt est public.

**2. Ne jamais recréer `index.html` à la racine.**
C'est le piège principal, et il est silencieux. Le Worker sert `public/index.html` et
ignore la racine. Un fichier recréé là serait **invisible sur le tableau de bord tout
en republiant les données** : le fichier s'écrit, le commit passe, le build réussit,
et pourtant rien ne bouge à l'écran pendant que la fuite est rouverte.

**3. Ne pas toucher à `workers_dev` dans `wrangler.toml`.**
Cloudflare Access protège l'hostname `*.workers.dev`, qui est l'unique adresse du
service. Passer `workers_dev = false` mettrait le tableau de bord hors ligne.

---

## 3. Installation, une seule fois

### 3.1 Cloner et installer

```bash
git clone https://github.com/MarianneFi/bons-intervention-dashboard.git
cd bons-intervention-dashboard
npm install
```

Node.js est requis. `npm install` installe Wrangler en local.

### 3.2 Authentifier Cloudflare

```bash
npx wrangler login
npx wrangler whoami
```

Le navigateur s'ouvre, Marianne approuve. `whoami` doit répondre
`marianne.finel@semise.fr`. Elle est propriétaire du compte : aucune autorisation à
demander ailleurs. L'authentification est persistante.

### 3.3 Localiser le dossier des bons

Un flux Power Automate appartenant à Marianne dépose chaque bon reçu par mail dans le
dossier **`Bons dintervention`** de son OneDrive professionnel.

**Prérequis à vérifier en premier : ce dossier doit être synchronisé localement sur le
Mac.** Sans cela, la tâche n'a aucun moyen de le lire.

```bash
find ~ -maxdepth 6 -type d -name "Bons dintervention" 2>/dev/null
ls ~/Library/CloudStorage/ 2>/dev/null
```

- **Un chemin s'affiche** : noter ce chemin, c'est `<dossier>` dans la suite.
- **Rien ne s'affiche** : la synchronisation OneDrive n'est pas active pour ce dossier.
  C'est un préalable, pas un détail. Demander à Marianne d'ouvrir OneDrive sur son Mac
  et de synchroniser ce dossier, puis recommencer. Ne pas chercher de contournement.

### 3.4 Obtenir la table des secteurs

Le bon d'intervention ne porte pas le gestionnaire de site : il se déduit de la
résidence, via le « Tableau des secteurs SEV ». Le fichier `secteurs.json` qui en
découle contient des coordonnées de personnels — il ne peut donc pas vivre dans le
dépôt public.

**Il est déjà généré**, dans le dépôt privé de Marianne
`MarianneFi/bons-intervention-source`, à `reference/secteurs.json`. Le récupérer :

```bash
git clone https://github.com/MarianneFi/bons-intervention-source.git /tmp/src
cp /tmp/src/reference/secteurs.json data/secteurs.json
rm -rf /tmp/src
```

Version en cours : établie à partir du tableau daté du **02.06.2026**.

**Si Marianne dispose d'une version plus récente du tableau Excel**, où qu'il se trouve
sur sa machine, le régénérer :

```bash
python3 scripts/secteurs_vers_json.py "<chemin du .xlsx>" > data/secteurs.json
```

et redéposer le résultat dans le dépôt privé pour la prochaine fois.

`data/` est ignoré par git dans ce dépôt-ci : `secteurs.json` ne doit jamais y être
versionné.

### 3.5 Vérifier la chaîne

```bash
npx wrangler kv key get --binding=BONS bons --remote | head -c 200
```

Un début de tableau JSON s'affiche : tout est prêt.

---

## 4. La procédure de mise à jour

Toutes les commandes se lancent **depuis le clone du dépôt** : c'est `wrangler.toml`
qui déclare le lien `BONS` vers le namespace KV. Ailleurs, elles échouent.

### Étape A — Lire l'état actuel

```bash
npx wrangler kv key get --binding=BONS bons --remote > /tmp/bons.json
```

Sortie JSON pure, sans bannière. **C'est la seule source de vérité** : ne jamais
reconstruire ce tableau de mémoire ni depuis une copie locale.

### Étape B — Repérer les bons non traités

Les fichiers du dossier OneDrive s'appellent `Bon d'intervention N°50.08.2026..docx`.
Le numéro est dans le nom.

**Attention, le numéro seul n'est pas une clé fiable** : deux bons du lot portent
`020.08.2026` (résidences Fabien et Stalingrad). Dé-dupliquer sur **`numero` + `site`**.

### Étape C — Extraire la couche mécanique

```bash
python3 scripts/extraire_bon.py "<dossier>/Bon d'intervention N°50.08.2026..docx"
```

Le script gère les **deux mises en page** qui coexistent dans les documents du
prestataire (tableau étiqueté, et étiquettes en ligne). Il rend un objet prérempli.

### Étape D — Rédiger

**C'est ici que se fait le vrai travail, et le script ne peut pas le faire.**

Mesuré sur les 39 bons dont le document et l'entrée en base se correspondent :

| Champ | Extraction fidèle | Nature du travail |
|---|---|---|
| `date` | 39/39 | mécanique |
| `statut` | 36/39 | mécanique, mais évolue après coup |
| `heure`, `site`, `astreinte` | 23-27/39 | mécanique + normalisation |
| `motif` | 13/39 | reformulation |
| `constat`, `remarque` | 0-2/39 | **réécriture intégrale** |

Le document contient le récit de l'agent à la première personne — « Sur place, je
constate que la porte sitex du logement 41 est restée grandement ouverte… ». La base
contient une synthèse condensée à la troisième personne — « Porte sitex du logement
vacant restée grandement ouverte… ».

Donc, à partir du squelette :

- **`motif`** : reformuler en libellé court et neutre. `PANNE D'ASCENSEUR « 10208562 »`
  devient `Panne d'ascenseur (appareil 10208562)`.
- **`constat`** : réécrire à la troisième personne, sans le « je » de l'agent, en
  gardant les faits, les sociétés citées et les numéros de dossier.
- **`remarque`** : la suite donnée et la clôture, également en synthèse.
- **`site`** : accentuer et normaliser. Le document écrit `MARTINIERE` et `Md. GENEVIEVE` ;
  la base attend `Martinière &middot; Mme Geneviève`, avec l'entité HTML.
- **`urgence`** : `"u1"`, `"u2"` ou `null`. Absent du document — à déduire de la gravité,
  ou laisser `null` en cas de doute.
- **`action`** : ce qui reste à faire côté Marianne, en une phrase. Vide s'il n'y a rien.
- **`gestionnaire`, `gestionnaireTel`, `gestionnaireEmail`** : depuis `data/secteurs.json`,
  via la résidence. Format : `Nom Prénom (secteur Ampère)`.

Ne jamais inventer. Un champ que le document ne donne pas reste une chaîne vide.

### Étape E — Fusionner

Ajouter les nouveaux bons à la fin du tableau. Un bon déjà présent n'est pas dupliqué.

**Le statut évolue après l'écriture du document.** Un bon rédigé « en cours » est
clôturé plus tard par Marianne, directement dans les données. Une réexécution ne doit
**jamais** écraser un statut plus avancé que celui du document.

### Étape F — Écrire

```bash
npx wrangler kv key put --binding=BONS bons --path=/tmp/bons.json --remote
```

**`--remote` est obligatoire dans les deux sens.** Sans lui, Wrangler travaille sur un
stockage local de développement : la commande réussit et la production ne change pas.

### Étape G — Vérifier et nettoyer

```bash
npx wrangler kv key get --binding=BONS bons --remote \
  | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{const b=JSON.parse(s);console.log(b.length+" bons, dernier : "+b[b.length-1].numero)})'

rm /tmp/bons.json
```

Le fichier temporaire contient des données personnelles : il ne reste pas sur le disque.

---

## 5. Le prompt de la tâche programmée

À coller tel quel dans la tâche Cowork, en remplaçant `<dossier>` par le chemin trouvé
en 3.3.

```
Tu es la tâche de mise à jour du tableau de bord des bons d'intervention
AAF La Providence. Chaque exécution démarre sans mémoire : ces
instructions sont complètes.

Travaille depuis le clone du dépôt bons-intervention-dashboard. Toutes les
commandes wrangler doivent être lancées depuis ce dossier.

Va jusqu'au bout en une seule traite. Ne demande aucune confirmation :
personne ne lit pendant l'exécution.

ÉTAPE 1 — LIRE L'ÉTAT ACTUEL
  npx wrangler kv key get --binding=BONS bons --remote > /tmp/bons.json
C'est la seule source de vérité. Si la commande échoue sur
l'authentification, arrête-toi et signale-le : il faut relancer
npx wrangler login, ce qui demande une présence humaine.

ÉTAPE 2 — REPÉRER LES NOUVEAUX BONS
Liste les .docx du dossier <dossier>. Le numéro est dans le nom du
fichier : « Bon d'intervention N°50.08.2026..docx » donne 50.08.2026.
Écarte les bons déjà présents, en comparant sur le COUPLE numero + site :
deux bons peuvent porter le même numéro pour des résidences différentes.

ÉTAPE 3 — EXTRAIRE
Pour chaque nouveau fichier :
  python3 scripts/extraire_bon.py "<chemin du .docx>"
Le script gère les deux mises en page du prestataire et rend un squelette.

ÉTAPE 4 — RÉDIGER
Le script ne fait que la couche mécanique. À toi de :
- reformuler motif en libellé court et neutre ;
- réécrire constat et remarque à la troisième personne, en synthèse, sans
  le « je » de l'agent, en gardant faits, sociétés et numéros de dossier ;
- normaliser site : « MARTINIERE » + « Md. GENEVIEVE » devient
  « Martinière &middot; Mme Geneviève », avec l'entité HTML et les accents ;
- renseigner urgence ("u1", "u2" ou null) ;
- rédiger action s'il reste quelque chose à faire, sinon chaîne vide ;
- renseigner gestionnaire, gestionnaireTel et gestionnaireEmail depuis
  data/secteurs.json, via la résidence.
N'invente rien. Un champ absent du document reste une chaîne vide.

ÉTAPE 5 — FUSIONNER
Ajoute les nouveaux bons à la fin. N'écrase JAMAIS un statut plus avancé
que celui du document : un bon peut avoir été clôturé après coup.

ÉTAPE 6 — ÉCRIRE
  npx wrangler kv key put --binding=BONS bons --path=/tmp/bons.json --remote
L'option --remote est obligatoire. Sans elle l'écriture part dans un
stockage local et la production ne change pas.

ÉTAPE 7 — VÉRIFIER ET NETTOYER
Relis KV, compte les bons, vérifie que le total a augmenté du nombre
attendu. Puis supprime /tmp/bons.json : il contient des données
personnelles.

ÉTAPE 8 — RENDRE COMPTE
Message court : nombre de bons avant, après, numéros ajoutés, numéros
mis à jour.

INTERDITS
- N'écris jamais de donnée de locataire dans le dépôt : il est public.
- Ne recrée jamais index.html à la racine. Le Worker sert
  public/index.html et ignore la racine : un fichier créé là serait
  invisible sur le tableau de bord tout en republiant les données.
- Ne fais ni commit ni push : une mise à jour de données ne passe plus
  par git.
- Ne modifie pas workers_dev dans wrangler.toml.

CONTRÔLE FINAL
Lance git status dans le clone. Aucun fichier contenant des bons ne doit
y apparaître. Si c'est le cas, ne committe rien et signale-le.
```

**Fréquence.** Power Automate dépose en continu, plusieurs fois par jour. La tâche peut
tourner à n'importe quel rythme : elle rattrape tout depuis la dernière fois. Le
tableau de bord met en avant les bons des sept derniers jours, donc un passage
quotidien a du sens ; un passage hebdomadaire laisserait filer des dossiers en attente.

---

## 6. Le schéma d'un bon

Quinze champs, tous des chaînes sauf `urgence` qui peut valoir `null`. Aucun n'est
optionnel : tous présents, éventuellement vides.

| Champ | Exemple | Note |
|---|---|---|
| `numero` | `"36.08.2026"` | ancien format à 3 chiffres (`"041"`) encore présent |
| `date` | `"2026-08-25"` | ISO strict ; pilote le filtre des 7 jours |
| `heure` | `"20h40 - 21h45"` | plage, ou heure d'entrée seule |
| `site` | `"Résidence &middot; M. Martin"` | résidence, entité HTML `&middot;`, occupant |
| `urgence` | `"u1"` · `"u2"` · `null` | absent du document |
| `statut` | `"attente"` · `"cloture"` | **sans accent** |
| `astreinte` | `"oui"` · `"non"` | cadre d'astreinte contacté |
| `astreinteDetail` | `"Nom Cadre, 21h15"` | vide si `astreinte` vaut `"non"` |
| `gestionnaire` | `"Nom Prénom (secteur Ampère)"` | depuis `secteurs.json` |
| `gestionnaireTel` | `"07 00 00 00 00"` | groupé par deux chiffres |
| `gestionnaireEmail` | `"secteurexemple@semise.fr"` | loge du secteur |
| `motif` | texte court | objet de l'appel |
| `constat` | texte long | ce qui a été relevé, réécrit en synthèse |
| `action` | texte long | attendu de Marianne ; vide si rien |
| `remarque` | texte long | suite donnée, clôture |

Le tableau de bord met en avant les bons non traités qui sont soit en attente, soit
vieux de moins de sept jours. Le marquage « traité » est propre au navigateur de
Marianne et ne touche pas aux données.

---

## 7. Diagnostic

| Symptôme | Cause | Correction |
|---|---|---|
| `index.html` introuvable à la racine | la tâche suit l'ancienne méthode | appliquer les étapes A à G |
| Commande réussie, dashboard inchangé | `--remote` oublié | relancer avec `--remote` |
| Erreur d'authentification Cloudflare | session Wrangler expirée | `npx wrangler login` (présence humaine requise) |
| `binding BONS not found` | commande lancée hors du clone | se placer dans le dossier du dépôt |
| `git status` montre un fichier avec des bons | la tâche a écrit dans le dépôt | ne rien committer, supprimer, corriger la tâche |
| Dashboard : « Session expirée » | jeton Access expiré côté navigateur | recharger et se reconnecter |
| Un bon attribué à « En cours de recrutement » | poste vacant dans le tableau des secteurs | laisser le gestionnaire vide et le signaler |

---

## 8. Fiche technique

| | |
|---|---|
| Tableau de bord | `https://bons-intervention-semise.marianne-finel.workers.dev` |
| Dépôt | `MarianneFi/bons-intervention-dashboard` (public) |
| Compte Cloudflare | `185ad6e4a1d4a950b1c248677784df0e` |
| Namespace KV | `BONS` · `da72f3e97ef14479a8ad724c72d45f66` |
| Clé | `bons` |
| Équipe Access | `tiny-river-e084.cloudflareaccess.com` |

**Contenu du dépôt**

- `public/index.html` — l'interface. Code seul, aucune donnée.
- `src/worker.js` — vérifie le jeton Access, sert KV sur `/api/bons`.
- `scripts/extraire_bon.py` — extraction mécanique d'un `.docx`.
- `scripts/secteurs_vers_json.py` — conversion du tableau des secteurs.
- `wrangler.toml` — configuration, contient le lien `BONS`.
- `data/` — ignoré par git. N'existe qu'en local.

Un push sur `main` déclenche un déploiement automatique via Cloudflare Workers Builds.
Utile pour modifier l'interface, sans effet sur les données.

---

## 9. Point resté ouvert

Les données ne sont plus publiées, mais elles restent lisibles dans les seize commits
antérieurs au 30 août 2026, le dépôt étant toujours public. La purge de l'historique
n'a pas été faite.

Cela ne change rien à la procédure ci-dessus, mais le sujet n'est pas clos.

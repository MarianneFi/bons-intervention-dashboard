# État des lieux — 30 août 2026

Ce qui a été fait, ce qui reste, et les pièges qui ont coûté du temps. À lire avant
toute reprise du dossier.

---

## Le problème d'origine

Le tableau de bord des bons d'intervention AAF La Providence était un unique fichier
`index.html`, à la racine d'un dépôt GitHub **public**, contenant les 49 bons **écrits
en dur** : 37 noms de locataires, téléphones des gestionnaires, descriptions de
situations individuelles. Trois surfaces exposaient ces données :

| Surface | État initial |
|---|---|
| Worker Cloudflare | protégé par Access |
| GitHub Pages | **ouvert**, servait les données complètes |
| Dépôt et son historique | **public** |

---

## Ce qui a été fait

### Architecture — terminé et vérifié

Les données sont sorties du code. Elles vivent dans **Cloudflare KV** et sont servies
par un Worker sur `/api/bons`, qui vérifie **intégralement** le jeton Cloudflare Access
— signature RSA contre le JWKS de l'équipe, émetteur, audience, expiration — avant de
répondre. Sans dépendance externe : WebCrypto suffit, `wrangler deploy` aussi.

Tests passés :

| Test | Résultat |
|---|---|
| `GET /` sert la page | 200, 0 donnée |
| `GET /api/bons` authentifié | 49 bons, identiques à la source |
| En-têtes | `no-store, private`, `nosniff`, `same-origin` |
| Sans jeton | 401 |
| Jeton bidon | 403 |
| Jeton forgé `alg: none` | 403 — algorithme refusé |
| En production, anonyme | 302 vers Access, 0 donnée exposée |
| En production, authentifié | 49 bons, KPI identiques, marquage « traité » OK |
| Session expirée | bandeau explicite, page non cassée |

### Diffusion coupée — terminé

GitHub Pages dépublié **et** source passée à `None` pour empêcher toute
reconstruction. L'URL renvoie 404, zéro nom exposé.

### Outillage — terminé

- `scripts/extraire_bon.py` — extrait un bon `.docx`. Gère les **deux mises en page**
  du prestataire (tableau étiqueté sur 18 fichiers, étiquettes en ligne sur 31).
- `scripts/secteurs_vers_json.py` — convertit le « Tableau des secteurs SEV » en index
  `résidence → secteur → gestionnaire, téléphone, loge`. 5 secteurs, 40 résidences.

### Documentation — terminé

- `docs/TACHE-PROGRAMMEE.md` — le mode d'emploi complet pour Claude Cowork chez Marianne.

---

## Ce qui reste ouvert

**La purge de l'historique.** Les 37 noms restent lisibles dans les seize commits
antérieurs au 30 août 2026, le dépôt étant toujours public. Reporté par décision de
Maxime. Le sujet n'est pas clos.

**La tâche programmée n'existe plus.** L'ancienne éditait `index.html` et n'est pas
consultable à distance : elle est attachée au Claude Cowork du poste de Marianne.
`docs/TACHE-PROGRAMMEE.md` permet d'en remonter une de zéro.

**Deux incohérences de données** à faire trancher par Marianne :
- le tableau des secteurs (02.06.2026) donne le poste de gestionnaire de **Stalingrad**
  vacant, alors que la base y place un gestionnaire que ce même tableau situe à
  **Centre Gare**. Les deux fiches se contredisent, l'une des deux est fausse ;
- deux bons portent le numéro `020.08.2026` (Fabien et Stalingrad).

**Le poste de Marianne est un PC Windows**, et le dossier OneDrive
`Bons dintervention` y est bien synchronisé localement — confirmé par Maxime. La
procédure est donc écrite en PowerShell.

**Une hypothèse levée par contournement** : l'emplacement du **tableau Excel des
secteurs** sur sa machine reste inconnu — il n'a été vu que dans le dossier de travail
local de Maxime. `secteurs.json` étant déjà généré et déposé dans le dépôt privé, la
tâche le récupère là et n'a pas besoin du tableur.

**Accès à retirer en fin de mission** : `maxtaillebois` est collaborateur des deux
dépôts.

---

## Les pièges, et ce qu'ils ont coûté

### Access protège bien `*.workers.dev`

**Ce que je croyais :** Access ne couvre pas les URL `workers.dev`, il faut donc
`workers_dev = false`.
**La réalité :** l'application Access `bons-intervention-semise` protège cet hostname,
qui est l'unique adresse du service. Vérifié : une requête anonyme est redirigée vers
l'écran de connexion.
**Conséquence :** mon premier commit coupait cette route et aurait mis le tableau de
bord hors ligne. Corrigé avant tout déploiement.

### Le connecteur HTTP de Power Automate est Premium — piste abandonnée

**L'idée :** faire pousser les `.docx` par Power Automate dans un dépôt privé, pour
qu'une routine Claude Code dans le cloud les lise sans qu'aucun identifiant Microsoft
ne sorte du tenant SEMISE. Techniquement sain.
**Le mur :** appeler une URL arbitraire depuis Power Automate exige le connecteur HTTP
générique, qui **nécessite une licence Power Automate Premium**. Marianne ne l'a pas.
**Ce que ça a coûté :** l'action a été construite entièrement, puis le flux enregistré
s'est retrouvé **bloqué** — et donc le dépôt OneDrive des bons interrompu. L'action a
été retirée et le flux restauré (« Votre flux est prêt à l'emploi »). Un jeton GitHub
avait été créé pour rien et doit être révoqué.
**La leçon :** vérifier la licence d'un connecteur **avant** de construire quoi que ce
soit dessus. J'avais vu le marqueur Premium et je l'ai signalé après coup au lieu de
m'arrêter.

**Ne pas relancer cette piste** sans décision explicite sur la licence.

### L'extraction ne remplace pas la rédaction

Mesuré sur les 39 bons appariés : `date` sort juste 39/39, mais `constat` 0/39 et
`remarque` 2/39. La base ne contient pas le texte du document — elle en contient une
**synthèse réécrite** à la troisième personne. Le script prépare, Claude rédige.
C'est structurant pour toute automatisation future.

### Autres pièges relevés

- **`--remote` sur les commandes KV.** Sans lui, Wrangler écrit dans un stockage local
  de développement : la commande réussit et la production ne bouge pas.
- **Le `+` de Power Automate.** Deux `+` se ressemblent, l'un place l'action dans la
  boucle, l'autre après. Seule la vue Code (`runAfter`) permet de vérifier.
- **L'éditeur d'expressions signale à tort** un problème sur la syntaxe `?['Name']`.
  Faux positif : la même expression est acceptée et figure correctement dans le code.
- **Le numéro de bon n'est pas unique.** Dé-dupliquer sur `numero` + `site`.
- **Le statut évolue** après l'écriture du document : ne jamais l'écraser à la baisse.

---

## La chaîne, telle qu'elle fonctionne aujourd'hui

```
Prestataire AAF La Providence
   │  mail avec le bon en .docx (rondier@lplaprovidence.com)
   ▼
Power Automate  (flux de Marianne, tenant SEMISE)
   │  dépose la pièce jointe
   ▼
OneDrive « Bons dintervention »  ──sync──>  PC Windows de Marianne
                                               │
                                               ▼
                                    Claude Cowork  (à remonter)
                                    extrait, rédige, fusionne
                                               │
                                               ▼
                                      Cloudflare KV
                                               │
                                               ▼
                          Worker + Access ──> tableau de bord
```

---

## Fiche technique

| | |
|---|---|
| Tableau de bord | `https://bons-intervention-semise.marianne-finel.workers.dev` |
| Dépôt public (code) | `MarianneFi/bons-intervention-dashboard` |
| Dépôt privé (source) | `MarianneFi/bons-intervention-source` — porte `reference/secteurs.json`, seul usage restant après l'abandon de la piste cloud |
| Compte Cloudflare | `185ad6e4a1d4a950b1c248677784df0e` |
| Namespace KV | `BONS` · `da72f3e97ef14479a8ad724c72d45f66` |
| Équipe Access | `tiny-river-e084.cloudflareaccess.com` |
| Flux Power Automate | « Enregistrer les pièces jointes Office 365 dans le dossier OneDrive Entreprise spécifié » |
| Tenant SEMISE | `db5f6c24-38c3-4abd-8b27-039456cf93ef` |

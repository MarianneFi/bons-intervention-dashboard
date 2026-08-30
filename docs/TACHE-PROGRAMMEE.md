# Monter la tâche programmée de mise à jour des bons

**Pour qui :** Claude, sur le poste de Marianne Finel (Claude Cowork).
**État :** à jour au 30 août 2026.
**Ce document se suffit à lui-même.** Aucune connaissance de l'ancienne tâche n'est
nécessaire ; l'architecture a changé et l'ancienne méthode ne fonctionne plus.

---

## 1. Ce qu'il faut comprendre avant tout

Ce dépôt alimente le tableau de bord des bons d'intervention AAF La Providence.

Jusqu'au 29 août 2026, les 49 bons étaient écrits **en dur** dans `index.html`, à la
racine d'un dépôt GitHub **public**. Trente-sept noms de locataires, les téléphones
des gestionnaires et des descriptions de situations individuelles étaient donc
lisibles par n'importe qui. C'était une fuite de données personnelles.

Le 30 août 2026, les données ont été sorties du code :

| | Avant | Maintenant |
|---|---|---|
| Où vivent les données | dans `index.html`, versionné | dans **Cloudflare KV** |
| Qui peut les lire | tout le monde | seulement un utilisateur authentifié par Cloudflare Access |
| Comment on les met à jour | éditer le HTML, commit, push, attendre le build | lire KV, modifier, réécrire KV |
| Le dépôt contient | le code **et** les données | le code seul |

**La mise à jour ne passe plus par git.** Ni commit, ni push, ni déploiement. Le
Worker relit KV à chaque visite : une écriture dans KV est visible immédiatement.

---

## 2. Les trois règles absolues

**1. Aucune donnée de locataire ne doit entrer dans ce dépôt.**
Ni dans `public/index.html`, ni dans un fichier créé à la racine, ni dans un message
de commit. Le dépôt est public.

**2. Ne jamais recréer `index.html` à la racine.**
C'est le piège principal. Le Worker sert `public/index.html` et ignore la racine. Un
fichier recréé là serait **invisible sur le tableau de bord tout en republiant les
données**. Tout semblerait fonctionner — le fichier s'écrit, le commit passe, le build
Cloudflare réussit — alors que le dashboard ne bouge pas et que la fuite est rouverte.
C'est le seul scénario réellement dangereux, parce qu'il est silencieux.

**3. Ne pas toucher à `workers_dev` dans `wrangler.toml`.**
Cloudflare Access protège l'hostname `*.workers.dev` lui-même, qui est l'unique
adresse du service. Passer `workers_dev = false` mettrait le tableau de bord hors
ligne.

---

## 3. Préparer le poste (une seule fois)

### 3.1 Cloner le dépôt

```bash
git clone https://github.com/MarianneFi/bons-intervention-dashboard.git
cd bons-intervention-dashboard
npm install
```

`npm install` installe Wrangler en local. Node.js est requis.

### 3.2 Authentifier Wrangler auprès de Cloudflare

```bash
npx wrangler login
npx wrangler whoami
```

Le navigateur s'ouvre, Marianne approuve. `whoami` doit répondre
`marianne.finel@semise.fr` — elle est propriétaire du compte Cloudflare, il n'y a
aucune autorisation à demander ailleurs.

Cette authentification est persistante : elle n'est pas à refaire à chaque exécution.
Si une exécution échoue avec une erreur d'authentification, c'est la seule commande à
relancer.

### 3.3 Vérifier que la chaîne répond

```bash
npx wrangler kv key get --binding=BONS bons --remote | head -c 200
```

Doit afficher le début d'un tableau JSON. Si oui, tout est prêt.

---

## 4. La procédure de mise à jour

Les commandes se lancent **depuis le clone du dépôt** : c'est `wrangler.toml` qui
déclare le lien `BONS` vers le bon namespace KV. Lancées ailleurs, elles échouent.

### Étape A — Lire l'état actuel

```bash
npx wrangler kv key get --binding=BONS bons --remote > /tmp/bons.json
```

La sortie standard est du JSON pur, sans bannière ni bruit : elle se redirige
directement dans un fichier. Le résultat est un tableau JSON de tous les bons connus.

**C'est la seule source de vérité.** Ne jamais reconstruire ce tableau de mémoire ni
depuis une copie locale : toujours partir de ce que KV contient à l'instant T.

### Étape B — Ajouter les nouveaux bons

Ajouter les objets à la fin du tableau, au schéma décrit en section 6.

- Un bon déjà présent se reconnaît à son `numero`. **Ne pas le dupliquer** : le mettre
  à jour sur place si son statut a évolué.
- Les champs inconnus se remplissent avec une chaîne vide `""`, jamais `null` — sauf
  `urgence`, qui vaut bien `null` en l'absence d'urgence déclarée.

### Étape C — Réécrire dans KV

```bash
npx wrangler kv key put --binding=BONS bons --path=/tmp/bons.json --remote
```

**L'option `--remote` est indispensable dans les deux sens.** Sans elle, Wrangler
travaille sur un stockage local de développement : la commande réussit, et le tableau
de bord réel ne change pas.

### Étape D — Vérifier, puis effacer le fichier de travail

```bash
npx wrangler kv key get --binding=BONS bons --remote \
  | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{const b=JSON.parse(s);console.log(b.length+" bons, dernier : "+b[b.length-1].numero)})'

rm /tmp/bons.json
```

Le fichier temporaire contient des données personnelles : il ne reste pas sur le
disque.

---

## 5. Monter la tâche programmée

### 5.1 Ce que la tâche doit faire

```
1. Collecter les nouveaux bons d'intervention          <- partie métier, à compléter
2. Lire l'état actuel depuis KV                        <- étape A
3. Fusionner : ajouter les nouveaux, mettre à jour les existants
4. Réécrire dans KV                                    <- étape C
5. Vérifier et nettoyer                                <- étape D
```

Seule l'étape 1 dépend de l'organisation de Marianne. Les étapes 2 à 5 sont
mécaniques et figées.

### 5.2 Récupérer l'étape de collecte

L'ancienne tâche programmée contenait déjà cette logique : d'où viennent les bons
(boîte mail, fichier déposé, saisie manuelle), à quelle fréquence, comment ils sont
mis en forme. **Cette partie-là se conserve intégralement.**

Si l'ancienne tâche n'est plus consultable, demander directement à Marianne :

- D'où arrivent les bons d'intervention ? (mail de l'astreinte, export, autre)
- À quelle fréquence veut-elle la mise à jour ?
- Y a-t-il un mail récapitulatif à envoyer après coup ?

Ne pas deviner. Une collecte inventée produirait des données fausses dans un tableau
de bord d'exploitation.

### 5.3 Modèle de prompt pour la tâche

À adapter en remplaçant le bloc `ÉTAPE 1`.

```
Tu es la tâche de mise à jour du tableau de bord des bons d'intervention
AAF La Providence. Chaque exécution démarre sans mémoire : ces instructions
sont complètes.

Travaille depuis le clone du dépôt bons-intervention-dashboard. Toutes les
commandes wrangler doivent être lancées depuis ce dossier.

Va jusqu'au bout en une seule traite. Ne demande aucune confirmation :
personne ne lit pendant l'exécution.

ÉTAPE 1 — COLLECTER
[À COMPLÉTER : d'où viennent les nouveaux bons et comment les extraire.
Produire une liste d'objets au schéma décrit dans docs/TACHE-PROGRAMMEE.md,
section 6.]

ÉTAPE 2 — LIRE L'ÉTAT ACTUEL
  npx wrangler kv key get --binding=BONS bons --remote > /tmp/bons.json
C'est la seule source de vérité. Ne reconstruis jamais ce tableau autrement.
Si la commande échoue sur l'authentification, arrête-toi et signale-le :
il faut relancer npx wrangler login, ce qui demande une présence humaine.

ÉTAPE 3 — FUSIONNER
Ajoute les nouveaux bons à la fin du tableau. Un bon dont le numero existe
déjà n'est pas ajouté : mets-le à jour sur place si son statut a changé.
Respecte le schéma à la lettre (section 6 du document) : statut vaut
"attente" ou "cloture" sans accent, date au format AAAA-MM-JJ, urgence vaut
"u1", "u2" ou null, tous les autres champs sont des chaînes présentes même
vides.

ÉTAPE 4 — ÉCRIRE
  npx wrangler kv key put --binding=BONS bons --path=/tmp/bons.json --remote
L'option --remote est obligatoire. Sans elle l'écriture part dans un
stockage local et la production ne change pas.

ÉTAPE 5 — VÉRIFIER ET NETTOYER
Relis KV, compte les bons, vérifie que le compte a bien augmenté du nombre
attendu. Puis supprime /tmp/bons.json : il contient des données
personnelles.

ÉTAPE 6 — RENDRE COMPTE
Termine par un message court : nombre de bons avant, nombre après, numéros
ajoutés, numéros mis à jour.

INTERDITS
- N'écris jamais de donnée de locataire dans le dépôt : il est public.
- Ne recrée jamais index.html à la racine. Le Worker sert public/index.html
  et ignore la racine : un fichier créé là serait invisible sur le tableau
  de bord tout en republiant les données.
- Ne fais ni commit ni push : une mise à jour de données ne passe plus par
  git.
- Ne modifie pas workers_dev dans wrangler.toml.

CONTRÔLE FINAL
Lance git status dans le clone. Aucun fichier contenant des bons ne doit y
apparaître. Si c'est le cas, ne committe rien et signale-le.
```

### 5.4 Fréquence

L'ancienne chaîne produisait des lots (voir le commit « Rattrapage bons n°046.07.2026
à 36.08.2026 »), ce qui suggère un rythme irrégulier. À caler avec Marianne. Le
tableau de bord met en avant les bons des sept derniers jours : une mise à jour
quotidienne ou tous les deux jours a du sens, une mise à jour hebdomadaire laisserait
passer des dossiers en attente.

---

## 6. Le schéma d'un bon

Quinze champs. Tous des chaînes de caractères sauf `urgence`, qui peut valoir `null`.
Aucun champ n'est optionnel : ils sont tous présents, éventuellement vides.

| Champ | Exemple | Note |
|---|---|---|
| `numero` | `"36.08.2026"` | identifiant unique ; ancien format à 3 chiffres (`"041"`) encore présent |
| `date` | `"2026-08-25"` | ISO strict ; sert au filtre des 7 derniers jours |
| `heure` | `"20h40 - 21h45"` | libre, souvent une plage |
| `site` | `"Résidence Exemple &middot; M. Martin"` | résidence, l'entité HTML `&middot;`, puis l'occupant |
| `urgence` | `"u1"` · `"u2"` · `null` | `null` quand aucune urgence n'est déclarée |
| `statut` | `"attente"` · `"cloture"` | **sans accent** ; pilote les compteurs |
| `astreinte` | `"oui"` · `"non"` | le cadre d'astreinte a-t-il été contacté |
| `astreinteDetail` | `"Nom Cadre, 21h15"` | vide si `astreinte` vaut `"non"` |
| `gestionnaire` | `"Nom Gestionnaire (secteur Ampère)"` | le secteur entre parenthèses est repris sur le bouton de relance |
| `gestionnaireTel` | `"07 00 00 00 00"` | groupé par deux chiffres |
| `gestionnaireEmail` | `"secteurexemple@semise.fr"` | adresse de la loge, destinataire de la relance |
| `motif` | texte court | l'objet de l'appel, ex. « WC bouché » |
| `constat` | texte long | ce qui a été relevé sur place |
| `action` | texte long | ce qui est attendu de Marianne ; vide si rien à faire |
| `remarque` | texte long | suite donnée, clôture |

Exemple complet :

```json
{
  "numero": "37.08.2026",
  "date": "2026-08-28",
  "heure": "18h10 - 19h05",
  "site": "Résidence Exemple &middot; Mme Dupont",
  "urgence": "u2",
  "statut": "attente",
  "astreinte": "oui",
  "astreinteDetail": "Nom Cadre, 18h20",
  "gestionnaire": "Nom Gestionnaire (secteur Ampère)",
  "gestionnaireTel": "07 00 00 00 00",
  "gestionnaireEmail": "secteurexemple@semise.fr",
  "motif": "Fuite sous évier",
  "constat": "Fuite au niveau du siphon, bac à vaisselle placé en attente.",
  "action": "relancer CIG lundi si aucune intervention",
  "remarque": ""
}
```

**Comment le tableau de bord s'en sert.** Sont mis en avant les bons non traités qui
sont soit en attente, soit vieux de moins de sept jours ; les autres basculent dans
l'historique. Le marquage « traité » est propre au navigateur de Marianne et ne touche
pas aux données : un bon marqué traité reste dans KV.

---

## 7. Diagnostic

| Symptôme | Cause | Que faire |
|---|---|---|
| `index.html` introuvable à la racine | la tâche suit encore l'ancienne méthode | remplacer par les étapes A à D |
| La commande réussit mais le dashboard ne change pas | `--remote` oublié | relancer avec `--remote` |
| Erreur d'authentification Cloudflare | session Wrangler expirée | `npx wrangler login` — nécessite une présence humaine |
| `binding BONS not found` | commande lancée hors du clone | se placer dans le dossier du dépôt |
| `git status` montre un fichier avec des bons | la tâche a écrit dans le dépôt | ne rien committer, supprimer le fichier, corriger la tâche |
| Le dashboard affiche « Session expirée » | jeton Access expiré côté navigateur | recharger la page et se reconnecter |

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
- `wrangler.toml` — configuration, contient le lien `BONS`.
- `data/` — ignoré par git, n'existe que sur le poste de Maxime Taillebois.

Un push sur `main` déclenche un déploiement automatique via Cloudflare Workers Builds.
C'est utile pour modifier l'interface, et sans effet sur les données.

---

## 9. Point resté ouvert

Les données ne sont plus publiées, mais elles restent lisibles dans les seize commits
antérieurs au 30 août 2026, le dépôt étant toujours public. La purge de l'historique a
été volontairement reportée par Maxime Taillebois.

Cela ne change rien à la procédure ci-dessus. Mais toute personne consultant le dépôt
peut encore lire les anciennes données : ne pas considérer le sujet comme clos.

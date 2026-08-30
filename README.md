# Tableau de bord des bons d'intervention — AAF La Providence

Tableau de bord de suivi des bons d'intervention, déployé sur Cloudflare Workers
derrière Cloudflare Access.

## Règle de confidentialité

**Ce dépôt ne doit contenir aucune donnée de locataire.**

Les bons d'intervention comportent des noms, des adresses de résidence et des
descriptions de situations individuelles : ce sont des données personnelles. Elles
sont stockées dans Cloudflare KV et servies par le Worker sur `/api/bons`,
uniquement à un utilisateur authentifié par Access.

Le fichier `data/bons.json` est ignoré par git (`.gitignore`). Ne jamais le forcer
dans un commit, et ne jamais réintroduire de données dans `public/index.html`.

## Organisation

| Chemin             | Rôle                                                |
| ------------------ | --------------------------------------------------- |
| `public/index.html`| L'interface. Code uniquement, publiable.             |
| `src/worker.js`    | Vérifie le jeton Access, sert les données depuis KV. |
| `data/bons.json`   | Les données. **Non versionné.**                      |
| `wrangler.toml`    | Configuration du Worker.                             |

## Configuration initiale

1. Créer le namespace KV et reporter l'`id` dans `wrangler.toml` :

   ```
   npx wrangler kv namespace create BONS
   ```

2. Les variables Access sont déjà renseignées dans `wrangler.toml`
   (`ACCESS_TEAM_DOMAIN`, `ACCESS_AUD`). Elles ne changent que si l'application
   Access est recréée.

3. Charger les données :

   ```
   npm run seed
   ```

4. Déployer :

   ```
   npm run deploy
   ```

## Tâche programmée

La mise à jour automatique est décrite en détail dans
[docs/TACHE-PROGRAMMEE.md](docs/TACHE-PROGRAMMEE.md) : préparation du poste, procédure
complète, modèle de prompt pour la tâche, schéma des données et diagnostic.

## Mettre à jour les bons

Modifier `data/bons.json` en local, puis `npm run seed`. Aucun déploiement
n'est nécessaire : le Worker relit KV à chaque requête.

## Développement local

```
npm run dev
```

`DEV_MODE` court-circuite la vérification du jeton, et n'est positionné que par
ce script. La configuration déployée ne le contient pas : en production, un
défaut de configuration provoque un refus, jamais un accès ouvert.

## Points de vigilance

- **Le service n'a qu'un seul hostname** : `bons-intervention-semise.marianne-finel.workers.dev`,
  protégé par l'application Access `bons-intervention-semise`. Contrairement à ce
  qui a longtemps été vrai chez Cloudflare, Access s'applique bien ici à une URL
  `workers.dev` — vérifié : une requête anonyme est redirigée vers l'écran de
  connexion. `workers_dev = true` doit donc le rester tant qu'aucun domaine
  personnalisé n'a pris le relais.
- **Si un domaine personnalisé est ajouté**, il lui faut sa propre application
  Access. Une route non couverte par une application sert le Worker sans
  authentification — et le Worker refuserait alors les requêtes (401), ce qui
  rendra le problème visible plutôt que silencieux.
- **GitHub Pages doit rester désactivé** sur ce dépôt. Une publication Pages sert
  les fichiers sans passer par Access, ce qui a été la cause de la fuite initiale.
- `ACCESS_AUD` et `ACCESS_TEAM_DOMAIN` ne sont pas des secrets : ils identifient
  l'application. La sécurité repose sur la vérification de la signature du jeton,
  pas sur leur confidentialité.

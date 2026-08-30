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

2. Renseigner dans `wrangler.toml` les deux variables Access, lues dans
   Zero Trust > Access > Applications > l'application > Overview :
   - `ACCESS_TEAM_DOMAIN` — le domaine d'équipe, ex. `semise.cloudflareaccess.com`
   - `ACCESS_AUD` — l'Application Audience (AUD) Tag

3. Charger les données :

   ```
   npm run seed
   ```

4. Déployer :

   ```
   npm run deploy
   ```

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

- `workers_dev = false` doit le rester. Access protège le domaine personnalisé,
  pas `*.workers.dev` : rouvrir cette route contournerait l'authentification.
- GitHub Pages doit rester désactivé sur ce dépôt. Une publication Pages sert les
  fichiers sans passer par Access.

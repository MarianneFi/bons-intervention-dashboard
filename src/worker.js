/**
 * Tableau de bord des bons d'intervention - AAF La Providence (SEMISE)
 *
 * Ce Worker sert les données nominatives des locataires. Elles ne sont
 * PAS dans le dépôt : elles vivent dans le namespace KV lié à `BONS`.
 *
 * Toute requête sur /api/bons doit porter un jeton Cloudflare Access
 * valide. Le jeton est vérifié intégralement (signature, émetteur,
 * audience, expiration) et non pas seulement constaté : la simple
 * présence d'un en-tête est falsifiable si le Worker devient joignable
 * autrement que par le domaine protégé.
 */

const JWKS_TTL_MS = 60 * 60 * 1000; // 1 h
let jwksCache = { url: null, keys: null, fetchedAt: 0 };

const b64urlToBytes = (s) => {
  const b64 = s.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(s.length / 4) * 4, "=");
  return Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
};
const b64urlToJson = (s) => JSON.parse(new TextDecoder().decode(b64urlToBytes(s)));

async function getKeys(teamDomain) {
  const url = `https://${teamDomain}/cdn-cgi/access/certs`;
  const frais = jwksCache.keys && jwksCache.url === url && Date.now() - jwksCache.fetchedAt < JWKS_TTL_MS;
  if (frais) return jwksCache.keys;

  const r = await fetch(url, { cf: { cacheTtl: 3600 } });
  if (!r.ok) throw new Error(`JWKS indisponible (${r.status})`);
  const { keys } = await r.json();
  jwksCache = { url, keys, fetchedAt: Date.now() };
  return keys;
}

/** Renvoie le payload si le jeton est valide, sinon lève une erreur. */
async function verifierJeton(token, teamDomain, aud) {
  const parts = token.split(".");
  if (parts.length !== 3) throw new Error("jeton malformé");
  const [h, p, sig] = parts;

  const header = b64urlToJson(h);
  if (header.alg !== "RS256") throw new Error(`algorithme refusé : ${header.alg}`);

  const jwk = (await getKeys(teamDomain)).find((k) => k.kid === header.kid);
  if (!jwk) throw new Error("clé de signature inconnue");

  const key = await crypto.subtle.importKey(
    "jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]
  );
  const ok = await crypto.subtle.verify(
    "RSASSA-PKCS1-v1_5", key, b64urlToBytes(sig), new TextEncoder().encode(`${h}.${p}`)
  );
  if (!ok) throw new Error("signature invalide");

  const payload = b64urlToJson(p);
  const now = Math.floor(Date.now() / 1000);
  if (payload.exp && payload.exp < now) throw new Error("jeton expiré");
  if (payload.nbf && payload.nbf > now + 60) throw new Error("jeton pas encore valide");
  if (payload.iss !== `https://${teamDomain}`) throw new Error("émetteur inattendu");

  const auds = Array.isArray(payload.aud) ? payload.aud : [payload.aud];
  if (!auds.includes(aud)) throw new Error("audience inattendue");

  return payload;
}

const json = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      // Données personnelles : jamais de mise en cache, ni proxy ni navigateur.
      "cache-control": "no-store, private",
      "x-content-type-options": "nosniff",
      "referrer-policy": "same-origin",
    },
  });

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname !== "/api/bons") return json({ erreur: "Ressource inconnue" }, 404);
    if (request.method !== "GET") return json({ erreur: "Méthode non autorisée" }, 405);

    // DEV_MODE n'est défini que pour les tests locaux (wrangler dev --var).
    // Absent de la configuration déployée : la production échoue fermée.
    const dev = env.DEV_MODE === "true";

    if (!dev) {
      const { ACCESS_TEAM_DOMAIN: team, ACCESS_AUD: aud } = env;
      if (!team || !aud) {
        console.error("ACCESS_TEAM_DOMAIN ou ACCESS_AUD non configuré : accès refusé.");
        return json({ erreur: "Service mal configuré" }, 500);
      }
      const token =
        request.headers.get("Cf-Access-Jwt-Assertion") ||
        (request.headers.get("Cookie") || "").match(/CF_Authorization=([^;]+)/)?.[1];

      if (!token) return json({ erreur: "Authentification requise" }, 401);
      try {
        await verifierJeton(token, team, aud);
      } catch (e) {
        console.warn("Jeton Access rejeté :", e.message);
        return json({ erreur: "Authentification invalide" }, 403);
      }
    }

    const bons = await env.BONS.get("bons", "json");
    if (!bons) {
      console.error("Clé KV 'bons' absente du namespace.");
      return json({ erreur: "Données indisponibles" }, 503);
    }
    return json(bons);
  },
};

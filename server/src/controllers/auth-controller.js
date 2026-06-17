import { generators } from "openid-client";
import { config } from "../config.js";
import { query, withTransaction } from "../db/pool.js";
import { getOidcClient, createPkceState } from "../auth/oidc-client.js";
import { ApiError } from "../middlewares/error-handler.js";

const userFields = "id, full_name, email, role, class_name, is_active, created_at";

function publicUser(user) {
  if (!user) return null;
  return {
    id: user.id,
    full_name: user.full_name,
    email: user.email,
    role: user.role,
    class_name: user.class_name,
    is_active: user.is_active
  };
}

async function findActiveUserByIdOrEmail({ userId, email }) {
  const values = [];
  const filters = ["is_active = true"];

  if (userId) {
    values.push(Number(userId));
    filters.push(`id = $${values.length}`);
  }

  if (email) {
    values.push(String(email).toLowerCase());
    filters.push(`lower(email) = $${values.length}`);
  }

  const where = userId || email ? filters.join(" AND ") : "is_active = true";
  const { rows } = await query(
    `SELECT ${userFields}
     FROM users
     WHERE ${where}
     ORDER BY id
     LIMIT 1`,
    values
  );

  return rows[0] || null;
}

async function findOrCreateOidcUser(profile) {
  const email = profile.email || profile.preferred_username || profile.upn;
  if (!email) {
    throw new ApiError(401, "oidc_email_missing", "Le profil Entra ID ne contient pas d'email utilisable.");
  }

  return withTransaction(async (client) => {
    const existing = await client.query(`SELECT ${userFields} FROM users WHERE lower(email) = lower($1) LIMIT 1`, [email]);
    if (existing.rowCount > 0) return existing.rows[0];

    const fullName = profile.name || email.split("@")[0];
    const inserted = await client.query(
      `INSERT INTO users (full_name, email, role, class_name, is_active)
       VALUES ($1, $2, 'student', NULL, true)
       RETURNING ${userFields}`,
      [fullName, email.toLowerCase()]
    );

    await client.query(
      `INSERT INTO audit_events (actor_id, event_type, severity, event_message)
       VALUES ($1, 'user_created_from_oidc', 'info', $2)`,
      [inserted.rows[0].id, `Utilisateur ${inserted.rows[0].email} cree depuis Entra ID.`]
    );

    return inserted.rows[0];
  });
}

function openSession(req, user) {
  req.session.userId = user.id;
  req.session.authMode = config.auth.mode;
  req.session.loginAt = new Date().toISOString();
}

function authResponse(user) {
  return {
    data: {
      user: publicUser(user),
      auth: {
        mode: config.auth.mode,
        authenticated: Boolean(user)
      }
    }
  };
}

export async function login(req, res) {
  if (config.auth.mode === "mock") {
    const user = await findActiveUserByIdOrEmail({
      userId: req.query.user_id || req.body?.user_id,
      email: req.query.email || req.body?.email
    });

    if (!user) {
      throw new ApiError(404, "mock_user_not_found", "Aucun utilisateur mock actif trouve.");
    }

    openSession(req, user);
    res.json(authResponse(user));
    return;
  }

  const client = await getOidcClient();
  const pkce = createPkceState();
  req.session.oidc = pkce;

  const authorizationUrl = client.authorizationUrl({
    scope: config.auth.scopes,
    code_challenge: generators.codeChallenge(pkce.codeVerifier),
    code_challenge_method: "S256",
    state: pkce.state,
    nonce: pkce.nonce
  });

  res.redirect(authorizationUrl);
}

export async function callback(req, res) {
  if (config.auth.mode === "mock") {
    res.json(authResponse(req.user || null));
    return;
  }

  const oidcSession = req.session.oidc;
  if (!oidcSession) {
    throw new ApiError(400, "oidc_session_missing", "Session OIDC introuvable. Relancer la connexion.");
  }

  const client = await getOidcClient();
  const params = client.callbackParams(req);
  const tokenSet = await client.callback(config.auth.azureRedirectUri, params, {
    code_verifier: oidcSession.codeVerifier,
    state: oidcSession.state,
    nonce: oidcSession.nonce
  });

  const claims = tokenSet.claims();
  const userInfo = tokenSet.access_token ? await client.userinfo(tokenSet.access_token) : {};
  const user = await findOrCreateOidcUser({ ...userInfo, ...claims });

  if (!user.is_active) {
    throw new ApiError(403, "user_disabled", "Compte utilisateur desactive.");
  }

  openSession(req, user);
  delete req.session.oidc;
  res.json(authResponse(user));
}

export async function logout(req, res) {
  await new Promise((resolve, reject) => {
    req.session.destroy((error) => {
      if (error) reject(new ApiError(500, "logout_failed", "Impossible de fermer la session."));
      else resolve();
    });
  });
  res.clearCookie(config.session.name);
  res.json({ data: { authenticated: false } });
}

export async function me(req, res) {
  res.json(authResponse(req.user || null));
}

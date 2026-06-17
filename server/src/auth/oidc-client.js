import { Issuer, generators } from "openid-client";
import { config } from "../config.js";

let cachedClient = null;

export async function getOidcClient() {
  if (cachedClient) return cachedClient;

  if (!config.auth.azureTenantId || !config.auth.azureClientId || !config.auth.azureRedirectUri) {
    throw new Error("Configuration Entra ID incomplete: AZURE_TENANT_ID, AZURE_CLIENT_ID et AZURE_REDIRECT_URI sont requis.");
  }

  const issuer = await Issuer.discover(`https://login.microsoftonline.com/${config.auth.azureTenantId}/v2.0`);
  cachedClient = new issuer.Client({
    client_id: config.auth.azureClientId,
    client_secret: config.auth.azureClientSecret || undefined,
    redirect_uris: [config.auth.azureRedirectUri],
    response_types: ["code"]
  });

  return cachedClient;
}

export function createPkceState() {
  return {
    codeVerifier: generators.codeVerifier(),
    state: generators.state(),
    nonce: generators.nonce()
  };
}


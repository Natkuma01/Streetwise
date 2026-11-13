export const CONSENT_KEY = "streetwise_rules_accepted_v1";
export const CONSENT_VERSION = 1;

export function hasAcceptedRules(storage = window.localStorage) {
  try {
    const consent = JSON.parse(storage.getItem(CONSENT_KEY));
    return consent?.version === CONSENT_VERSION && Boolean(consent.acceptedAt);
  } catch {
    return false;
  }
}

export function acceptRules(storage = window.localStorage, now = new Date()) {
  storage.setItem(
    CONSENT_KEY,
    JSON.stringify({ acceptedAt: now.toISOString(), version: CONSENT_VERSION }),
  );
}

export function clearRulesAcceptance(storage = window.localStorage) {
  try {
    storage.removeItem(CONSENT_KEY);
  } catch {
    // Storage may already be unavailable or empty.
  }
}

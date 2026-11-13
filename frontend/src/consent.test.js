import assert from "node:assert/strict";
import test from "node:test";

import {
  CONSENT_KEY,
  acceptRules,
  clearRulesAcceptance,
  hasAcceptedRules,
} from "./consent.js";

function createStorage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    removeItem: (key) => values.delete(key),
    setItem: (key, value) => values.set(key, value),
  };
}

test("a first-time visitor has not accepted the rules", () => {
  assert.equal(hasAcceptedRules(createStorage()), false);
});

test("acceptance is remembered in browser storage", () => {
  const storage = createStorage();
  acceptRules(storage, new Date("2026-11-12T18:00:00.000Z"));

  assert.equal(hasAcceptedRules(storage), true);
  assert.deepEqual(JSON.parse(storage.getItem(CONSENT_KEY)), {
    acceptedAt: "2026-11-12T18:00:00.000Z",
    version: 1,
  });
});

test("old or malformed acceptance does not bypass the rules", () => {
  const storage = createStorage();
  storage.setItem(CONSENT_KEY, "not-json");
  assert.equal(hasAcceptedRules(storage), false);

  storage.setItem(CONSENT_KEY, JSON.stringify({ acceptedAt: "today", version: 0 }));
  assert.equal(hasAcceptedRules(storage), false);
});

test("disagreeing clears an earlier acceptance", () => {
  const storage = createStorage();
  acceptRules(storage);
  clearRulesAcceptance(storage);
  assert.equal(hasAcceptedRules(storage), false);
});

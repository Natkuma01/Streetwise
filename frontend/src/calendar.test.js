import assert from "node:assert/strict";
import test from "node:test";

import { eventIdFromHash, filterEventsByCategories, monthWindow } from "./calendar.js";

const events = [
  { id: 1, categories: ["Tech", "Education"] },
  { id: 2, categories: ["Community"] },
  { id: 3, categories: ["Finance", "Career"] },
];

test("category filters match any selected category", () => {
  assert.deepEqual(
    filterEventsByCategories(events, ["Education", "Career"]).map((event) => event.id),
    [1, 3],
  );
});

test("no category filters returns every event", () => {
  assert.deepEqual(filterEventsByCategories(events, []), events);
});

test("month window spans exactly one calendar month", () => {
  const { start, end } = monthWindow(new Date(2026, 10, 1));
  assert.match(start, /^2026-11-01T/);
  assert.match(end, /^2026-12-01T/);
});

test("event detail hashes resolve only numeric event ids", () => {
  assert.equal(eventIdFromHash("#event/42"), 42);
  assert.equal(eventIdFromHash("#event/not-a-number"), null);
  assert.equal(eventIdFromHash("#rules"), null);
});

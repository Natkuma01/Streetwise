import assert from "node:assert/strict";
import test from "node:test";

import { eventIdFromHash, filterEventsByCategories, isValidEmail, isValidHttpUrl, monthWindow, validateEventSubmission } from "./calendar.js";

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

test("event submission validation accepts optional fields left blank", () => {
  assert.deepEqual(validateEventSubmission({
    title: "Community workshop",
    date: "2026-12-10",
    startTime: "18:00",
    endTime: "",
    time_zone: "America/New_York",
    categories: ["Community"],
    event_url: "",
    submitter_email: "",
  }), {});
});

test("event submission validation returns field-specific errors", () => {
  const errors = validateEventSubmission({
    title: "",
    date: "",
    startTime: "",
    endTime: "17:00",
    time_zone: "",
    categories: [],
    location: "www.example.com/meeting",
    event_url: "javascript:alert(1)",
    submitter_email: "not-an-email",
  });

  assert.deepEqual(Object.keys(errors).sort(), [
    "categories", "date", "event_url", "location", "start_time", "submitter_email", "time_zone", "title",
  ]);
});

test("URL and email validation only accepts expected structures", () => {
  assert.equal(isValidHttpUrl("https://example.com/event"), true);
  assert.equal(isValidHttpUrl("javascript:alert(1)"), false);
  assert.equal(isValidEmail("visitor@example.com"), true);
  assert.equal(isValidEmail("visitor-at-example.com"), false);
});

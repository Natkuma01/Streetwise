import assert from "node:assert/strict";
import test from "node:test";

import { isValidYoutubeUrl, youtubeIdFromUrl } from "./videos.js";

test("accepts supported YouTube URL formats", () => {
  assert.equal(youtubeIdFromUrl("https://www.youtube.com/watch?v=dQw4w9WgXcQ"), "dQw4w9WgXcQ");
  assert.equal(youtubeIdFromUrl("https://youtu.be/dQw4w9WgXcQ"), "dQw4w9WgXcQ");
  assert.equal(youtubeIdFromUrl("https://youtube.com/shorts/dQw4w9WgXcQ"), "dQw4w9WgXcQ");
});

test("rejects non-YouTube and structurally invalid URLs", () => {
  assert.equal(isValidYoutubeUrl("https://example.com/watch?v=dQw4w9WgXcQ"), false);
  assert.equal(isValidYoutubeUrl("https://youtube.com.evil.example/watch?v=dQw4w9WgXcQ"), false);
  assert.equal(isValidYoutubeUrl("https://youtube.com/watch?v=short"), false);
  assert.equal(isValidYoutubeUrl("not a url"), false);
});

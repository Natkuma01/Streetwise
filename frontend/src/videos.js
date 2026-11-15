const YOUTUBE_HOSTS = new Set([
  "youtube.com",
  "www.youtube.com",
  "m.youtube.com",
  "music.youtube.com",
]);
const YOUTUBE_SHORT_HOSTS = new Set(["youtu.be", "www.youtu.be"]);
const YOUTUBE_ID = /^[A-Za-z0-9_-]{11}$/;

export function youtubeIdFromUrl(value) {
  try {
    const url = new URL(value);
    if (!['http:', 'https:'].includes(url.protocol)) return null;

    let candidate = null;
    if (YOUTUBE_SHORT_HOSTS.has(url.hostname)) {
      candidate = url.pathname.split('/').filter(Boolean)[0];
    } else if (YOUTUBE_HOSTS.has(url.hostname)) {
      const parts = url.pathname.split('/').filter(Boolean);
      if (url.pathname.replace(/\/$/, '') === '/watch') candidate = url.searchParams.get('v');
      else if (parts.length >= 2 && ['embed', 'shorts', 'live'].includes(parts[0])) candidate = parts[1];
    }
    return candidate && YOUTUBE_ID.test(candidate) ? candidate : null;
  } catch {
    return null;
  }
}

export function isValidYoutubeUrl(value) {
  return youtubeIdFromUrl(value) !== null;
}

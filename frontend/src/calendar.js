export function filterEventsByCategories(events, selectedCategories) {
  if (!selectedCategories.length) return events;
  return events.filter((event) =>
    event.categories.some((category) => selectedCategories.includes(category)),
  );
}

export function monthWindow(month) {
  const start = new Date(month.getFullYear(), month.getMonth(), 1);
  const end = new Date(month.getFullYear(), month.getMonth() + 1, 1);
  return { start: start.toISOString(), end: end.toISOString() };
}

export function eventIdFromHash(hash) {
  const match = hash.match(/^#event\/(\d+)$/);
  return match ? Number(match[1]) : null;
}

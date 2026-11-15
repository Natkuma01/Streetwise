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

const TIME_PATTERN = /^([01]\d|2[0-3]):[0-5]\d$/;

export function isValidHttpUrl(value) {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol);
  } catch {
    return false;
  }
}

export function isValidEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

export function validateEventSubmission(form) {
  const errors = {};
  if (!form.title.trim()) errors.title = "Add a title.";
  else if (form.title.trim().length > 180) errors.title = "Keep the title to 180 characters or fewer.";
  if (!form.date || Number.isNaN(Date.parse(`${form.date}T00:00:00`))) errors.date = "Choose a valid date.";
  if (!TIME_PATTERN.test(form.startTime)) errors.start_time = "Add a valid start time.";
  if (!form.time_zone) errors.time_zone = "Choose a time zone.";
  if (!form.categories.length) errors.categories = "Choose at least one category.";
  if (form.endTime && !TIME_PATTERN.test(form.endTime)) errors.end_time = "Add a valid end time or leave it blank.";
  else if (form.endTime && form.startTime && form.endTime <= form.startTime) errors.end_time = "End time must be after start time.";
  if (form.location && (/^www\./i.test(form.location.trim()) || form.location.includes("://")) && !isValidHttpUrl(form.location.trim())) errors.location = "Add a complete http or https meeting link, or enter a physical location.";
  if (form.event_url.trim() && !isValidHttpUrl(form.event_url.trim())) errors.event_url = "Add a valid http or https link.";
  if (form.submitter_email.trim() && !isValidEmail(form.submitter_email.trim())) errors.submitter_email = "Add a valid email address or leave it blank.";
  return errors;
}

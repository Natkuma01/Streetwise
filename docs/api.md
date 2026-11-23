# Streetwise API (v1.0)

Base path: `/api/`. Everything is JSON. There is no login and no CSRF token. In local development the Vite dev server forwards `/api` to Django, so call `/api/events/` from React with no host.

## Times

All times are UTC. Send and expect ISO 8601 with a `Z`, like `2026-12-01T18:00:00Z`. Convert to the viewer's local time in React. A time sent with no offset is read as UTC.

## `GET /api/events/`

Returns Pending and Approved events, soonest first. Rejected and cancelled events never appear.

Optional filters, both on the event start time:

| Parameter | Meaning |
| --- | --- |
| `start` | On or after this date or datetime. |
| `end` | On or before this date or datetime. A plain date includes that whole day. |

A plain date like `2026-12-01` is read as UTC. Pass full datetimes if you need a month boundary in the viewer's timezone.

```json
[
  {
    "id": 1,
    "title": "Intro to threat modeling",
    "start_at": "2026-12-01T18:00:00Z",
    "end_at": null,
    "event_link": "https://example.com/threat-modeling",
    "attendance_mode": "virtual",
    "description": "",
    "categories": [{ "id": 1, "name": "Cybersecurity" }],
    "submitter_name": "Anonymous",
    "status": "pending"
  }
]
```

- `status` is `pending` or `approved`. Show pending events in the faded style.
- `submitter_name` is `"Anonymous"` when the submitter left it blank.
- The submitter's email, the reference number and the private edit key are never returned here.

## `GET /api/categories/`

```json
[{ "id": 5, "name": "Business" }, { "id": 1, "name": "Cybersecurity" }]
```

Use these ids in the add event form. The list can change in Django admin, so load it instead of hard-coding it.

## `POST /api/events/`

| Field | Required | Notes |
| --- | --- | --- |
| `title` | yes | Up to 200 characters. |
| `submitter_email` | yes | Never shown publicly. Used for the receipt and approval emails. |
| `start_at` | yes | Must be in the future. |
| `event_link` | yes | Must start with `http://` or `https://`. Up to 500 characters. |
| `attendance_mode` | yes | `in_person` or `virtual`. |
| `categories` | yes | A list of category ids. At least one. |
| `submitter_name` | no | Shown as "Anonymous" when blank. |
| `end_at` | no | Must be after `start_at`. |
| `description` | no | |

Any `status` sent in the body is ignored. New events are always Pending.

```json
{
  "title": "Resume workshop",
  "submitter_email": "pat@example.com",
  "start_at": "2026-12-03T23:00:00Z",
  "event_link": "https://example.com/resume",
  "attendance_mode": "in_person",
  "categories": [3]
}
```

### Spam protection (add this to the form)

The form needs a hidden trap field called `fax_number`. Real people never see it, so it stays empty. Bots fill in every box they find.

- Add an input named `fax_number` to the form and hide it. Use CSS (`position: absolute; left: -9999px`) plus `tabIndex={-1}` and `autoComplete="off"`. Do not use `type="hidden"` or `display: none`, because some bots skip those.
- Send it with the rest of the body. Leave it as an empty string `""`.
- If it has any value, the API replies `201` as if it worked, but saves nothing and sends no email. The fake reply has only `status` and `ref_number`, so do not rely on the other fields in the success response.

There is also a rate limit: **10 submits per hour for each visitor address** (`EVENT_SUBMIT_RATE` in `.env`). The 11th gets `429` with a `Retry-After` header (seconds). Show something kind, like "Too many submissions. Please try again later." Reading the calendar is never limited.

Success is `201` with the saved event plus its `ref_number`, like `SW-A3F19C2B`. Show it on the confirmation screen so the person can quote it in an email.

```json
{
  "id": 7,
  "title": "Resume workshop",
  "start_at": "2026-12-03T23:00:00Z",
  "end_at": null,
  "event_link": "https://example.com/resume",
  "attendance_mode": "in_person",
  "description": "",
  "categories": [{ "id": 3, "name": "Human Resources" }],
  "submitter_name": "Anonymous",
  "status": "pending",
  "ref_number": "SW-A3F19C2B"
}
```

Bad input is `400`. The body maps each field to a list of messages. Show each message next to its field.

```json
{
  "start_at": ["The event start must be in the future."],
  "categories": ["Choose at least one category."]
}
```

A missing required field returns `"This field is required."` for that field.

## Edit or cancel with the private link

Every submitter gets a private link in their receipt email:

```
https://your-site/events/manage#<manage-key>
```

The key sits after the `#` on purpose. Browsers never send that part to a server, so it stays out of server logs. The React page at `/events/manage` should:

1. Read the key from `window.location.hash` (drop the leading `#`).
2. Send it in an `X-Manage-Key` header on every call below. **Never put the key in the URL path or query string.** The API ignores it there.
3. Remove it from the address bar after reading it if you like: `history.replaceState(null, "", "/events/manage")`. Keep it in memory (or `sessionStorage`) for the page.

There are no accounts. Whoever has the key can change that one event, so tell people not to forward the email.

| Call | What it does |
| --- | --- |
| `GET /api/manage/` | Returns the event, with `ref_number` and `submitter_email` too. Use it to fill the edit form. |
| `PATCH /api/manage/` | Edits the event. Send only the fields that changed. |
| `POST /api/manage/cancel/` | Cancels the event. It disappears from the calendar. No body needed. |

Fields that can be edited: `title`, `submitter_name`, `start_at`, `end_at` (send `null` to clear it), `event_link`, `attendance_mode`, `description`, `categories`. The email, reference number and status cannot be changed. If you send them, they are ignored. The same rules as a new submit apply to every field you send.

```bash
curl -X PATCH https://your-site/api/manage/ \
  -H "X-Manage-Key: 3f1c2e9a-7b1d-4c58-9b0a-2f6a5d8e1c34" \
  -H "Content-Type: application/json" \
  -d '{"title": "Resume workshop (new room)"}'
```

The response is the full event, like this:

```json
{
  "id": 7,
  "ref_number": "SW-A3F19C2B",
  "title": "Resume workshop (new room)",
  "submitter_email": "pat@example.com",
  "submitter_name": "",
  "start_at": "2026-12-03T23:00:00Z",
  "end_at": null,
  "event_link": "https://example.com/resume",
  "attendance_mode": "in_person",
  "description": "",
  "categories": [{ "id": 3, "name": "Human Resources" }],
  "status": "pending"
}
```

`submitter_name` is the real saved value here, so it is `""` when blank. Do not show "Anonymous" in the edit form.

**An edit sends an approved event back to Pending.** The admin gets an email to review it again. Tell the person this before they save, for example: "Saving changes sends your event back for review." An edit that changes nothing does not do this. Editing a Pending event keeps it Pending.

| Status | Meaning |
| --- | --- |
| `200` | Done. |
| `400` | Bad input. Same format as the submit errors. |
| `404` | The key is missing or wrong. Show "This link is not valid." |
| `409` | The event is rejected or cancelled, so it cannot be changed. `detail` says which. A cancelled event can still be opened with `GET`, so show that it is cancelled. Cancelling an already cancelled event is fine and returns `200`. |
| `410` | The link expired. It works until 3 days after the event ends (`MANAGE_LINK_GRACE_DAYS`). |
| `429` | Too many tries from this address (60 per hour). |

Errors other than `400` look like `{ "detail": "..." }`.

Responses are marked `Cache-Control: no-store`, since they hold private details.

## Emails

On a successful submit the backend sends two emails: a receipt to the submitter, and a heads-up to the project inbox. The receipt includes the reference number and the private edit and cancel link (see above). When the admin approves, the submitter gets a third email. Rejecting sends nothing.

If an approved event is edited, the project inbox gets another email so the admin can approve it again. Events that stay Pending for more than 24 hours get one reminder email to the project inbox (`python manage.py send_pending_reminders`, run hourly by cron).

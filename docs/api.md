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

Success is `201` with the saved event plus its `reference_number`, like `SW-A3F19C2B`. Show it on the confirmation screen so the person can quote it in an email.

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
  "reference_number": "SW-A3F19C2B"
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

## Emails

On a successful submit the backend sends two emails: a receipt to the submitter, and a heads-up to the project inbox. The receipt includes the reference number and a private link to edit or cancel (the page behind that link is ticket SSP-20). When the admin approves, the submitter gets a third email. Rejecting sends nothing.

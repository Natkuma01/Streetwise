import { useEffect, useMemo, useState } from "react";
import { CalendarDays, ChevronLeft, ChevronRight, ExternalLink, MapPin, Plus, ShieldCheck, SlidersHorizontal, X } from "lucide-react";
import { eventIdFromHash, filterEventsByCategories, monthWindow } from "./calendar";

const CATEGORIES = ["Tech", "Finance", "Marketing", "Business", "Entrepreneurship", "Education", "Arts & Culture", "Community", "Career", "Others"];
const COLORS = {
  Tech: "#276c57", Finance: "#3d8067", Marketing: "#b58c2d", Business: "#507564",
  Entrepreneurship: "#96783a", Education: "#6c8d5b", "Arts & Culture": "#7d6f48",
  Community: "#2f7a6b", Career: "#557c3f", Others: "#718078",
};
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const emptyForm = { title: "", date: "", startTime: "", endTime: "", event_url: "", categories: [], location: "", description: "" };

const isoDay = (date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
const sameDay = (iso, date) => iso.slice(0, 10) === isoDay(date);
const displayTime = (iso) => new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", timeZone: "America/New_York" }).format(new Date(iso));

function App({ onReviewRules }) {
  const [month, setMonth] = useState(() => new Date(new Date().getFullYear(), new Date().getMonth(), 1));
  const [events, setEvents] = useState([]);
  const [filters, setFilters] = useState([]);
  const [showFilters, setShowFilters] = useState(false);
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [confirming, setConfirming] = useState(false);
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(true);
  const [detailId, setDetailId] = useState(() => eventIdFromHash(window.location.hash));
  const [detailEvent, setDetailEvent] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const loadEvents = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams(monthWindow(month));
      const response = await fetch(`/api/events/?${params}`);
      const data = await response.json();
      setEvents(data.events || []);
    } finally { setLoading(false); }
  };

  useEffect(() => { loadEvents(); }, [month]);

  useEffect(() => {
    const syncDetail = () => setDetailId(eventIdFromHash(window.location.hash));
    window.addEventListener("hashchange", syncDetail);
    window.addEventListener("popstate", syncDetail);
    return () => {
      window.removeEventListener("hashchange", syncDetail);
      window.removeEventListener("popstate", syncDetail);
    };
  }, []);

  useEffect(() => {
    if (!detailId) {
      setDetailEvent(null);
      return;
    }
    const cached = events.find((event) => event.id === detailId);
    if (cached) {
      setDetailEvent(cached);
      return;
    }
    setDetailLoading(true);
    fetch(`/api/events/${detailId}/`)
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("not found")))
      .then((data) => setDetailEvent(data.event))
      .catch(() => setDetailEvent(null))
      .finally(() => setDetailLoading(false));
  }, [detailId, events]);

  const visibleEvents = useMemo(
    () => filterEventsByCategories(events, filters),
    [events, filters],
  );
  const days = useMemo(() => {
    const first = new Date(month.getFullYear(), month.getMonth(), 1);
    const start = new Date(first); start.setDate(1 - first.getDay());
    return Array.from({ length: 42 }, (_, index) => { const day = new Date(start); day.setDate(start.getDate() + index); return day; });
  }, [month]);

  const updateForm = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const toggleCategory = (category, target = "form") => {
    if (target === "filter") setFilters((current) => current.includes(category) ? current.filter((item) => item !== category) : [...current, category]);
    else updateForm("categories", form.categories.includes(category) ? form.categories.filter((item) => item !== category) : [...form.categories, category]);
  };
  const openAdd = (date = null) => {
    setForm({ ...emptyForm, date: date ? isoDay(date) : "" }); setErrors({}); setConfirming(false); setModal("add");
  };
  const openEvent = (event) => {
    window.history.pushState(null, "", `#event/${event.id}`);
    setDetailEvent(event);
    setDetailId(event.id);
    setModal(null);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const closeEvent = () => {
    window.history.pushState(null, "", window.location.pathname);
    setDetailId(null);
    setDetailEvent(null);
  };
  const validate = () => {
    const next = {};
    if (!form.title.trim()) next.title = "Add a title.";
    if (!form.date) next.date = "Choose a date.";
    if (!form.startTime) next.startTime = "Add a start time.";
    if (!form.endTime) next.endTime = "Add an end time.";
    if (!form.event_url.trim()) next.event_url = "Add the event link.";
    if (!form.categories.length) next.categories = "Choose at least one category.";
    if (form.date && form.startTime && form.endTime && form.endTime <= form.startTime) next.endTime = "End time must be after start time.";
    setErrors(next); return Object.keys(next).length === 0;
  };
  const beginSubmit = (event) => { event.preventDefault(); if (validate()) setConfirming(true); };
  const submitEvent = async () => {
    const payload = { ...form, start_at: `${form.date}T${form.startTime}:00`, end_at: `${form.date}T${form.endTime}:00` };
    const response = await fetch("/api/events/", { method: "POST", headers: { "Content-Type": "application/json", "X-CSRFToken": document.cookie.match(/csrftoken=([^;]+)/)?.[1] || "" }, body: JSON.stringify(payload) });
    const data = await response.json();
    if (!response.ok) { setErrors(data.errors || { form: "Something went wrong. Please try again." }); setConfirming(false); return; }
    setEvents((current) => [...current, data.event]); setConfirming(false); setModal(null);
  };

  if (detailId) {
    return <EventDetailsPage event={detailEvent} loading={detailLoading} onBack={closeEvent} onReviewRules={onReviewRules} />;
  }

  return <div className="app-shell">
    <header className="topbar">
      <a className="brand" href="#" aria-label="Streetwise NYC home"><span className="brand-mark"><CalendarDays size={20} /></span><span>Streetwise <b>NYC</b></span></a>
      <p className="tagline">A community calendar for curious New Yorkers.</p>
      <button className="rules-link" type="button" onClick={onReviewRules}>
        <ShieldCheck size={16} /> Community rules
      </button>
      <button className="primary-button" onClick={() => openAdd()}><Plus size={18} /> Add an event</button>
    </header>

    <main>
      <section className="intro">
        <div><p className="eyebrow">WHAT'S HAPPENING IN THE CITY</p><h1>Find your next<br/><em>good room.</em></h1></div>
        <p className="intro-copy">Talks, gatherings, workshops, and ideas worth leaving the house for—shared by the Streetwise community.</p>
      </section>

      <section className="calendar-card">
        <div className="calendar-toolbar">
          <div className="month-controls"><button className="icon-button" onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))} aria-label="Previous month"><ChevronLeft /></button><h2>{month.toLocaleString("en-US", { month: "long", year: "numeric" })}</h2><button className="icon-button" onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))} aria-label="Next month"><ChevronRight /></button></div>
          <div className="toolbar-actions"><button className="text-button" onClick={() => setMonth(new Date(new Date().getFullYear(), new Date().getMonth(), 1))}>Today</button><button className={`filter-button ${filters.length ? "active" : ""}`} onClick={() => setShowFilters(!showFilters)}><SlidersHorizontal size={16}/> Categories {filters.length ? `(${filters.length})` : ""}</button></div>
        </div>
        {showFilters && <div className="filter-panel"><div><b>Show me</b><span>Select as many as you like</span></div><div className="filter-options">{CATEGORIES.map((category) => <button key={category} onClick={() => toggleCategory(category, "filter")} className={filters.includes(category) ? "selected" : ""} style={{ "--category": COLORS[category] }}><i />{category}</button>)}</div>{filters.length > 0 && <button className="clear-button" onClick={() => setFilters([])}>Clear all</button>}</div>}
        <div className="weekday-row">{WEEKDAYS.map((day) => <div key={day}>{day}</div>)}</div>
        <div className="calendar-grid">{days.map((day) => {
          const dayEvents = visibleEvents.filter((event) => sameDay(event.start_at, day));
          const outside = day.getMonth() !== month.getMonth();
          const today = isoDay(day) === isoDay(new Date());
          const startOfToday = new Date(); startOfToday.setHours(0, 0, 0, 0);
          const past = day < startOfToday;
          return <div className={`day-cell ${outside ? "outside" : ""} ${past ? "past" : ""}`} key={isoDay(day)} onDoubleClick={() => openAdd(day)}>
            <div className={`date-number ${today ? "today" : ""}`}>{day.getDate()}</div>
            <div className="day-events">{dayEvents.slice(0, 3).map((event) => <button className={`event-chip ${event.status === "cancelled" ? "cancelled" : ""} ${event.status === "pending" ? "pending" : ""}`} key={event.id} style={{ "--category": COLORS[event.categories[0]] }} onClick={() => openEvent(event)}><span>{displayTime(event.start_at)}</span>{event.status === "cancelled" ? "Cancelled · " : event.status === "pending" ? "Pending · " : ""}{event.title}</button>)}{dayEvents.length > 3 && <button className="more-events" onClick={() => setModal({ day, events: dayEvents })}>+{dayEvents.length - 3} more</button>}</div>
            {!outside && <button className="day-add" onClick={() => openAdd(day)} aria-label={`Add event on ${day.toDateString()}`}><Plus size={15}/></button>}
          </div>;
        })}</div>
        {loading && <div className="loading">Loading events…</div>}
      </section>

      <section className="category-key"><span>Category key</span>{CATEGORIES.map((category) => <span key={category}><i style={{ background: COLORS[category] }}/>{category}</span>)}</section>
    </main>

    <footer><p>Built for the Streetwise community in NYC.</p><p>Need an event removed? No big deal—<a href="mailto:natkuma@outlook.com">email Natalie</a> or <a href="https://www.linkedin.com/in/natalie-chan-shimin/" target="_blank" rel="noreferrer">message her on LinkedIn</a>.</p></footer>

    {modal === "add" && <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && setModal(null)}><div className="modal add-modal"><button className="modal-close" onClick={() => setModal(null)}><X /></button>{confirming ? <Confirmation form={form} onBack={() => setConfirming(false)} onSubmit={submitEvent}/> : <EventForm form={form} errors={errors} updateForm={updateForm} toggleCategory={toggleCategory} onSubmit={beginSubmit}/>}</div></div>}
    {modal?.events && <div className="modal-backdrop"><div className="modal"><button className="modal-close" onClick={() => setModal(null)}><X /></button><p className="eyebrow">{modal.day.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}</p><h2>Events this day</h2><div className="event-list">{modal.events.map((event) => <button key={event.id} onClick={() => openEvent(event)}>{event.status === "cancelled" ? "Cancelled · " : event.status === "pending" ? "Pending · " : ""}{displayTime(event.start_at)} · {event.title}</button>)}</div></div></div>}
  </div>;
}

function FieldError({ children }) { return children ? <span className="field-error">{children}</span> : null; }
function EventForm({ form, errors, updateForm, toggleCategory, onSubmit }) {
  return <form onSubmit={onSubmit}><p className="eyebrow">SHARE WITH THE COMMUNITY</p><h2>Add an event</h2><p className="form-lede">Found something worth knowing about? Drop in the essentials—the event page can handle the rest.</p>
    {errors.form && <div className="form-error">{errors.form}</div>}
    <label>Event title <b>*</b><input value={form.title} onChange={(e) => updateForm("title", e.target.value)} placeholder="What’s the event called?"/><FieldError>{errors.title}</FieldError></label>
    <div className="form-row three"><label>Date <b>*</b><input type="date" value={form.date} onChange={(e) => updateForm("date", e.target.value)}/><FieldError>{errors.date}</FieldError></label><label>Starts <b>*</b><input type="time" value={form.startTime} onChange={(e) => updateForm("startTime", e.target.value)}/><FieldError>{errors.startTime}</FieldError></label><label>Ends <b>*</b><input type="time" value={form.endTime} onChange={(e) => updateForm("endTime", e.target.value)}/><FieldError>{errors.endTime}</FieldError></label></div>
    <label>Event or registration link <b>*</b><input type="url" value={form.event_url} onChange={(e) => updateForm("event_url", e.target.value)} placeholder="https://…"/><small>This can be the event page with all the details.</small><FieldError>{errors.event_url}</FieldError></label>
    <fieldset><legend>Categories <b>*</b> <span>Choose all that fit</span></legend><div className="category-picker">{CATEGORIES.map((category) => <button type="button" key={category} className={form.categories.includes(category) ? "selected" : ""} style={{ "--category": COLORS[category] }} onClick={() => toggleCategory(category)}><i/>{category}</button>)}</div><FieldError>{errors.categories}</FieldError></fieldset>
    <label>Location <span>Optional</span><input value={form.location} onChange={(e) => updateForm("location", e.target.value)} placeholder="Venue, neighborhood, or ‘Online’"/></label>
    <label>Short description <span>Optional</span><textarea value={form.description} onChange={(e) => updateForm("description", e.target.value)} placeholder="Anything useful that isn't obvious from the event page" rows="3"/></label>
    <button className="primary-button submit-button" type="submit">Review event <ChevronRight size={18}/></button>
  </form>;
}
function Confirmation({ form, onBack, onSubmit }) {
  return <div className="confirmation"><div className="warning-icon">!</div><p className="eyebrow">ONE QUICK LOOK</p><h2>Everything look right?</h2><p>Your event will appear on the calendar in a light <strong>Pending</strong> style until Natalie reviews and approves it. Give the date, time, and link a quick check before submitting. We’re happy you’re sharing it.</p>
    <div className="review-card"><b>{form.title}</b><span>{new Date(`${form.date}T12:00`).toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" })}</span><span>{form.startTime}–{form.endTime} · New York time</span><span className="review-link">{form.event_url}</span></div>
    <div className="confirmation-actions"><button className="text-button" onClick={onBack}>Go back and edit</button><button className="primary-button" onClick={onSubmit}>Yes, add it</button></div>
  </div>;
}
function EventDetailsPage({ event, loading, onBack, onReviewRules }) {
  return <div className="app-shell event-detail-page">
    <header className="topbar">
      <button className="brand brand-button" type="button" onClick={onBack} aria-label="Back to calendar"><span className="brand-mark"><CalendarDays size={20} /></span><span>Streetwise <b>NYC</b></span></button>
      <p className="tagline">Event details</p>
      <button className="rules-link" type="button" onClick={onReviewRules}><ShieldCheck size={16} /> Community rules</button>
      <button className="text-button" type="button" onClick={onBack}><ChevronLeft size={17}/> Back to calendar</button>
    </header>
    <main className="event-detail-main">
      {loading && <p className="detail-state">Loading event…</p>}
      {!loading && !event && <section className="detail-page-card"><p className="eyebrow">EVENT NOT AVAILABLE</p><h1>This event could not be found.</h1><button className="primary-button" onClick={onBack}>Return to calendar</button></section>}
      {event && <article className="detail-page-card">
        {event.status === "cancelled" && <div className="cancelled-banner" role="status">Cancelled — this event is no longer taking place.</div>}
        {event.status === "pending" && <div className="pending-banner" role="status">Pending approval — this event has been submitted and is waiting for review.</div>}
        <div className="detail-categories">{event.categories.map((category) => <span style={{ "--category": COLORS[category] }} key={category}><i/>{category}</span>)}</div>
        <h1>{event.title}</h1>
        <p className="detail-time">{new Date(event.start_at).toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" })}<br/><b>{displayTime(event.start_at)}–{displayTime(event.end_at)} ET</b></p>
        {event.location && <p className="detail-location"><MapPin size={18}/>{event.location}</p>}
        {event.description && <p className="detail-description">{event.description}</p>}
        <a className="primary-button detail-link" href={event.event_url} target="_blank" rel="noreferrer">View event details <ExternalLink size={17}/></a>
      </article>}
    </main>
  </div>;
}

export default App;


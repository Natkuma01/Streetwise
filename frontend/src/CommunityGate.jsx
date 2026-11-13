import { ArrowRight, CalendarDays, RotateCcw } from "lucide-react";
import { useState } from "react";

const RULES = [
  {
    title: "Share information people can trust.",
    copy: "Check event details and links before you post so other people can rely on what you share.",
  },
  {
    title: "Treat everyone with respect.",
    copy: "Harassment, hate speech, discrimination, and personal attacks don’t belong here.",
  },
  {
    title: "Keep it useful.",
    copy: "Don’t post spam, scams, or misleading links. Share things that genuinely help the community.",
  },
  {
    title: "Protect your own privacy.",
    copy: (
      <>
        This is an early version of the platform and does not yet have all of the
        security protections we plan to add. Strengthening security is our next
        priority. For now, <mark style={{ background: "#bfe8d3", color: "#16251f", borderRadius: 3, padding: "0.08em 0.25em" }}>DO NOT SHARE SENSITIVE INFORMATION</mark> or anything
        you would not be comfortable having seen publicly.
      </>
    ),
  },
];

export function CommunityRules({ isReviewing, onAgree, onDisagree }) {
  const [storageError, setStorageError] = useState("");

  const agree = () => {
    try {
      onAgree();
    } catch {
      setStorageError(
        "Your browser isn’t letting this site remember your choice. Please allow browser storage and try again.",
      );
    }
  };

  return (
    <main className="gate-page">
      <section className="gate-hero">
        <a className="brand gate-brand" href="#rules" aria-label="Streetwise NYC community rules">
          <span className="brand-mark"><CalendarDays size={20} /></span>
          <span>Streetwise <b>NYC</b></span>
        </a>
        <p className="eyebrow">{isReviewing ? "A QUICK REFRESH" : "WELCOME TO STREETWISE"}</p>
        <h1>Good things happen when people <em>share what they know.</em></h1>
        <p className="gate-lede">
          Job hunting and building a career are hard enough on your own. Streetwise is a place
          to share events, opportunities, resources, and honest advice with the community.
        </p>
      </section>

      <section className="rules-card" aria-labelledby="community-rules-heading">
        <div className="rules-intro">
          <p className="eyebrow">{isReviewing ? "GOOD TO SEE YOU AGAIN" : "BEFORE YOU COME IN"}</p>
          <h2 id="community-rules-heading">A few rules to keep this space useful.</h2>
          <p>
            {isReviewing
              ? "Here are the rules you agreed to. You can come back and review them anytime."
              : "Please take a minute to read these. Everyone sees the same rules before opening the calendar."}
          </p>
        </div>

        <ol className="rules-list">
          {RULES.map((rule, index) => (
            <li key={rule.title}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <div><strong>{rule.title}</strong><p>{rule.copy}</p></div>
            </li>
          ))}
        </ol>

        <div className="rules-decision">
          <p>
            By selecting <strong>Agree and continue</strong>, you’re saying that you understand
            these rules and will follow them.
          </p>
          <div>
            <button className="primary-button" type="button" onClick={agree}>
              Agree and continue <ArrowRight size={18} />
            </button>
            <button className="quiet-button" type="button" onClick={onDisagree}>Disagree</button>
          </div>
          {storageError && <p className="gate-error" role="alert">{storageError}</p>}
        </div>
      </section>
    </main>
  );
}

export function NotWelcome({ onReview }) {
  return (
    <main className="declined-page">
      <section className="declined-card">
        <p className="eyebrow">STREETWISE COMMUNITY</p>
        <h1>You’re not welcome to use this website without accepting the rules.</h1>
        <p>
          This community only works when everyone agrees to treat each other with care and
          respect. If you change your mind, you can read the rules again.
        </p>
        <button className="primary-button" type="button" onClick={onReview}>
          <RotateCcw size={17} /> Read the rules again
        </button>
      </section>
    </main>
  );
}

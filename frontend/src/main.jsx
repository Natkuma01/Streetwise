import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { CommunityRules, NotWelcome } from "./CommunityGate";
import { acceptRules, clearRulesAcceptance, hasAcceptedRules } from "./consent";
import "./styles.css";

function viewFromLocation() {
  if (window.location.hash === "#rules") return "rules";
  if (window.location.hash === "#not-welcome") return "not-welcome";
  return hasAcceptedRules() ? "calendar" : "rules";
}

function StreetwiseExperience() {
  const [view, setView] = useState(viewFromLocation);

  useEffect(() => {
    const syncView = () => setView(viewFromLocation());
    window.addEventListener("hashchange", syncView);
    return () => window.removeEventListener("hashchange", syncView);
  }, []);

  const openView = (nextView, hash) => {
    window.history.pushState(null, "", hash);
    setView(nextView);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  if (view === "rules") {
    return (
      <CommunityRules
        isReviewing={hasAcceptedRules()}
        onAgree={() => {
          acceptRules();
          window.history.replaceState(null, "", window.location.pathname);
          setView("calendar");
        }}
        onDisagree={() => {
          clearRulesAcceptance();
          openView("not-welcome", "#not-welcome");
        }}
      />
    );
  }

  if (view === "not-welcome") {
    return <NotWelcome onReview={() => openView("rules", "#rules")} />;
  }

  return <App onReviewRules={() => openView("rules", "#rules")} />;
}

createRoot(document.getElementById("root")).render(
  <React.StrictMode><StreetwiseExperience /></React.StrictMode>,
);


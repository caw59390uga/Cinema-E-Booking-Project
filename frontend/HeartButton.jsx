import React from "react";
import { Heart } from "lucide-react";

// Heart icon with a tooltip. Filled = already a favorite.
// Keep it OUTSIDE other <button> elements (nested buttons are invalid HTML).
export default function HeartButton({
  active,
  onClick,
  signedIn = true,
  className = "",
}) {
  const label = !signedIn
    ? "Sign in to save favorites"
    : active
    ? "Remove from favorites"
    : "Add to favorites";

  return (
    <button
      type="button"
      className={`heart-btn ${active ? "active" : ""} ${className}`}
      data-tip={label}
      aria-label={label}
      aria-pressed={Boolean(active)}
      onClick={(event) => {
        event.stopPropagation();
        onClick();
      }}
    >
      <Heart size={17} fill={active ? "currentColor" : "none"} />
    </button>
  );
}

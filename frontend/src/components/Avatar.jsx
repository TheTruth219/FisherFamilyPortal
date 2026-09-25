import React, { useState } from "react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const SIZES = {
  sm: "h-11 w-11 text-base",
  md: "h-16 w-16 text-xl",
  lg: "h-28 w-28 text-4xl",
};

export function Avatar({ member, size = "md", className = "", testId }) {
  const [failed, setFailed] = useState(false);
  const initials = `${member?.first_name?.[0] || member?.email?.[0] || "F"}${member?.last_name?.[0] || ""}`.toUpperCase();
  const src = member?.photo_url && !failed ? `${BACKEND_URL}${member.photo_url}` : null;
  return (
    <div
      data-testid={testId}
      className={`relative flex items-center justify-center rounded-full overflow-hidden font-heading font-bold text-white bg-gradient-to-br from-blue-800 to-blue-900 flex-shrink-0 ring-2 ring-white shadow-sm ${SIZES[size]} ${className}`}
    >
      {src ? (
        <img src={src} alt="" className="h-full w-full object-cover" onError={() => setFailed(true)} />
      ) : (
        <span aria-hidden="true">{initials}</span>
      )}
    </div>
  );
}

export const money = (cents = 0) =>
  `$${(cents / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export const shortDate = (iso) => (iso ? String(iso).slice(0, 10) : "");

export const prettyDate = (iso) => {
  if (!iso) return "";
  const d = new Date(String(iso).length === 10 ? iso + "T00:00:00" : iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
};

export const ROLE_TIERS = { member: 1, business: 2, committee: 3, admin: 4 };
export const roleLevel = (r) => ROLE_TIERS[r] || 0;

export const steps = [
  { key: "role", title: "What role are you targeting?" },
  { key: "contact", title: "Your contact details" },
  { key: "experience", title: "Work experience" },
  { key: "education", title: "Education" },
  { key: "skills", title: "Your skills" },
  { key: "review", title: "Review & score" },
] as const;
export type StepKey = (typeof steps)[number]["key"];

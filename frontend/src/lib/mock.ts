import type { ScoreReport } from "@/types/resume";

/** Mock report — used while backend scoring endpoints are stubs. */
export const mockReport: ScoreReport = {
  id: "demo",
  jobTitle: "Frontend Developer",
  total: 72,
  verdict: "Good foundation — 6 fixes found",
  categories: [
    { key: "skills", label: "Skills", score: 82, weight: 0.3 },
    { key: "experience", label: "Experience", score: 74, weight: 0.25 },
    { key: "semantic", label: "Semantic match", score: 66, weight: 0.2 },
    { key: "projects", label: "Projects", score: 70, weight: 0.1 },
    { key: "education", label: "Education", score: 88, weight: 0.1 },
    { key: "formatting", label: "Formatting", score: 55, weight: 0.05 },
  ],
  suggestions: [
    { id: "s1", severity: "high", title: "Add missing role-critical skills", why: "TypeScript, testing, and CI/CD appear in most Frontend Developer postings but not in your resume.", category: "skills" },
    { id: "s2", severity: "high", title: "Quantify your achievements", why: "Only 1 of 8 bullet points contains a number. Recruiters scan for measurable impact.", category: "experience" },
    { id: "s3", severity: "medium", title: "Use a single-column layout", why: "Multi-column layouts confuse ATS parsers and can scramble your work history.", category: "formatting" },
    { id: "s4", severity: "medium", title: "Tailor your summary to the role", why: "Your summary is generic — mirror the job title and top 3 required skills.", category: "semantic" },
    { id: "s5", severity: "low", title: "Add project links", why: "Live demos or GitHub links raise credibility for developer roles.", category: "projects" },
    { id: "s6", severity: "low", title: "Order sections by relevance", why: "For this role, Skills and Projects should appear before Education.", category: "formatting" },
  ],
  missingSkills: ["TypeScript", "Jest", "CI/CD", "Accessibility", "Next.js"],
  createdAt: new Date().toISOString(),
};

export const roleSkillSuggestions: Record<string, string[]> = {
  "frontend developer": ["React", "TypeScript", "Next.js", "Tailwind CSS", "Jest", "Accessibility", "REST APIs", "Git"],
  "backend developer": ["Python", "FastAPI", "PostgreSQL", "Docker", "Redis", "REST APIs", "CI/CD", "AWS"],
  "data scientist": ["Python", "Pandas", "scikit-learn", "PyTorch", "SQL", "Statistics", "Data Visualization", "MLOps"],
  default: ["Communication", "Problem Solving", "Git", "Agile", "Teamwork"],
};

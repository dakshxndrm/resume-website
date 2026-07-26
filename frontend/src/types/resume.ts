/** Internal resume data model — JSON Resume schema subset (https://jsonresume.org/schema/) */
export interface ResumeBasics {
  name: string;
  label: string; // target job title
  email: string;
  phone?: string;
  url?: string;
  location?: string;
  summary?: string;
  /** Extra profile URLs (LinkedIn, GitHub, portfolio). Optional — older saved
   *  resumes without it still load, and the backend accepts any basics shape. */
  links?: string[];
}

export interface WorkItem {
  company: string;
  position: string;
  startDate: string;
  endDate?: string; // empty = present
  highlights: string[];
}

export interface EducationItem {
  institution: string;
  area: string;
  studyType: string;
  startDate: string;
  endDate?: string;
  score?: string;
}

export interface ProjectItem {
  name: string;
  description: string;
  highlights: string[];
  url?: string;
}

export interface Resume {
  id?: string;
  basics: ResumeBasics;
  work: WorkItem[];
  education: EducationItem[];
  projects: ProjectItem[];
  skills: string[];
  certifications: string[];
}

export interface CategoryScore {
  key: "skills" | "experience" | "semantic" | "projects" | "education" | "formatting";
  label: string;
  score: number; // 0-100
  weight: number; // e.g. 0.30
}

export interface Suggestion {
  id: string;
  severity: "high" | "medium" | "low";
  title: string;
  why: string;
  category: CategoryScore["key"];
}

export interface ScoreReport {
  id: string;
  resumeId?: string;
  jobTitle?: string;
  total: number; // 0-100
  verdict: string;
  categories: CategoryScore[];
  suggestions: Suggestion[];
  /** Whether `suggestions` came from the LLM or the rule-based fallback. */
  suggestionsSource?: "ai" | "rules";
  missingSkills: string[];
  createdAt: string;
}

export const emptyResume = (): Resume => ({
  basics: { name: "", label: "", email: "" },
  work: [],
  education: [],
  projects: [],
  skills: [],
  certifications: [],
});

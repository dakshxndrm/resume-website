"use client";
/** Skills as removable chips. Enter or the Add button commits; each chip has its
 *  own labelled remove button so the list is fully keyboard operable. */
import { useId, useState } from "react";
import { Plus, X } from "lucide-react";
import { Button } from "@/components/ui/Button";

export function SkillChips({
  skills, onChange, label = "Skills", hint,
}: {
  skills: string[];
  onChange: (skills: string[]) => void;
  label?: string;
  hint?: string;
}) {
  const [draft, setDraft] = useState("");
  const id = useId();

  const add = () => {
    // one paste of "React, Redux, Jest" should become three chips, not one
    const incoming = draft.split(",").map((s) => s.trim()).filter(Boolean);
    const merged = [...skills];
    for (const skill of incoming) {
      if (!merged.some((s) => s.toLowerCase() === skill.toLowerCase())) merged.push(skill);
    }
    onChange(merged);
    setDraft("");
  };

  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="text-sm font-medium text-secondary">{label}</label>
      {hint && <p id={`${id}-hint`} className="text-xs text-neutral">{hint}</p>}

      <div className="flex gap-2">
        <input
          id={id}
          value={draft}
          aria-describedby={hint ? `${id}-hint` : undefined}
          placeholder="e.g. PostgreSQL"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault(); // don't submit the surrounding form
              add();
            }
          }}
          className="focus-ring flex-1 rounded-btn border border-neutral/30 px-3.5 py-2.5 text-base outline-none transition-colors"
        />
        <Button variant="ghost" type="button" onClick={add} disabled={!draft.trim()}>
          <Plus className="h-4 w-4" aria-hidden />
          Add
        </Button>
      </div>

      {skills.length > 0 && (
        <ul className="mt-1 flex flex-wrap gap-2">
          {skills.map((skill) => (
            <li
              key={skill}
              className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 py-1 pl-3 pr-1.5 text-sm font-medium text-primary"
            >
              {skill}
              <button
                type="button"
                aria-label={`Remove ${skill}`}
                onClick={() => onChange(skills.filter((s) => s !== skill))}
                className="focus-ring rounded-full p-0.5 transition-colors hover:bg-primary/20"
              >
                <X className="h-3.5 w-3.5" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

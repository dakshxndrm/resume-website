"use client";
/** Add / remove / reorder wrapper shared by Experience, Education and Projects.
 *  Reorder is buttons, not drag-and-drop: keyboard and screen-reader usable, and
 *  no extra dependency. */
import type { ReactNode } from "react";
import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";

interface Props<T> {
  legend: string;
  items: T[];
  onChange: (items: T[]) => void;
  blank: () => T;
  addLabel: string;
  emptyHint: string;
  /** Label for one entry, used in the move/remove button aria-labels. */
  describe: (item: T, index: number) => string;
  children: (item: T, patch: (fields: Partial<T>) => void, index: number) => ReactNode;
}

export function RepeatableList<T>({
  legend, items, onChange, blank, addLabel, emptyHint, describe, children,
}: Props<T>) {
  const replace = (index: number, next: T) =>
    onChange(items.map((item, i) => (i === index ? next : item)));

  const move = (from: number, to: number) => {
    if (to < 0 || to >= items.length) return;
    const next = [...items];
    [next[from], next[to]] = [next[to], next[from]];
    onChange(next);
  };

  return (
    <fieldset className="flex flex-col gap-4">
      <legend className="mb-2 text-lg font-semibold">{legend}</legend>

      {items.length === 0 && <p className="text-sm text-neutral">{emptyHint}</p>}

      {items.map((item, i) => {
        const name = describe(item, i);
        return (
          <div key={i} className="rounded-card border border-neutral/15 bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-center justify-between gap-2">
              <span className="text-sm font-semibold text-neutral">{name}</span>
              <div className="flex items-center gap-1">
                <IconButton
                  label={`Move ${name} up`}
                  disabled={i === 0}
                  onClick={() => move(i, i - 1)}
                >
                  <ArrowUp className="h-4 w-4" aria-hidden />
                </IconButton>
                <IconButton
                  label={`Move ${name} down`}
                  disabled={i === items.length - 1}
                  onClick={() => move(i, i + 1)}
                >
                  <ArrowDown className="h-4 w-4" aria-hidden />
                </IconButton>
                <IconButton
                  label={`Remove ${name}`}
                  onClick={() => onChange(items.filter((_, j) => j !== i))}
                >
                  <Trash2 className="h-4 w-4 text-error" aria-hidden />
                </IconButton>
              </div>
            </div>

            <div className="flex flex-col gap-4">
              {children(item, (fields) => replace(i, { ...item, ...fields }), i)}
            </div>
          </div>
        );
      })}

      <div>
        <Button variant="ghost" type="button" onClick={() => onChange([...items, blank()])}>
          <Plus className="h-4 w-4" aria-hidden />
          {addLabel}
        </Button>
      </div>
    </fieldset>
  );
}

function IconButton({
  label, onClick, disabled, children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className="focus-ring rounded-btn p-2 text-neutral transition-colors hover:bg-surface hover:text-secondary disabled:cursor-not-allowed disabled:opacity-30"
    >
      {children}
    </button>
  );
}

"use client";
import { forwardRef, useId, type InputHTMLAttributes, type TextareaHTMLAttributes } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, className = "", ...rest }, ref) => {
    const id = useId();
    return (
      <div className="flex flex-col gap-1.5">
        <label htmlFor={id} className="text-sm font-medium text-secondary">
          {label}
        </label>
        <input
          id={id}
          ref={ref}
          aria-invalid={!!error}
          aria-describedby={error ? `${id}-err` : undefined}
          className={`focus-ring rounded-btn border px-3.5 py-2.5 text-base outline-none transition-colors ${
            error ? "border-error" : "border-neutral/30"
          } ${className}`}
          {...rest}
        />
        {error && (
          <p id={`${id}-err`} role="alert" className="text-sm text-error">
            {error}
          </p>
        )}
      </div>
    );
  }
);
Input.displayName = "Input";

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
  error?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ label, error, className = "", ...rest }, ref) => {
    const id = useId();
    return (
      <div className="flex flex-col gap-1.5">
        <label htmlFor={id} className="text-sm font-medium text-secondary">
          {label}
        </label>
        <textarea
          id={id}
          ref={ref}
          aria-invalid={!!error}
          className={`focus-ring min-h-28 rounded-btn border px-3.5 py-2.5 text-base outline-none transition-colors ${
            error ? "border-error" : "border-neutral/30"
          } ${className}`}
          {...rest}
        />
        {error && (
          <p role="alert" className="text-sm text-error">
            {error}
          </p>
        )}
      </div>
    );
  }
);
Textarea.displayName = "Textarea";

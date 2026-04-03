import { cn } from "@/lib/utils";
import { Check, ChevronDown } from "lucide-react";
import { forwardRef, useEffect, useRef, useState } from "react";

// ── Native select (compact pagination use) ─────────────────────────

type NativeSelectProps = React.SelectHTMLAttributes<HTMLSelectElement> & {
  compact?: boolean;
};

const Select = forwardRef<HTMLSelectElement, NativeSelectProps>(
  ({ className, compact, children, ...props }, ref) => {
    return (
      <div className="relative">
        <select
          ref={ref}
          className={cn(
            "w-full appearance-none rounded-lg border border-input bg-background text-sm outline-none transition-shadow cursor-pointer",
            "hover:border-muted-foreground/40",
            "focus:ring-2 focus:ring-ring/40 focus:border-ring/60",
            "disabled:cursor-not-allowed disabled:opacity-50",
            compact
              ? "py-1 pl-2 pr-7"
              : "py-2.5 pl-3 pr-9",
            className,
          )}
          {...props}
        >
          {children}
        </select>
        <ChevronDown
          className={cn(
            "pointer-events-none absolute top-1/2 -translate-y-1/2 text-muted-foreground/60",
            compact ? "right-1.5 h-3 w-3" : "right-2.5 h-4 w-4",
          )}
        />
      </div>
    );
  },
);

Select.displayName = "Select";

// ── Custom dropdown select ──────────────────────────────────────────

type Option = {
  value: string | number;
  label: string;
};

type CustomSelectProps = {
  options: Option[];
  value: string | number;
  onChange: (value: string | number) => void;
  placeholder?: string;
  className?: string;
  disabled?: boolean;
};

function CustomSelect({
  options,
  value,
  onChange,
  placeholder = "Select...",
  className,
  disabled,
}: CustomSelectProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open]);

  const selected = options.find((o) => o.value === value);

  return (
    <div ref={ref} className={cn("relative", className)}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "flex w-full items-center justify-between rounded-lg border border-input bg-background px-3 py-2.5 text-sm outline-none transition-shadow cursor-pointer",
          "hover:border-muted-foreground/40",
          "focus:ring-2 focus:ring-ring/40 focus:border-ring/60",
          "disabled:cursor-not-allowed disabled:opacity-50",
          open && "ring-2 ring-ring/40 border-ring/60",
        )}
      >
        <span className={cn(!selected && "text-muted-foreground")}>
          {selected?.label ?? placeholder}
        </span>
        <ChevronDown
          className={cn(
            "h-4 w-4 text-muted-foreground/60 transition-transform duration-200",
            open && "rotate-180",
          )}
        />
      </button>

      {open && (
        <div className="absolute left-0 z-50 mt-1.5 max-h-60 w-full overflow-auto rounded-xl border border-border bg-card shadow-lg animate-enter origin-top">
          {options.map((opt, i) => {
            const isSelected = opt.value === value;
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => {
                  onChange(opt.value);
                  setOpen(false);
                }}
                className={cn(
                  "flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm transition-colors",
                  "hover:bg-accent",
                  isSelected && "font-medium text-primary",
                  i === 0 && "rounded-t-xl",
                  i === options.length - 1 && "rounded-b-xl",
                )}
              >
                <span className="flex h-4 w-4 shrink-0 items-center justify-center">
                  {isSelected && <Check className="h-3.5 w-3.5 text-primary" />}
                </span>
                {opt.label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export { Select, CustomSelect };

import React, { useState } from "react";
import { format, parseISO, isValid } from "date-fns";
import { Calendar as CalendarIcon } from "lucide-react";
import { get } from "lodash";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useContent } from "@/context/ContentContext";

// Presentational date picker. value/onChange use "YYYY-MM-DD" strings.
export function DatePicker({ value, onChange, testId, placeholder = "Pick a date", className = "" }) {
  const [open, setOpen] = useState(false);
  const parsed = value ? parseISO(value) : undefined;
  const selected = parsed && isValid(parsed) ? parsed : undefined;
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          data-testid={testId}
          className={`editable-input inline-flex items-center gap-2 text-left ${className}`}
        >
          <CalendarIcon className="w-4 h-4 text-blue-900 flex-shrink-0" />
          <span className={selected ? "text-slate-900" : "text-slate-400"}>
            {selected ? format(selected, "PPP") : placeholder}
          </span>
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          mode="single"
          selected={selected}
          defaultMonth={selected}
          onSelect={(d) => {
            if (d) onChange(format(d, "yyyy-MM-dd"));
            setOpen(false);
          }}
          initialFocus
        />
      </PopoverContent>
    </Popover>
  );
}

// Content-bound date picker: reads/writes portal content at `path`.
export function EDatePicker({ path, testId, placeholder = "Pick a date" }) {
  const { content, editMode, update } = useContent();
  const value = get(content, path) || "";
  if (!editMode) {
    const parsed = value ? parseISO(value) : undefined;
    const nice = parsed && isValid(parsed) ? format(parsed, "PPP") : value || "—";
    return <span data-testid={`content-${path}`} className="text-lg text-slate-900">{nice}</span>;
  }
  return <DatePicker value={value} onChange={(v) => update(path, v)} testId={testId || `edit-${path}`} placeholder={placeholder} />;
}

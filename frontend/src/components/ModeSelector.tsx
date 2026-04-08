import { Info } from "lucide-react";
import type { SearchMode } from "@/types/api";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface ModeSelectorProps {
  value: SearchMode;
  onChange: (mode: SearchMode) => void;
  disabled?: boolean;
}

const modes: { value: SearchMode; label: string; tooltip: string }[] = [
  {
    value: "semantic",
    label: "Semantic",
    tooltip: "Best for concepts and themes",
  },
  {
    value: "keyword",
    label: "Keyword",
    tooltip: "Best for exact words and names",
  },
  {
    value: "hybrid",
    label: "Hybrid",
    tooltip: "Combines both approaches (recommended)",
  },
];

export function ModeSelector({ value, onChange, disabled }: ModeSelectorProps) {
  return (
    <div
      className="flex items-center justify-center gap-2 flex-wrap"
      role="radiogroup"
      aria-label="Search mode"
    >
      {modes.map((mode) => (
        <div key={mode.value} className="flex items-center gap-1">
          <button
            onClick={() => onChange(mode.value)}
            disabled={disabled}
            className={`pill-button ${
              value === mode.value
                ? "pill-button-active"
                : "pill-button-inactive"
            } disabled:opacity-50`}
            role="radio"
            aria-checked={value === mode.value}
          >
            {mode.label}
          </button>
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                className="p-1 text-muted-foreground hover:text-foreground transition-colors"
                aria-label={`Info about ${mode.label} mode`}
              >
                <Info className="h-4 w-4" />
              </button>
            </TooltipTrigger>
            <TooltipContent>
              <p>{mode.tooltip}</p>
            </TooltipContent>
          </Tooltip>
        </div>
      ))}
    </div>
  );
}

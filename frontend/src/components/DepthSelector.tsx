import { Info } from "lucide-react";
import type { AnalysisDepth } from "@/types/api";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface DepthSelectorProps {
  value: AnalysisDepth;
  onChange: (depth: AnalysisDepth) => void;
  disabled?: boolean;
}

const depths: { value: AnalysisDepth; label: string; tooltip: string }[] = [
  {
    value: "quick",
    label: "Quick",
    tooltip: "~7 verses, faster response",
  },
  {
    value: "balanced",
    label: "Balanced",
    tooltip: "~12 verses, recommended",
  },
  {
    value: "comprehensive",
    label: "Comprehensive",
    tooltip: "~20 verses, deep analysis",
  },
];

export function DepthSelector({ value, onChange, disabled }: DepthSelectorProps) {
  return (
    <div className="space-y-2">
      <label className="block text-sm font-semibold text-foreground">
        Analysis Depth:
      </label>
      <div
        className="flex items-center justify-center gap-2 flex-wrap"
        role="radiogroup"
        aria-label="Analysis depth"
      >
        {depths.map((depth) => (
          <div key={depth.value} className="flex items-center gap-1">
            <button
              onClick={() => onChange(depth.value)}
              disabled={disabled}
              className={`pill-button text-xs ${
                value === depth.value
                  ? "pill-button-active"
                  : "pill-button-inactive"
              } disabled:opacity-50`}
              role="radio"
              aria-checked={value === depth.value}
            >
              {depth.label}
            </button>
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  className="p-0.5 text-muted-foreground hover:text-foreground transition-colors"
                  aria-label={`Info about ${depth.label} depth`}
                >
                  <Info className="h-3 w-3" />
                </button>
              </TooltipTrigger>
              <TooltipContent>
                <p>{depth.tooltip}</p>
              </TooltipContent>
            </Tooltip>
          </div>
        ))}
      </div>
    </div>
  );
}

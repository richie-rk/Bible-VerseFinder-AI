import { AlertTriangle, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";

interface ErrorBannerProps {
  message: string;
  details?: string;
  onRetry?: () => void;
  isRetrying?: boolean;
}

export function ErrorBanner({
  message,
  details,
  onRetry,
  isRetrying,
}: ErrorBannerProps) {
  const [showDetails, setShowDetails] = useState(false);

  return (
    <div
      className="bg-destructive/10 border border-destructive/20 rounded-lg p-4 mb-4"
      role="alert"
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="h-5 w-5 text-destructive flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          <p className="text-sm font-medium text-destructive">{message}</p>

          {details && (
            <button
              onClick={() => setShowDetails(!showDetails)}
              className="flex items-center gap-1 text-xs text-destructive/70 mt-2 hover:text-destructive transition-colors"
            >
              {showDetails ? (
                <>
                  <ChevronUp className="h-3 w-3" />
                  Hide details
                </>
              ) : (
                <>
                  <ChevronDown className="h-3 w-3" />
                  Show details
                </>
              )}
            </button>
          )}

          {showDetails && details && (
            <pre className="mt-2 p-2 bg-destructive/5 rounded text-xs text-destructive/80 overflow-x-auto">
              {details}
            </pre>
          )}

          {onRetry && (
            <button
              onClick={onRetry}
              disabled={isRetrying}
              className="flex items-center gap-2 mt-3 px-4 py-2 bg-destructive text-destructive-foreground rounded-lg text-sm font-medium hover:bg-destructive/90 transition-colors disabled:opacity-50"
            >
              <RefreshCw
                className={`h-4 w-4 ${isRetrying ? "animate-spin" : ""}`}
              />
              {isRetrying ? "Retrying..." : "Try Again"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

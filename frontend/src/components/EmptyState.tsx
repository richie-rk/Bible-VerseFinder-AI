import { BookOpen } from "lucide-react";

interface EmptyStateProps {
  onExampleClick: (query: string) => void;
}

const examples = [
  "What is grace?",
  "How to overcome fear",
  "Love your neighbor",
  "Faith and works",
];

export function EmptyState({ onExampleClick }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center text-center px-4 py-16 animate-[scaleIn_0.3s_ease-out]">
      <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mb-6">
        <BookOpen className="h-8 w-8 text-primary" aria-hidden="true" />
      </div>

      <h2 className="text-2xl font-bold text-primary mb-2">
        Discover what the Bible says
      </h2>

      <p className="text-base text-muted-foreground mb-8">
        Search any topic, question, or theme
      </p>

      <div className="flex flex-wrap items-center justify-center gap-2 max-w-md">
        {examples.map((example) => (
          <button
            key={example}
            onClick={() => onExampleClick(example)}
            className="px-4 py-2.5 rounded-full text-sm font-medium border border-primary text-primary bg-card hover:bg-primary hover:text-primary-foreground transition-all duration-200 hover-scale"
          >
            {example}
          </button>
        ))}
      </div>
    </div>
  );
}

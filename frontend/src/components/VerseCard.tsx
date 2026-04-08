import { useState, useMemo } from "react";
import { Heart, Copy, Share2, Check } from "lucide-react";
import type { VerseResult } from "@/types/api";
import { useFavorites } from "@/hooks/useFavorites";
import { useToast } from "@/hooks/use-toast";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { parseVerseId } from "@/lib/api";

interface VerseCardProps {
  verse: VerseResult;
  onClick: () => void;
  showRank?: boolean;
}

export function VerseCard({ verse, onClick, showRank = true }: VerseCardProps) {
  const [copied, setCopied] = useState(false);
  const { isFavorite, toggleFavorite } = useFavorites();
  const { toast } = useToast();
  const favorite = isFavorite(verse.verse_id);

  // Parse chapter and verse from verse_id
  const { chapter, verse: verseNum } = useMemo(
    () => parseVerseId(verse.verse_id),
    [verse.verse_id]
  );

  const reference = `${verse.book} ${chapter}:${verseNum}`;
  const scorePercent = Math.min(100, Math.round(verse.score * 100));

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(`${reference}\n${verse.text}`);
      setCopied(true);
      toast({
        description: "Copied to clipboard",
      });
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast({
        variant: "destructive",
        description: "Failed to copy",
      });
    }
  };

  const handleFavorite = (e: React.MouseEvent) => {
    e.stopPropagation();
    toggleFavorite(verse.verse_id);
  };

  const handleShare = async (e: React.MouseEvent) => {
    e.stopPropagation();
    const shareText = `${reference} - ${verse.text}`;
    try {
      if (navigator.share) {
        await navigator.share({ text: shareText });
      } else {
        await navigator.clipboard.writeText(shareText);
        toast({
          description: "Copied to clipboard for sharing",
        });
      }
    } catch {
      // User cancelled or error
    }
  };

  // Truncate text
  const maxLength = 200;
  const truncatedText =
    verse.text.length > maxLength
      ? verse.text.slice(0, maxLength) + "..."
      : verse.text;
  const isTruncated = verse.text.length > maxLength;

  return (
    <article
      className="verse-card group"
      onClick={onClick}
      onKeyDown={(e) => e.key === "Enter" && onClick()}
      tabIndex={0}
      role="button"
      aria-label={`${reference}: ${verse.text.slice(0, 50)}...`}
    >
      {/* Top row */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-primary font-bold text-base">{reference}</span>
          <span className="px-2 py-0.5 bg-muted text-muted-foreground text-xs rounded">
            {verse.book}
          </span>
        </div>
        {showRank && (
          <span className="flex-shrink-0 w-7 h-7 rounded-full bg-primary text-primary-foreground text-sm font-semibold flex items-center justify-center">
            {verse.rank}
          </span>
        )}
      </div>

      {/* Verse text */}
      <p className="text-[15px] leading-relaxed text-foreground mb-3">
        {truncatedText}
        {isTruncated && (
          <span className="text-primary text-sm ml-1 hover:underline">
            Read more →
          </span>
        )}
      </p>

      {/* Bottom row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* Match score */}
          <div className="flex items-center gap-2">
            <div className="w-16 h-1.5 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-primary transition-all duration-300"
                style={{ width: `${scorePercent}%` }}
              />
            </div>
            <span className="text-xs text-muted-foreground">
              {scorePercent}% match
            </span>
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                onClick={handleFavorite}
                className="p-1.5 rounded hover:bg-muted transition-colors"
                aria-label={favorite ? "Remove from favorites" : "Add to favorites"}
              >
                <Heart
                  className={`h-4 w-4 ${
                    favorite ? "fill-red-500 text-red-500" : "text-muted-foreground"
                  }`}
                />
              </button>
            </TooltipTrigger>
            <TooltipContent>
              {favorite ? "Remove from favorites" : "Add to favorites"}
            </TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <button
                onClick={handleCopy}
                className="p-1.5 rounded hover:bg-muted transition-colors"
                aria-label="Copy to clipboard"
              >
                {copied ? (
                  <Check className="h-4 w-4 text-green-500" />
                ) : (
                  <Copy className="h-4 w-4 text-muted-foreground" />
                )}
              </button>
            </TooltipTrigger>
            <TooltipContent>Copy to clipboard</TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <button
                onClick={handleShare}
                className="p-1.5 rounded hover:bg-muted transition-colors"
                aria-label="Share verse"
              >
                <Share2 className="h-4 w-4 text-muted-foreground" />
              </button>
            </TooltipTrigger>
            <TooltipContent>Share verse</TooltipContent>
          </Tooltip>
        </div>
      </div>

      {/* Click hint */}
      <p className="text-xs text-muted-foreground italic mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
        Click for chapter context
      </p>
    </article>
  );
}

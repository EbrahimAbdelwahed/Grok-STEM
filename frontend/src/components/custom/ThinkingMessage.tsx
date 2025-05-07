// frontend/src/components/custom/ThinkingMessage.tsx
import React from 'react';

// Update Phase type to include new steps
export type Phase = 'cache_check' | 'retrieval' | 'reasoning' | 'steps' | 'plotting' | 'image_generation';

interface ThinkingMessageProps {
  phase: Phase | null; // Allow null phase
}

// Add labels for new phases
const phaseLabels: Record<Phase, string> = {
  cache_check: 'Checking cache...',
  retrieval: '🔍 Searching knowledge base...',
  reasoning: '🧠 Reasoning...',
  steps: '🪜 Organizing steps...',
  plotting: '📊 Generating plot...',
  image_generation: '🖼️ Generating image...',
};

export const ThinkingMessage: React.FC<ThinkingMessageProps> = ({ phase }) => {
  if (!phase) return null; // Don't render if phase is null

  return (
    <div className="flex items-center space-x-2 p-2 text-sm italic text-muted-foreground">
      <svg
        className="animate-spin h-4 w-4 text-muted-foreground" // Use muted foreground color
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
      >
        <circle
          className="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="4"
        ></circle>
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" // Improved spinner shape
        ></path>
      </svg>
      <span>{phaseLabels[phase] || 'Processing...'}</span> {/* Fallback label */}
    </div>
  );
};
// frontend/src/components/custom/ThinkingMessage.tsx
import React from 'react';

interface ThinkingMessageProps {
  phase: 'reasoning' | 'steps' | 'plotting';
}

const phaseLabels: Record<ThinkingMessageProps['phase'], string> = {
  reasoning: '🧠 Reasoning...',
  steps: '🪜 Organizing steps...',
  plotting: '📊 Generating plot...',
};

export const ThinkingMessage: React.FC<ThinkingMessageProps> = ({ phase }) => {
  return (
    <div className="flex items-center space-x-2 p-2 text-sm italic text-gray-500 dark:text-gray-400">
      <svg
        className="animate-spin h-4 w-4 text-gray-400"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
      >
        <circle
          className=" opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="4"
        ></circle>
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8v8H4z"
        ></path>
      </svg>
      <span>{phaseLabels[phase]}</span>
    </div>
  );
};

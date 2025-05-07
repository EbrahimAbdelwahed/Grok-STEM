// frontend/src/components/custom/ChatMessage.tsx
import React from 'react';
import { MarkdownRenderer } from './MarkdownRenderer';
import { AlertTriangle } from 'lucide-react';

interface ChatMessageProps {
  content: string;
  isError?: boolean;
  errorContent?: string | null; // Optional specific error content
}

export const ChatMessage: React.FC<ChatMessageProps> = ({
    content,
    isError = false,
    errorContent = "An error occurred."
}) => {

  if (isError) {
    return (
      <div className="p-3 my-1 rounded-lg bg-destructive/10 text-destructive dark:bg-destructive/20">
        <div className="flex items-start space-x-2">
            <AlertTriangle className="h-5 w-5 mt-0.5 shrink-0" />
            <div className="flex-1">
                <p className="font-medium text-sm">Error</p>
                <p className="text-xs">{content || errorContent}</p>
            </div>
        </div>
      </div>
    );
  }

  // Render normal message content using Markdown
  return (
    <div className="prose dark:prose-invert max-w-none prose-p:my-2 prose-ul:my-2 prose-li:my-1">
        {/* Render markdown content */}
        <MarkdownRenderer source={content} />
    </div>
  );
};

// No default export needed if using named export consistently
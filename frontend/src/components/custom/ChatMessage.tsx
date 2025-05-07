// frontend/src/components/custom/ChatMessage.tsx
import React, { useState } from 'react';
import { MarkdownRenderer } from './MarkdownRenderer';
import { Button } from '../ui/button';
import { ChevronDown, ChevronUp } from 'lucide-react';

interface ChatMessageProps {
  content: string;
  isError?: boolean;
  isMeta?: boolean;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ content, isError = false, isMeta = false }) => {
  const [expanded, setExpanded] = useState(false);
  const toggleExpanded = () => setExpanded((prev) => !prev);

  // If meta (steps placeholder), render differently
  if (isMeta) {
    return (
      <div className="p-2 my-2 bg-gray-100 dark:bg-gray-700 rounded">
        <em className="text-sm text-gray-600 dark:text-gray-300">{content}</em>
      </div>
    );
  }

  return (
    <div
      className={`p-4 my-2 rounded-lg ${
        isError
          ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300'
          : 'bg-white text-gray-900 dark:bg-gray-800 dark:text-gray-100'
      }`}
    >
      <div className="prose dark:prose-invert">
        <MarkdownRenderer source={content} />
      </div>
      {/* Collapsible Raw Content for 'show your work' */}
      {!isError && (
        <div className="mt-2">
          <Button
            size="sm"
            variant="outline"
            onClick={toggleExpanded}
            className="flex items-center"
          >
            {expanded ? <ChevronUp className="mr-1" /> : <ChevronDown className="mr-1" />}
            {expanded ? 'Hide reasoning details' : 'Show reasoning details'}
          </Button>
          {expanded && (
            <pre className="mt-2 p-2 bg-gray-50 dark:bg-gray-700 rounded overflow-auto text-xs">
              {content}
            </pre>
          )}
        </div>
      )}
    </div>
  );
};

export default ChatMessage;
// This component is a simple chat message renderer that supports Markdown rendering and collapsible sections for detailed content.
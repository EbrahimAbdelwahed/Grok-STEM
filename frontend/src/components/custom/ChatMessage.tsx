// frontend/src/components/custom/ChatMessage.tsx

import React from 'react';
import { motion } from 'framer-motion';
import { cn } from '../../lib/utils';
import { BotMessageSquare, User } from 'lucide-react'; // Standard icons
import { EnhancedMessage } from "../../interfaces/interfaces"; // Use the enhanced interface
import { MarkdownRenderer } from './MarkdownRenderer';   // Renders markdown text
import { PlotDisplay } from './PlotDisplay';         // Renders the Plotly chart
import { StepNavigator } from './StepNavigator';     // Renders the step list
// Import ThinkingMessage for potential use elsewhere or if refactoring loading state
export { ThinkingMessage } from './ThinkingMessage';

interface ChatMessageProps {
  message: EnhancedMessage;
  scrollToStep: (stepId: string) => void; // Function to handle step navigation clicks
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message, scrollToStep }) => {
  const isUser = message.role === 'user';
  const isAssistant = message.role === 'assistant';

  // Determine if there is any content to render at all
  const hasContent = !!message.text_content || !!message.plotly_json || (!!message.steps && message.steps.length > 0);

  if (!hasContent) {
    // Don't render completely empty message shells
    // Log in dev mode if this happens unexpectedly
    if (process.env.NODE_ENV === 'development') {
        console.warn("Skipping render for empty message object:", message);
    }
    return null;
  }

  console.debug("Rendering ChatMessage:", message);  // NEW

  return (
    <motion.div
      className={cn(
        "flex w-full items-start gap-3 px-4 group/message",
        isUser ? "justify-end" : "justify-start"
      )}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      layout // Animate layout changes
    >
      {/* Assistant Icon */}
      {isAssistant && (
        <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center ring-1 ring-inset ring-primary/20 mt-1">
          <BotMessageSquare className="h-5 w-5 text-primary" />
        </div>
      )}

      {/* Message Content Bubble */}
      <div
        // Apply max-width to the bubble itself, not the flex container
        className={cn(
          "flex flex-col", // Stack content vertically
          "rounded-lg p-3 shadow-sm",
           "max-w-[85%] md:max-w-[75%]", // Limit bubble width
          isUser
            ? "bg-primary text-primary-foreground order-last"
            : "bg-card text-card-foreground border order-first"
        )}
      >
        {/* 1. Render Text Content (always check if it exists) */}
        {message.text_content && (
           <MarkdownRenderer>{message.text_content}</MarkdownRenderer>
        )}

        {/* 2. Render Plot (only for assistant, if data exists) */}
        {isAssistant && message.plotly_json && (
          <PlotDisplay plotlyData={message.plotly_json} />
        )}

        {/* 3. Render Step Navigator (only for assistant, if steps exist) */}
        {isAssistant && message.steps && message.steps.length > 0 && (
           <StepNavigator steps={message.steps} scrollToStep={scrollToStep} />
        )}

        {/* --- Placeholder for future actions --- */}
        {/* {isAssistant && !isLoading && <MessageActions message={message} />} */}
      </div>

      {/* User Icon */}
      {isUser && (
         <div className="flex-shrink-0 w-8 h-8 rounded-full bg-muted flex items-center justify-center ring-1 ring-inset ring-border mt-1 order-first">
           <User className="h-5 w-5 text-muted-foreground" />
         </div>
      )}
    </motion.div>
  );
};
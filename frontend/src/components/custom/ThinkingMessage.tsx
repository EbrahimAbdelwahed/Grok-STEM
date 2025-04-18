// frontend/src/components/custom/ThinkingMessage.tsx
import React from 'react';
import { motion } from 'framer-motion';
import { BotMessageSquare } from 'lucide-react'; // Using Bot icon

export const LoadingDots: React.FC = () => (
  <span className="inline-flex items-center gap-1 ml-1">
    {[0, 1, 2].map((dot) => (
      <motion.span
        key={dot}
        className="w-1.5 h-1.5 bg-primary rounded-full" // Slightly larger dots
        initial={{ opacity: 0.2 }}
        animate={{ opacity: 1 }}
        transition={{
          duration: 0.6, // Slightly slower animation
          repeat: Infinity,
          repeatType: "reverse",
          delay: dot * 0.2
        }}
      />
    ))}
  </span>
);


export const ThinkingMessage: React.FC = () => {
  return (
    <motion.div
      className="flex items-start gap-3 px-4 w-full max-w-3xl mx-auto"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      {/* Icon */}
      <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center ring-1 ring-inset ring-primary/20">
         <BotMessageSquare className="h-5 w-5 text-primary" />
      </div>
      {/* Message Bubble */}
      <div className="flex-1 overflow-hidden">
        <div className="rounded-lg bg-muted p-3">
          <p className="text-sm text-muted-foreground italic">
            Grokking the problem...
            <LoadingDots />
          </p>
        </div>
      </div>
    </motion.div>
  );
};
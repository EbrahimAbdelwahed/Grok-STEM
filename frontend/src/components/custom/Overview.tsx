// frontend/src/components/custom/Overview.tsx
import React from 'react';
import { motion } from 'framer-motion';
import { BotMessageSquare, FlaskConical } from 'lucide-react'; // Or other relevant icons

export const Overview: React.FC = () => {
  return (
    <motion.div
      key="overview"
      className="flex flex-col items-center justify-center h-full px-4 text-center"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }} // Changed exit animation slightly
      transition={{ duration: 0.5 }}
    >
      <div className="max-w-xl flex flex-col items-center gap-4">
        <div className="flex items-center justify-center gap-3 text-grokstem">
           <BotMessageSquare size={40}/>
           <span className="text-2xl font-bold text-foreground">+</span>
           <FlaskConical size={40}/>
        </div>
        <h2 className="text-2xl font-semibold text-foreground mt-2">
          Welcome to GrokSTEM!
        </h2>
        <p className="text-muted-foreground leading-relaxed">
          Ask me any STEM question (Physics, Chemistry, Math, etc.). I'll provide step-by-step reasoning and generate plots when helpful.
        </p>
        <p className="text-sm text-muted-foreground/80">
          Example: "What is the escape velocity of Earth?" or "Plot y = x^2 from -5 to 5".
        </p>
        {/* Placeholder for suggested prompts if ChatInput doesn't handle them */}
      </div>
    </motion.div>
  );
};
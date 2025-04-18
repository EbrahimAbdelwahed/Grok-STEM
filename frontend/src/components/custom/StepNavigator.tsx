// frontend/src/components/custom/StepNavigator.tsx
import React from 'react';
import { ListOrdered } from 'lucide-react';
import { ReasoningStep } from '../../interfaces/interfaces';
import { cn } from '../../lib/utils';

interface StepNavigatorProps {
  steps: ReasoningStep[];
  scrollToStep: (stepId: string) => void;
  className?: string;
}

export const StepNavigator: React.FC<StepNavigatorProps> = ({ steps, scrollToStep, className }) => {
  if (!steps || steps.length === 0) {
    return null; // Don't render if there are no steps
  }

  return (
    <div className={cn("mt-4 mb-2 p-3 border rounded-md bg-muted/50 dark:bg-secondary/30", className)}>
      <h4 className="flex items-center text-sm font-semibold mb-2 text-foreground">
        <ListOrdered className="w-4 h-4 mr-2" />
        Solution Steps:
      </h4>
      <ol className="space-y-1 text-sm list-none pl-1"> {/* Use list-none if numbering comes from title */}
        {steps.map((step) => (
          <li key={step.id}>
            <button
              onClick={() => scrollToStep(step.id)}
              className="text-primary hover:underline text-left hover:text-primary/80 transition-colors duration-150"
              title={`Go to ${step.title}`} // Accessibility
            >
              {step.title}
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
};
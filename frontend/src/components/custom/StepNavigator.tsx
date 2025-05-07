// frontend/src/components/custom/StepNavigator.tsx
import React from 'react';

interface Step {
  id: string;
  title: string;
}

interface StepNavigatorProps {
  steps: Step[];
}

export const StepNavigator: React.FC<StepNavigatorProps> = ({ steps }) => {
  const handleClick = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow p-4 space-y-2">
      <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-2">Steps</h3>
      <ul className="space-y-1">
        {steps.map((step) => (
          <li key={step.id}>
            <button
              onClick={() => handleClick(step.id)}
              className="text-left w-full text-sm text-blue-600 dark:text-blue-400 hover:underline"
            >
              {step.title}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
};

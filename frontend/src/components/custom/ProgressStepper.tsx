// frontend/src/components/custom/ProgressStepper.tsx
import React from 'react';
import { motion } from 'framer-motion';

export type Phase = 'reasoning' | 'steps' | 'plotting' | 'done';

interface ProgressStepperProps {
  currentPhase: Phase;
}

const phases = [
  { key: 'reasoning', label: 'Reasoning', icon: '🧠' },
  { key: 'steps', label: 'Steps', icon: '🪜' },
  { key: 'plotting', label: 'Plotting', icon: '📊' },
];

export const ProgressStepper: React.FC<ProgressStepperProps> = ({ currentPhase }) => {
  const getStatus = (phaseKey: string) => {
    const order = ['reasoning', 'steps', 'plotting'];
    const currentIndex = currentPhase === 'done' ? order.length : order.indexOf(currentPhase);
    const phaseIndex = order.indexOf(phaseKey);
    if (phaseIndex < currentIndex) return 'complete';
    if (phaseIndex === currentIndex) return 'active';
    return 'upcoming';
  };

  return (
    <div className="flex items-center space-x-4 p-2 bg-gray-50 dark:bg-gray-900 rounded-lg">
      {phases.map(({ key, label, icon }) => {
        const status = getStatus(key);
        return (
          <div key={key} className="flex items-center space-x-2">
            <motion.div
              initial={{ scale: status === 'active' ? 1 : 0.8, opacity: status === 'upcoming' ? 0.5 : 1 }}
              animate={{ scale: status === 'active' ? 1.2 : 1, opacity: status === 'upcoming' ? 0.5 : 1 }}
              transition={{ duration: 0.3 }}
              className={`text-xl rounded-full w-8 h-8 flex items-center justify-center
                ${status === 'complete' ? 'bg-green-500 text-white' : ''}
                ${status === 'active' ? 'bg-blue-500 text-white' : ''}
                ${status === 'upcoming' ? 'bg-gray-300 dark:bg-gray-700 text-gray-500' : ''}`}
            >
              {icon}
            </motion.div>
            <span className={`text-sm font-medium
              ${status === 'active' ? 'text-blue-600 dark:text-blue-400' : 'text-gray-600 dark:text-gray-400'}`}
            >{label}</span>
          </div>
        );
      })}
      {currentPhase === 'done' && (
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.3 }}
          className="ml-auto text-green-500 font-semibold flex items-center space-x-1"
        >
          <span>✅</span>
          <span>Done</span>
        </motion.div>
      )}
    </div>
  );
};

import React from 'react';
import { ThemeToggle } from "./ThemeToggle";
import { BotMessageSquare } from 'lucide-react'; // Or your custom Logo component

export const Header: React.FC = () => {
  return (
    <header className="sticky top-0 z-40 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 shrink-0"> {/* Add shrink-0 */}
      <div className="container flex h-14 items-center justify-between px-4"> {/* Use container for consistent padding */}
        <div className="flex items-center space-x-2">
          {/* Apply custom GrokSTEM color using Tailwind variable */}
          <BotMessageSquare className="h-6 w-6 text-[hsl(var(--grokstem))]" />
          <span className="font-bold text-lg">GrokSTEM</span>
        </div>
        <ThemeToggle />
      </div>
    </header>
  );
};
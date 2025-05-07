// frontend/src/components/custom/ChatInput.tsx
import React, { useState, useRef, useEffect } from 'react';
import { Textarea } from "../ui/textarea";
import { cn } from "../../lib/utils";
import { Button } from "../ui/button";
import { ArrowUp, Info, FunctionSquare } from "lucide-react";
import { Popover, PopoverTrigger, PopoverContent } from "../ui/popover";
import { motion } from 'framer-motion';

interface ChatInputProps {
  input: string;
  setInput: (input: string) => void;
  onSubmit: (text?: string) => void;
  isLoading: boolean;
  isConnected: boolean;
}

const templates = [
  { label: 'Projectile Motion', action: 'A ball is thrown at 20 m/s at an angle of 30 degrees. Calculate its range and maximum height.' },
  { label: 'Ideal Gas Law', action: 'What is the volume of 1 mole of an ideal gas at STP (Standard Temperature and Pressure)?' },
  { label: 'Derivative', action: 'Find the derivative of f(x) = x^3 + 2x^2 - 5x + 1' },
  { label: 'Plot Function', action: 'Plot the function y = sin(x) for x from -2*pi to 2*pi' },
];

export const ChatInput: React.FC<ChatInputProps> = ({ input, setInput, onSubmit, isLoading, isConnected }) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [showTemplates, setShowTemplates] = useState(false);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      const maxHeight = 200;
      textarea.style.height = `${Math.min(textarea.scrollHeight, maxHeight)}px`;
    }
  }, [input]);

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
  };

  const handleSend = () => {
    if (input.trim()) {
      onSubmit(input.trim());
    }
  };

  const wrapMath = () => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const before = input.slice(0, start);
    const selected = input.slice(start, end);
    const after = input.slice(end);
    const wrapped = `${before}$$${selected || '\quad'}$$${after}`;
    setInput(wrapped);
    // Place cursor inside math
    const cursorPos = start + 2 + (selected ? 0 : 1);
    setTimeout(() => textarea.setSelectionRange(cursorPos, cursorPos + (selected.length || 0)), 0);
    textarea.focus();
  };

  const handleTemplateSelect = (action: string) => {
    setInput(action);
    setShowTemplates(false);
    textareaRef.current?.focus();
  };

  return (
    <div className="relative">
      <div className="flex items-center space-x-2 mb-2">
        <Popover open={showTemplates} onOpenChange={setShowTemplates}>
          <PopoverTrigger asChild>
            <Button size="sm" variant="outline" aria-label="Insert template">
              <FunctionSquare className="h-4 w-4" /> Templates
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-56 p-2">
            {templates.map((t) => (
              <button
                key={t.label}
                className="block w-full text-left px-2 py-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700"
                onClick={() => handleTemplateSelect(t.action)}
              >
                <span className="font-medium">{t.label}</span>
                <p className="text-xs text-muted-foreground">{t.action}</p>
              </button>
            ))}
          </PopoverContent>
        </Popover>
        <Button size="sm" variant="outline" onClick={wrapMath} aria-label="Wrap math">
          <span className="text-xl">∫</span>
        </Button>
      </div>
      <div className="relative flex items-end rounded-lg border bg-background focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 focus-within:ring-offset-background">
        <Textarea
          ref={textareaRef}
          placeholder={isConnected ? "Ask a STEM question..." : "Connecting..."}
          className="flex-1 resize-none border-0 shadow-none focus-visible:ring-0 bg-transparent pr-12 py-2 min-h-[40px] max-h-[200px]"
          value={input}
          onChange={handleInputChange}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey && !isLoading && isConnected) { e.preventDefault(); handleSend(); } }}
          disabled={!isConnected || isLoading}
          aria-label="Chat input"
        />
        <Button
          size="icon"
          className="absolute bottom-1.5 right-1.5 rounded-lg w-8 h-8"
          onClick={handleSend}
          disabled={!input.trim() || isLoading || !isConnected}
          aria-label="Send message"
        >
          <ArrowUp className="h-4 w-4" />
        </Button>
      </div>
      <div className="text-xs text-center text-muted-foreground flex items-center justify-center gap-1 mt-1">
        <Info size={12}/> GrokSTEM uses Grok-3-mini Beta and GPT-4o-mini.
      </div>
    </div>
  );
};

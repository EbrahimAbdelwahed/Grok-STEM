// frontend/src/components/custom/ChatInput.tsx
import React, { useState, useRef, useEffect } from 'react';
import { Textarea } from "../ui/textarea";
import { cn } from "../../lib/utils";
import { Button } from "../ui/button";
import { ArrowUp, Info } from "lucide-react"; // Replaced custom icon
// import { toast } from 'sonner'; // Assuming Sonner for notifications
import { motion } from 'framer-motion';

interface ChatInputProps {
    input: string; // Renamed from 'question'
    setInput: (input: string) => void; // Renamed from 'setQuestion'
    onSubmit: (text?: string) => void;
    isLoading: boolean;
    isConnected: boolean; // Pass connection status
}

// Example suggested actions
const suggestedActions = [
    {
        title: 'Projectile Motion',
        label: 'Calculate range and max height',
        action: 'A ball is thrown at 20 m/s at an angle of 30 degrees. Calculate its range and maximum height.',
    },
    {
        title: 'Ideal Gas Law',
        label: 'Find the volume of 1 mole of gas',
        action: 'What is the volume of 1 mole of an ideal gas at STP (Standard Temperature and Pressure)?',
    },
    {
        title: 'Derivative',
        label: 'Find the derivative of x^3 + 2x',
        action: 'Find the derivative of f(x) = x^3 + 2x^2 - 5x + 1',
    },
     {
        title: 'Plot Function',
        label: 'Plot y = sin(x)',
        action: 'Plot the function y = sin(x) for x from -2*pi to 2*pi',
    },
];

export const ChatInput: React.FC<ChatInputProps> = ({ input, setInput, onSubmit, isLoading, isConnected }) => {
    const [showSuggestions, setShowSuggestions] = useState(true);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // Auto-resize textarea height based on content
    useEffect(() => {
        const textarea = textareaRef.current;
        if (textarea) {
            textarea.style.height = 'auto'; // Reset height
            const scrollHeight = textarea.scrollHeight;
            // Set a max height (e.g., 200px) to prevent infinite growth
            const maxHeight = 200;
            textarea.style.height = `${Math.min(scrollHeight, maxHeight)}px`;
        }
    }, [input]);

    const handleInputChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
        setInput(event.target.value);
        // Hide suggestions when user starts typing
        if (event.target.value.length > 0) {
            setShowSuggestions(false);
        }
    };

    const handleSend = () => {
        if (!input.trim() || isLoading || !isConnected) return;
        onSubmit(input);
        setShowSuggestions(false); // Hide suggestions on send
    };

    const handleSuggestionClick = (actionText: string) => {
        setInput(actionText); // Set input field
        setShowSuggestions(false);
        // Optionally submit immediately:
        // onSubmit(actionText);
        // Or wait for user to press send/enter
        textareaRef.current?.focus();
    };

     const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (event.key === 'Enter' && !event.shiftKey) {
          event.preventDefault(); // Prevent newline
          handleSend();
        }
    };


    return(
    <div className="w-full flex flex-col gap-3"> {/* Use gap for spacing */}
        {/* Suggested Prompts - Shown only when input is empty */}
        {showSuggestions && input.length === 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {suggestedActions.map((suggestion, index) => (
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.05 * index, duration: 0.2 }}
                        key={suggestion.title}
                    >
                        <Button
                            variant="outline"
                            onClick={() => handleSuggestionClick(suggestion.action)}
                            className="text-left border rounded-lg px-3 py-2 text-sm w-full h-auto justify-start items-start flex flex-col"
                        >
                            <span className="font-medium text-foreground">{suggestion.title}</span>
                            <span className="text-xs text-muted-foreground">
                                {suggestion.label}
                            </span>
                        </Button>
                    </motion.div>
                ))}
            </div>
        )}

        {/* Input Area */}
        <div className="relative flex items-end rounded-lg border bg-background focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 focus-within:ring-offset-background">
            <Textarea
                ref={textareaRef}
                placeholder={isConnected ? "Ask a STEM question..." : "Connecting..."}
                className="flex-1 resize-none border-0 shadow-none focus-visible:ring-0 bg-transparent pr-12 py-2 min-h-[40px] max-h-[200px]" // Adjust padding/height
                value={input}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                rows={1} // Start with 1 row, auto-expands
                disabled={!isConnected || isLoading}
                aria-label="Chat message input"
            />
            <Button
                type="submit" // Use type submit if inside a form
                size="icon"
                className="absolute bottom-1.5 right-1.5 rounded-lg w-8 h-8" // Position button
                onClick={handleSend}
                disabled={!input.trim() || isLoading || !isConnected}
                aria-label="Send message"
            >
                <ArrowUp className="h-4 w-4" />
            </Button>
        </div>
         {/* Optional Status/Info Footer */}
         <div className="text-xs text-center text-muted-foreground flex items-center justify-center gap-1">
            <Info size={12}/> GrokSTEM uses Grok-3-mini Beta and GPT-4o-mini. Responses may be inaccurate.
         </div>
    </div>
    );
}

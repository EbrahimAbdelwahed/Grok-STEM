// frontend/src/components/custom/MarkdownRenderer.tsx
import React, { memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";       // For GitHub Flavored Markdown (tables, strikethrough, etc.)
import remarkMath from "remark-math";     // To support math syntax ($...$, $$...$$)
import rehypeKatex from "rehype-katex";   // To render math using KaTeX

// Import KaTeX CSS for styling math equations
import 'katex/dist/katex.min.css';

import { cn } from "../../lib/utils";

interface MarkdownRendererProps {
  children: string; // Markdown content as a string
  className?: string; // Optional additional class names for the container
}

// Define a type for the props passed to custom components (adjust as needed)
type ComponentProps = {
  node?: any; // The remark/rehype node
  inline?: boolean;
  className?: string;
  children?: React.ReactNode;
  [key: string]: any; // Allow other props like id, href, src, etc.
};

const NonMemoizedMarkdownRenderer = ({ children, className }: MarkdownRendererProps) => {
  const components = {
    // --- Code blocks and inline code styling ---
    code: ({ node, inline, className: codeClassName, children: codeChildren, ...props }: ComponentProps) => {
      const match = /language-(\w+)/.exec(codeClassName || "");
      return !inline && match ? (
        // Code Block
        <pre
          className={cn(
             "my-4 p-4 rounded-md bg-muted dark:bg-secondary/30 overflow-x-auto text-sm font-mono", // Use monospace font
             codeClassName // Allow additional classes if needed
          )}
          {...props}
        >
          <code className={`language-${match[1]}`}>{codeChildren}</code>
        </pre>
      ) : (
        // Inline Code
        <code
          className={cn(
             "px-1 py-0.5 rounded bg-muted text-muted-foreground dark:bg-secondary/50 dark:text-secondary-foreground font-mono text-sm", // Monospace font
             codeClassName
          )}
          {...props}
        >
          {codeChildren}
        </code>
      );
    },

    // --- Step Heading ID Injection ---
    h2: ({ node, children: h2Children, ...props }: ComponentProps) => {
      let id: string | undefined = undefined;
      // Check if children is an array and the first element is a string
      if (Array.isArray(h2Children) && h2Children.length > 0 && typeof h2Children[0] === 'string') {
          const textContent = h2Children[0];
          // Match "Step <number>:" case-insensitively at the beginning
          const match = textContent.match(/^Step\s+(\d+)\s*[:\-–—]?/i);
          if (match && match[1]) {
              id = `step-${match[1]}`;
          }
      }
      // Add scroll-mt-20 for sticky header offset when scrolling
      return (
        <h2 id={id} className="mt-6 mb-3 text-2xl font-semibold border-b pb-2 scroll-mt-20" {...props}>
          {h2Children}
        </h2>
      );
    },

    // --- Standard List Styling ---
     ol: ({ node, children: olChildren, ...props }: ComponentProps) => (
        <ol className="list-decimal list-inside my-3 pl-6 space-y-1" {...props}>{olChildren}</ol> // Increased padding
     ),
     ul: ({ node, children: ulChildren, ...props }: ComponentProps) => (
        <ul className="list-disc list-inside my-3 pl-6 space-y-1" {...props}>{ulChildren}</ul> // Increased padding
     ),
     li: ({ node, children: liChildren, ...props }: ComponentProps) => (
        <li className="my-1" {...props}>{liChildren}</li>
     ),

     // --- Link Styling ---
     a: ({ node, children: aChildren, ...props }: ComponentProps) => (
       <a
         className="text-primary underline hover:text-primary/80 transition-colors"
         target="_blank" // Open external links in new tab
         rel="noopener noreferrer" // Security best practice for target="_blank"
         {...props}
       >
           {aChildren}
       </a>
     ),

     // --- Other Element Styling ---
     h1: ({ node, children: h1Children, ...props }: ComponentProps) => (<h1 className="mt-6 mb-4 text-3xl font-bold border-b pb-2 scroll-mt-20" {...props}>{h1Children}</h1>),
     h3: ({ node, children: h3Children, ...props }: ComponentProps) => (<h3 className="mt-5 mb-2 text-xl font-semibold scroll-mt-20" {...props}>{h3Children}</h3>),
     h4: ({ node, children: h4Children, ...props }: ComponentProps) => (<h4 className="mt-4 mb-2 text-lg font-semibold scroll-mt-20" {...props}>{h4Children}</h4>),
     blockquote: ({ node, children: bqChildren, ...props }: ComponentProps) => (
        <blockquote className="mt-4 border-l-4 border-border pl-4 italic text-muted-foreground" {...props}>{bqChildren}</blockquote>
     ),
     hr: ({ node, ...props }: ComponentProps) => <hr className="my-4 border-border" {...props} />,
     // Add table styling if needed (often requires prose plugin or custom styles)
     table: ({ node, children: tableChildren, ...props }: ComponentProps) => (
        <div className="overflow-x-auto my-4">
           <table className="w-full border-collapse border border-border" {...props}>{tableChildren}</table>
        </div>
     ),
     th: ({ node, children: thChildren, ...props }: ComponentProps) => (
        <th className="border border-border px-4 py-2 text-left font-semibold bg-muted" {...props}>{thChildren}</th>
     ),
     td: ({ node, children: tdChildren, ...props }: ComponentProps) => (
        <td className="border border-border px-4 py-2 text-left" {...props}>{tdChildren}</td>
     ),
  };

  return (
    // Apply prose classes for overall markdown styling adjustments
    // prose-sm: Smaller base font size
    // prose-base: Default font size
    // dark:prose-invert: Adjusts colors for dark mode
    // max-w-none: Removes the default max-width constraint of prose
    // break-words: Helps prevent long unbreakable strings from overflowing
    <div className={cn("prose prose-sm sm:prose-base dark:prose-invert max-w-none break-words", className)}>
        <ReactMarkdown
            remarkPlugins={[remarkGfm, remarkMath]}
            rehypePlugins={[rehypeKatex]}
            components={components as any} // Cast needed due to complex component types
            // Allow specific HTML elements if absolutely necessary (e.g., from KaTeX)
            // Be cautious with allowing arbitrary HTML due to potential XSS risks
            // Example: rehypePlugins={[rehypeRaw, rehypeKatex]}
        >
            {children}
        </ReactMarkdown>
    </div>
  );
};

// Memoize the component to prevent re-renders if the markdown string hasn't changed
export const MarkdownRenderer = memo(NonMemoizedMarkdownRenderer);
MarkdownRenderer.displayName = "MarkdownRenderer"; // Add display name for React DevTools
// frontend/src/components/custom/MarkdownRenderer.tsx
import React, { memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import 'katex/dist/katex.min.css'; // Import KaTeX CSS
import { cn } from "../../lib/utils";

interface MarkdownRendererProps {
  children: string; // Markdown content as a string
}

// Define a type for the props passed to custom components
type ComponentProps = {
  node: any; // The remark/rehype node
  inline?: boolean;
  className?: string;
  children: React.ReactNode;
  [key: string]: any; // Allow other props
};

const NonMemoizedMarkdownRenderer = ({ children }: MarkdownRendererProps) => {
  const components = {
    // Code blocks and inline code styling
    code: ({ node, inline, className, children, ...props }: ComponentProps) => {
      const match = /language-(\w+)/.exec(className || "");
      return !inline && match ? (
        <pre
          className={cn(
             "my-4 p-4 rounded-md bg-secondary/50 dark:bg-secondary/20 overflow-x-auto text-sm",
             className // Allow additional classes if needed
          )}
          {...props}
        >
          <code className={`language-${match[1]}`}>{children}</code>
        </pre>
      ) : (
        <code
          className={cn(
             "px-1 py-0.5 rounded bg-muted text-muted-foreground font-mono text-sm",
             className
          )}
          {...props}
        >
          {children}
        </code>
      );
    },
    // Add IDs to step headings (assuming "## Step X:" format)
    h2: ({ node, children, ...props }: ComponentProps) => {
      let id: string | undefined = undefined;
      // Attempt to extract step number to create an ID
      if (typeof children === 'string' || (Array.isArray(children) && typeof children[0] === 'string')) {
          const textContent = Array.isArray(children) ? children[0] : children;
          const match = textContent.match(/^Step (\d+):?/i); // Case-insensitive match for "Step X:"
          if (match && match[1]) {
              id = `step-${match[1]}`;
          }
      }
      return (
        <h2 id={id} className="mt-6 mb-3 text-2xl font-semibold border-b pb-2" {...props}>
          {children}
        </h2>
      );
    },
     // Standard list styling using prose utilities implicitly (if @tailwindcss/typography is used well)
     // Or define explicitly if needed:
     ol: ({ node, children, ...props }: ComponentProps) => (
        <ol className="list-decimal list-inside my-3 pl-4 space-y-1" {...props}>{children}</ol>
     ),
     ul: ({ node, children, ...props }: ComponentProps) => (
        <ul className="list-disc list-inside my-3 pl-4 space-y-1" {...props}>{children}</ul>
     ),
     li: ({ node, children, ...props }: ComponentProps) => (
        <li className="my-1" {...props}>{children}</li>
     ),
     // Link styling
     a: ({ node, children, ...props }: ComponentProps) => (
       <a className="text-primary underline hover:text-primary/80" target="_blank" rel="noopener noreferrer" {...props}>{children}</a>
     ),
     // Other heading levels
     h1: ({ node, children, ...props }: ComponentProps) => (<h1 className="mt-6 mb-4 text-3xl font-bold border-b pb-2" {...props}>{children}</h1>),
     h3: ({ node, children, ...props }: ComponentProps) => (<h3 className="mt-5 mb-2 text-xl font-semibold" {...props}>{children}</h3>),
     h4: ({ node, children, ...props }: ComponentProps) => (<h4 className="mt-4 mb-2 text-lg font-semibold" {...props}>{children}</h4>),
     // Add styling for other elements like blockquotes, tables if needed
     blockquote: ({ node, children, ...props }: ComponentProps) => (
        <blockquote className="mt-4 border-l-4 pl-4 italic text-muted-foreground" {...props}>{children}</blockquote>
     ),
  };

  return (
    // Apply prose classes for overall markdown styling, adjust as needed
    <div className="prose prose-sm sm:prose-base dark:prose-invert max-w-none break-words">
        <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={components}
        // Allow HTML if needed for complex KaTeX or other tags, but be cautious
        // rehypePlugins={[rehypeRaw, rehypeKatex]} // Example if using rehype-raw
        >
        {children}
        </ReactMarkdown>
    </div>
  );
};

// Memoize the component to prevent re-renders if the children (markdown string) haven't changed
export const MarkdownRenderer = memo(NonMemoizedMarkdownRenderer);
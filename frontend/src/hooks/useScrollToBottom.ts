// frontend/src/hooks/useScrollToBottom.ts

import { useEffect, useRef, RefObject, useState } from 'react';

/**
 * Custom hook to automatically scroll a container to its bottom when content changes.
 * Also includes logic to only auto-scroll if the user is already near the bottom.
 * @returns A tuple containing:
 *   - ref for the scrollable container element.
 *   - ref for an element placed at the end of the content to scroll to.
 */
export function useScrollToBottom<T extends HTMLElement>(): [
  RefObject<T>, // containerRef
  RefObject<HTMLDivElement> // endRef (using HTMLDivElement for simplicity)
] {
  const containerRef = useRef<T>(null);
  const endRef = useRef<HTMLDivElement>(null); // Typically an empty div at the end
  const [isNearBottom, setIsNearBottom] = useState(true); // Track if user is near bottom

  // Effect to track if user scrolls away from the bottom
  useEffect(() => {
    const container = containerRef.current;

    const handleScroll = () => {
      if (container) {
        const { scrollTop, scrollHeight, clientHeight } = container;
        // Consider user "near bottom" if they are within ~100px of it
        const nearBottom = scrollHeight - scrollTop - clientHeight < 100;
        setIsNearBottom(nearBottom);
      }
    };

    if (container) {
      container.addEventListener('scroll', handleScroll, { passive: true });
      // Initial check
      handleScroll();
    }

    return () => {
      if (container) {
        container.removeEventListener('scroll', handleScroll);
      }
    };
  }, []); // Runs once on mount

  // Effect to scroll to bottom when content changes, but only if near bottom
  useEffect(() => {
    const container = containerRef.current;
    const end = endRef.current;

    if (container && end && isNearBottom) {
      // Use 'instant' for immediate jump after new content added
      end.scrollIntoView({ behavior: 'instant', block: 'end' });
    }

  }, [messages?.length, isNearBottom]); // Re-run when messages change (or specific content) OR if user scrolls back down
  // Note: Depending on how content streams, you might need a more sophisticated trigger than messages.length
  // Consider triggering based on a dependency that changes when *any* message content updates.


  return [containerRef, endRef];
}

// Helper type if needed elsewhere (adjust based on actual message structure)
// This is just an example dependency for the useEffect trigger.
// Replace with the actual dependency that signals new content or stream updates.
declare const messages: Array<{ id: string; [key: string]: any }> | undefined;
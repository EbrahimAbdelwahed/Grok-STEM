// frontend/src/hooks/useScrollToBottom.ts
import { useEffect } from 'react';

/**
 * Scrolls the given ref element into view whenever any of the dependencies change.
 * @param ref - React ref pointing to the target element
 * @param deps - Dependency array to trigger the scroll effect
 */
export function useScrollToBottom(
  ref: React.RefObject<HTMLElement>,
  deps: any[]
): void {
  useEffect(() => {
    if (!ref.current) return;
    // Smoothly scroll to the bottom-of-chat anchor
    ref.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, deps);
}

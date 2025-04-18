// frontend/src/interfaces/interfaces.ts

/**
 * Defines the structure for a single step in the reasoning breakdown.
 */
export interface ReasoningStep {
  id: string;      // Unique identifier for the step (e.g., "step-1")
  title: string;   // A short title or summary of the step
}

/**
 * Defines the structure for Plotly JSON data expected from the backend.
 * Note: This is a basic representation. For stricter typing, you might
 * import types from 'plotly.js' if feasible, or define more specific
 * interfaces for data and layout based on your expected plot types.
 */
export interface PlotlyData {
  data: any[];      // Array of trace objects (e.g., scatter, bar, line)
  layout: object;   // Plotly layout object
  // config?: object; // Optional Plotly config object
}

/**
 * Represents a single message in the chat conversation.
 * Can be from the 'user' or 'assistant'.
 * Includes optional fields for structured content like plots and steps.
 */
export interface EnhancedMessage {
  id: string;                     // Unique identifier for the message
  role: 'user' | 'assistant';     // Sender of the message
  text_content?: string;          // The main textual content of the message
  plotly_json?: PlotlyData | null;// Optional Plotly JSON data for visualization
  steps?: ReasoningStep[] | null; // Optional list of reasoning steps
  // Optional: Add other fields as needed, e.g., timestamps, feedback status
  // timestamp?: Date;
  // feedback?: 'liked' | 'disliked' | null;
}
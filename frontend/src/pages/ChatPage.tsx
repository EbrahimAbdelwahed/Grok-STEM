// frontend/src/pages/ChatPage.tsx

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { v4 as uuidv4 } from 'uuid';

// Import UI components
import { Header } from '@/components/custom/Header';
import { ChatInput } from '@/components/custom/ChatInput';
import { ChatMessage, ThinkingMessage } from '@/components/custom/ChatMessage';
import { Overview } from '@/components/custom/Overview';

// Import utilities and types
import { useScrollToBottom } from '@/hooks/useScrollToBottom';
import { EnhancedMessage, PlotlyData, ReasoningStep } from '@/interfaces/interfaces'; // Ensure all types are imported
// import { toast } from 'sonner'; // Import Sonner if using it for notifications

// --- Constants ---
const WEBSOCKET_URL = import.meta.env.VITE_WEBSOCKET_URL ?? "ws://localhost:8000/ws";

// Define the expected structure of incoming WebSocket messages
interface WebSocketMessage {
  type: 'text' | 'plot' | 'steps' | 'end' | 'error';
  id: string; // ID matching the message stream this chunk belongs to
  content?: string;
  plotly_json?: PlotlyData;
  steps?: ReasoningStep[];
}

export const ChatPage: React.FC = () => {
  // --- State ---
  const [messages, setMessages] = useState<EnhancedMessage[]>([]);
  const [input, setInput] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [currentError, setCurrentError] = useState<string | null>(null); // State for displaying errors

  // --- Refs ---
  const ws = useRef<WebSocket | null>(null);
  // Ref to store the ID of the assistant message currently being generated
  const currentAssistantMessageId = useRef<string | null>(null);
  const [messagesContainerRef, messagesEndRef] = useScrollToBottom<HTMLDivElement>([messages.length]);

  // --- WebSocket Connection Logic ---
  const connectWebSocket = useCallback(() => {
    // Avoid reconnecting if already open or connecting
    if (ws.current && (ws.current.readyState === WebSocket.OPEN || ws.current.readyState === WebSocket.CONNECTING)) {
      console.log("WebSocket already open or connecting.");
      return;
    }

    console.log(`Attempting to connect WebSocket to ${WEBSOCKET_URL}...`);
    setCurrentError(null); // Clear previous errors on new connection attempt
    ws.current = new WebSocket(WEBSOCKET_URL);

    ws.current.onopen = () => {
      console.log("WebSocket Connected");
      setIsConnected(true);
      setCurrentError(null);
    };

    ws.current.onclose = (event) => {
      console.log("WebSocket Disconnected:", event.reason, event.code);
      setIsConnected(false);
      // Only set error if it was an unexpected close
      if (!event.wasClean) {
          setCurrentError("Connection lost. Please try refreshing.");
          // toast.error("Connection lost. Please try refreshing.");
      }
      // If a message was being processed when connection dropped, stop loading
      if (currentAssistantMessageId.current) {
        setIsLoading(false);
        currentAssistantMessageId.current = null;
      }
    };

    ws.current.onerror = (error) => {
      console.error("WebSocket Error:", error);
      setCurrentError("Connection error. Please check the console or refresh.");
      // toast.error("WebSocket connection error.");
      setIsConnected(false);
      setIsLoading(false);
      currentAssistantMessageId.current = null;
    };

    // --- Message Handling ---
    ws.current.onmessage = (event) => {
      try {
        const messageData: WebSocketMessage = JSON.parse(event.data);
        const { type, id } = messageData;

        // If this is the first chunk for a new assistant response, record its ID
        if (currentAssistantMessageId.current === null && id && type !== 'end' && type !== 'error') {
            currentAssistantMessageId.current = id;
             // Add a placeholder message structure immediately if it doesn't exist
             setMessages(prev => {
                if (prev.some(msg => msg.id === id)) return prev; // Already exists
                return [...prev, { id, role: 'assistant', text_content: "" }]; // Add placeholder
             });
        }

        // Ignore messages not matching the current stream ID (unless it's a new error)
        if (type !== 'error' && id !== currentAssistantMessageId.current) {
          console.warn(`Ignoring message with ID ${id}. Current stream ID is ${currentAssistantMessageId.current}`);
          return;
        }

        setMessages((prevMessages) => {
          const msgIndex = prevMessages.findIndex(msg => msg.id === id);

          if (msgIndex === -1 && type !== 'error') {
            // This case should ideally be handled by the placeholder logic above,
            // but acts as a fallback if the first chunk isn't received correctly.
            console.warn(`Message with ID ${id} not found, creating.`);
             if(type === 'text') return [...prevMessages, { id, role: 'assistant', text_content: messageData.content || "" }];
             if(type === 'plot') return [...prevMessages, { id, role: 'assistant', plotly_json: messageData.plotly_json }];
             if(type === 'steps') return [...prevMessages, { id, role: 'assistant', steps: messageData.steps }];
             // Don't create new messages for 'end'
             return prevMessages;
          }

          // Update existing message based on type
          const updatedMessages = [...prevMessages];
          const currentMsg = updatedMessages[msgIndex];

          switch (type) {
            case 'text':
              updatedMessages[msgIndex] = {
                ...currentMsg,
                role: 'assistant', // Ensure role is assistant
                text_content: (currentMsg?.text_content || "") + (messageData.content || ""),
              };
              break;
            case 'plot':
              if (messageData.plotly_json) {
                updatedMessages[msgIndex] = { ...currentMsg, role: 'assistant', plotly_json: messageData.plotly_json };
              }
              break;
            case 'steps':
              if (messageData.steps) {
                updatedMessages[msgIndex] = { ...currentMsg, role: 'assistant', steps: messageData.steps };
              }
              break;
            case 'end':
              // Finalize the stream for this message
              setIsLoading(false);
              currentAssistantMessageId.current = null; // Reset for next message
              // Optionally update a flag on the message itself e.g., message.isComplete = true
              break;
            case 'error':
               // Handle errors sent from backend (could display differently)
               console.error("Backend Error:", messageData.content);
               setCurrentError(`Backend Error: ${messageData.content}`);
               // toast.error(`Backend Error: ${messageData.content}`);
               setIsLoading(false);
               currentAssistantMessageId.current = null;
               // Add a new distinct error message to the chat?
               // return [...prevMessages, {id: messageData.id || uuidv4(), role: 'assistant', text_content: `Error: ${messageData.content}` }];
               break; // Keep existing messages, error shown separately
            default:
              console.warn("Received unknown message type:", messageData);
          }
          return updatedMessages;
        });

      } catch (error) {
        console.error("Failed to parse WebSocket message or update state:", event.data, error);
        // Handle non-JSON messages or other errors if needed
        // setIsLoading(false); // Consider stopping loading on parse errors?
        // setCurrentError("Received invalid message format from server.");
      }
    };
  }, []); // Empty dependency array ensures this runs once on mount

  // --- Effects ---
  useEffect(() => {
    connectWebSocket();
    return () => { ws.current?.close(); };
  }, [connectWebSocket]);

  // --- Event Handlers ---
  const handleSubmit = useCallback(async (messageToSend?: string) => {
    const text = (messageToSend ?? input).trim(); // Use passed text or state
    if (!text) return;
    if (!isConnected || !ws.current || ws.current.readyState !== WebSocket.OPEN) {
      console.error("WebSocket is not connected.");
      setCurrentError("Not connected. Please wait or refresh.");
      // toast.error("Not connected. Please wait or refresh.");
      return;
    }
    if (isLoading) {
      console.warn("Submission attempt while loading blocked.");
      // toast.warning("Please wait for the current response to finish.");
      return;
    }

    const userMessageId = uuidv4();
    const userMessage: EnhancedMessage = {
      id: userMessageId,
      role: 'user',
      text_content: text,
    };

    // Add user message and set loading *before* sending
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    setInput("");
    setCurrentError(null); // Clear previous errors on new submission

    // Send message via WebSocket
    ws.current.send(text);

  }, [input, isLoading, isConnected, connectWebSocket]); // Add connectWebSocket if using reconnect logic

  // Function to scroll to a specific step
  const scrollToStep = useCallback((stepId: string) => {
    const element = document.getElementById(stepId);
    if (element) {
       // Add slight offset from top if header is sticky
      const headerOffset = 80; // Adjust based on your header height
      const elementPosition = element.getBoundingClientRect().top;
      const offsetPosition = elementPosition + window.scrollY - headerOffset;

      window.scrollTo({
          top: offsetPosition,
          behavior: "smooth"
      });
      // Simple version: element.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else {
      console.warn(`Element with ID ${stepId} not found for scrolling.`);
    }
  }, []);


  // --- Render ---
  return (
    <div className="flex flex-col h-screen bg-background">
      <Header />

      {/* Optional: Display connection error */}
      {currentError && (
        <div className="bg-destructive text-destructive-foreground p-2 text-center text-sm">
          {currentError}
        </div>
      )}

      <div
        className="flex-1 overflow-y-auto p-4 space-y-6" // Increased space-y
        ref={messagesContainerRef}
      >
        {messages.length === 0 && !isLoading && <Overview />}
        {messages.map((msg) => (
          <ChatMessage key={msg.id} message={msg} scrollToStep={scrollToStep} />
        ))}
        {isLoading && <ThinkingMessage />}
        <div ref={messagesEndRef} className="h-1" />
      </div>

      <div className="p-4 border-t bg-background">
        <div className="max-w-3xl mx-auto">
          <ChatInput
            input={input} // Pass state
            setInput={setInput} // Pass setter
            onSubmit={handleSubmit}
            isLoading={isLoading}
            isConnected={isConnected} // Pass connection status
          />
        </div>
      </div>
    </div>
  );
};

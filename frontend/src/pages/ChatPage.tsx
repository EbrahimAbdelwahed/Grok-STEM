import React, { useState, useEffect, useRef, useCallback } from 'react';
import { v4 as uuidv4 } from 'uuid';

// Import UI components
import { Header } from '@/components/custom/Header';
import { ChatInput } from '@/components/custom/ChatInput';
import { ChatMessage, ThinkingMessage } from '@/components/custom/ChatMessage'; // Import ThinkingMessage here
import { Overview } from '@/components/custom/Overview';
import { ScrollArea, ScrollBar } from '@/components/ui/scroll-area'; // Import ScrollArea components
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"; // For errors
import { Terminal } from "lucide-react"; // Icon for alert

// Import utilities and types
import { useScrollToBottom } from '@/hooks/useScrollToBottom';
import { EnhancedMessage, PlotlyData, ReasoningStep } from '@/interfaces/interfaces';

// --- Constants ---
const WEBSOCKET_URL = import.meta.env.VITE_WEBSOCKET_URL ?? "ws://localhost:8000/ws"; // Default for local dev
const RECONNECT_DELAY = 5000; // 5 seconds

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
  const reconnectTimeoutId = useRef<NodeJS.Timeout | null>(null);
  // Ref to store the ID of the assistant message currently being generated
  const currentAssistantMessageId = useRef<string | null>(null);
  // UseScrollToBottom hook for the ScrollArea viewport
  const scrollAreaRef = useRef<HTMLDivElement>(null); // Ref for the ScrollArea viewport
  const { scrollContainerRef, messagesEndRef, scrollToBottom } = useScrollToBottom<HTMLDivElement>([messages, isLoading]); // Pass isLoading to trigger scroll on its change


  // --- WebSocket Connection Logic ---
  const connectWebSocket = useCallback(() => {
    // Clear any existing reconnect timeout
    if (reconnectTimeoutId.current) {
      clearTimeout(reconnectTimeoutId.current);
      reconnectTimeoutId.current = null;
    }

    // Avoid reconnecting if already open or connecting
    if (ws.current && (ws.current.readyState === WebSocket.OPEN || ws.current.readyState === WebSocket.CONNECTING)) {
      console.log("WebSocket already open or connecting.");
      setIsConnected(true); // Ensure state reflects reality
      return;
    }

    console.log(`Attempting to connect WebSocket to ${WEBSOCKET_URL}...`);
    setCurrentError(null); // Clear previous errors on new connection attempt
    setIsConnected(false); // Assume not connected initially
    ws.current = new WebSocket(WEBSOCKET_URL);

    ws.current.onopen = () => {
        console.debug("WebSocket connected.");
        setIsConnected(true);
        setCurrentError(null);
        if (reconnectTimeoutId.current) { // Clear timeout if connection succeeds
            clearTimeout(reconnectTimeoutId.current);
            reconnectTimeoutId.current = null;
        }
    };

    ws.current.onclose = (event) => {
        console.debug(`WebSocket closed: Code=${event.code}, reason=${event.reason}`);
        setIsConnected(false);
        ws.current = null; // Clear the ref

        // Only set error and attempt reconnect if it wasn't a clean close or manual close (code 1000)
        if (!event.wasClean && event.code !== 1000) {
          const errorMsg = `Connection lost (Code: ${event.code}). Attempting to reconnect...`;
          setCurrentError(errorMsg);
          console.log(errorMsg);
          // Schedule reconnect attempt
          if (!reconnectTimeoutId.current) {
              reconnectTimeoutId.current = setTimeout(connectWebSocket, RECONNECT_DELAY);
          }
        } else {
            // Clean close, maybe user navigated away
            setCurrentError(null); // Clear any previous errors
        }

        // If a message was being processed when connection dropped, stop loading
        if (currentAssistantMessageId.current) {
          console.warn("Connection closed while message", currentAssistantMessageId.current, "was processing.");
          setIsLoading(false);
          currentAssistantMessageId.current = null;
        }
    };

    ws.current.onerror = (error) => {
        console.error("WebSocket encountered error:", error);
        setCurrentError("Connection error occurred.");
        setIsConnected(false);
        setIsLoading(false); // Stop loading on error
        currentAssistantMessageId.current = null;
        if (ws.current && ws.current.readyState !== WebSocket.CLOSED) {
          ws.current.close(); // Attempt to force close to trigger onclose handler
        }
        ws.current = null; // Clear ref
    };

    // --- Message Handling ---
    ws.current.onmessage = (event) => {
        console.debug("WebSocket message received:", event.data);
        try {
          const messageData: WebSocketMessage = JSON.parse(event.data);
          const { type, id } = messageData;

          // 1) Always handle 'end' first, before matching IDs
          if (type === 'end') {
              console.log(`[ID: ${id}] Received end signal.`);
              setIsLoading(false);
              currentAssistantMessageId.current = null;
              return;
          }

          // Handle backend errors specifically
          if (type === 'error') {
              console.error(`[ID: ${id}] Backend Error Received:`, messageData.content);
              const errorId = id || uuidv4(); // Use message ID or generate one
              const errorMsg = `Backend Error: ${messageData.content || 'Unknown error'}`;
              setCurrentError(errorMsg);
              setIsLoading(false);

              // Try to update the placeholder if it exists, otherwise add new error msg
              setMessages(prev => {
                   const msgIndex = prev.findIndex(msg => msg.id === errorId && msg.role === 'assistant');
                   if (msgIndex !== -1) {
                        const updatedMessages = [...prev];
                        // Replace placeholder with error content or mark it as error
                        updatedMessages[msgIndex] = {
                            ...updatedMessages[msgIndex],
                            text_content: `Error: ${messageData.content || 'Unknown error'}`, // Show error in chat
                            isError: true // Add a flag
                        };
                        return updatedMessages;
                   } else {
                       // If no placeholder, maybe add a generic error message? Or rely on Alert.
                       // For now, we rely on the Alert banner.
                       return prev;
                   }
              });

              // If the error belongs to the current stream, reset the stream ID
              if (id === currentAssistantMessageId.current) {
                  currentAssistantMessageId.current = null;
              }
              return; // Stop processing this specific error message here
          }

          // Initial message chunk handling: Create placeholder if needed
          if (currentAssistantMessageId.current === null && type !== 'error') {
              console.log(`[ID: ${id}] Received first chunk, type: ${type}`);
              currentAssistantMessageId.current = id;
              // Add a new, empty assistant message placeholder
              setMessages(prev => {
                   // Check if a message with this ID already exists (e.g., from cache hit followed by error?)
                  if (prev.some(msg => msg.id === id)) {
                      console.warn(`[ID: ${id}] Message placeholder already exists.`);
                      return prev;
                  }
                  console.log(`[ID: ${id}] Adding new assistant message placeholder.`);
                  // Add placeholder with role and ID, other fields undefined initially
                  return [...prev, { id, role: 'assistant' }];
              });
          }

          // 2) Ignore any messages that don't belong to the current stream
          if (id !== currentAssistantMessageId.current) {
              console.warn(`Ignoring message with ID ${id} - does not match current stream ${currentAssistantMessageId.current}`);
              return;
          }

          // Update the state immutably
          setMessages(prevMessages => {
              // Find the index of the message to update
              const msgIndex = prevMessages.findIndex(msg => msg.id === id);

              if (msgIndex === -1) {
                  // Should not happen if placeholder logic works, but log if it does
                  console.error(`[ID: ${id}] Cannot find message to update.`);
                  return prevMessages;
              }

              const updatedMessages = [...prevMessages];
              let currentMsg = { ...updatedMessages[msgIndex] }; // Create a copy to modify

              // Process based on message type
              switch (type) {
                  case 'text':
                      currentMsg.text_content = (currentMsg.text_content || "") + (messageData.content || "");
                      console.debug(`[ID: ${id}] Appended text chunk. New length: ${currentMsg.text_content?.length}`);
                      break;
                  case 'plot':
                      if (messageData.plotly_json) {
                          currentMsg.plotly_json = messageData.plotly_json;
                          console.log(`[ID: ${id}] Added plot data.`);
                      }
                      break;
                  case 'steps':
                      if (messageData.steps) {
                          currentMsg.steps = messageData.steps;
                          console.log(`[ID: ${id}] Added ${messageData.steps.length} steps.`);
                      }
                      break;
                  // 'end' case is now handled at the top of the function
                  default:
                      console.warn(`[ID: ${id}] Received unknown message type:`, type);
                      return prevMessages; // Return current state
              }

              // Put the updated message back into the array
              updatedMessages[msgIndex] = currentMsg;
              return updatedMessages;
          });

        } catch (error) {
          console.error("Failed to parse WebSocket message or update state:", event.data, error);
          setCurrentError("Received invalid message format from server.");
          // 3) Always clear loading and reset stream if parsing blows up
          setIsLoading(false);
          currentAssistantMessageId.current = null;
        }
    };
  }, []); // connectWebSocket has no dependencies, runs once

  // --- Effects ---
  useEffect(() => {
    connectWebSocket(); // Initial connection attempt
    // Cleanup function to close WebSocket and clear timeout on component unmount
    return () => {
      console.log("ChatPage unmounting. Closing WebSocket.");
      if (reconnectTimeoutId.current) {
        clearTimeout(reconnectTimeoutId.current);
      }
      ws.current?.close(1000, "Component unmounting"); // Code 1000 for normal closure
      ws.current = null;
    };
  }, [connectWebSocket]); // Re-run effect only if connectWebSocket identity changes (it shouldn't)


  // --- Event Handlers ---
  const handleSubmit = useCallback(async (messageToSend?: string) => {
    const text = (messageToSend ?? input).trim();
    if (!text) return;

    if (!isConnected || !ws.current || ws.current.readyState !== WebSocket.OPEN) {
      console.error("WebSocket is not connected. Cannot send message.");
      setCurrentError("Not connected. Please wait or refresh.");
      // Optionally try to reconnect immediately
      // connectWebSocket();
      return;
    }
    if (isLoading) {
      console.warn("Submission attempt while loading blocked.");
      return;
    }

    const userMessageId = uuidv4();
    const userMessage: EnhancedMessage = {
      id: userMessageId,
      role: 'user',
      text_content: text,
    };

    // Add user message and immediately set loading
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    setInput("");
    setCurrentError(null); // Clear previous errors on new submission
    scrollToBottom(); // Scroll after adding user message

    // Send message via WebSocket
    console.log(`Sending message: ${text.substring(0, 50)}...`);
    ws.current.send(text);

  }, [input, isLoading, isConnected, scrollToBottom]); // Add scrollToBottom dependency


  // --- Scrolling ---
  const scrollToStep = useCallback((stepId: string) => {
    const element = document.getElementById(stepId);
    const scrollContainer = scrollContainerRef.current; // Use the ref from the hook

    if (element && scrollContainer) {
        const containerTop = scrollContainer.getBoundingClientRect().top;
        const elementTop = element.getBoundingClientRect().top;
        const headerOffset = 80; // Adjust as needed for sticky header height
        const currentScrollTop = scrollContainer.scrollTop;

        const scrollToPosition = currentScrollTop + (elementTop - containerTop) - headerOffset;

        scrollContainer.scrollTo({
            top: scrollToPosition,
            behavior: 'smooth'
        });
        console.log(`Scrolling to step ${stepId} at position ${scrollToPosition}`);
    } else {
        console.warn(`Element with ID ${stepId} or scroll container not found for scrolling.`);
    }
  }, [scrollContainerRef]); // Dependency on container ref from hook

  // --- Render ---
  return (
    <div className="flex flex-col h-screen bg-background overflow-hidden"> {/* Prevent body scroll */}
      <Header />

      {/* Error Alert */}
      {currentError && (
         <Alert variant="destructive" className="m-2 rounded-md shrink-0"> {/* Add shrink-0 */}
             <Terminal className="h-4 w-4" />
             <AlertTitle>Connection Issue</AlertTitle>
             <AlertDescription>{currentError}</AlertDescription>
         </Alert>
      )}

      {/* Use ScrollArea for the main chat content */}
      {/* Assign the ref from useScrollToBottom to the ScrollArea's viewport */}
      <ScrollArea className="flex-1" viewportRef={scrollContainerRef}>
          <div className="p-4 space-y-6 max-w-4xl mx-auto"> {/* Add max-width and center */}
            {messages.length === 0 && !isLoading && <Overview />}
            {messages.map((msg) => (
              <ChatMessage key={msg.id} message={msg} scrollToStep={scrollToStep} />
            ))}
            {isLoading && <ThinkingMessage />}
            {/* Invisible div to target for scrolling to bottom */}
            <div ref={messagesEndRef} className="h-1" />
          </div>
          <ScrollBar orientation="vertical" />
      </ScrollArea>

      {/* Input area sticky at the bottom */}
      <div className="p-4 border-t bg-background shrink-0"> {/* Add shrink-0 */}
        <div className="max-w-3xl mx-auto">
          <ChatInput
            input={input}
            setInput={setInput}
            onSubmit={handleSubmit}
            isLoading={isLoading}
            isConnected={isConnected}
          />
        </div>
      </div>
    </div>
  );
};

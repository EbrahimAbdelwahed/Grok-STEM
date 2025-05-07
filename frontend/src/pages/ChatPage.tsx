// frontend/src/pages/ChatPage.tsx
import React, { useEffect, useState, useRef, useCallback } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { Header } from '@/components/custom/Header';
import { ChatInput } from '@/components/custom/ChatInput';
import { ChatMessage } from '@/components/custom/ChatMessage';
import { ThinkingMessage, Phase as ThinkingPhaseType } from '@/components/custom/ThinkingMessage'; // Import Phase type
import { Sidebar, SidebarContentData } from '@/components/custom/Sidebar';
import { useScrollToBottom } from '@/hooks/useScrollToBottom';
import { Button } from '@/components/ui/button';
import { Image as ImageIcon } from 'lucide-react';
import { Overview } from '@/components/custom/Overview'; // Import Overview

// --- Types ---
interface Step {
  id: string;
  title: string;
}

// Represents a completed or in-progress message in the history
interface HistoryMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string | null;
  // Assistant-specific fields
  steps?: Step[] | null;
  plotJson?: any | null;
  imageUrl?: string | null;
  imagePrompt?: string | null; // The prompt used *for* the image
  isError?: boolean;
  errorContent?: string | null;
  // Metadata for UI state
  isComplete?: boolean; // Flag to indicate if assistant response stream is finished
}

// Structure of incoming WebSocket chunks
interface WebSocketChunk {
  type: string;
  id: string; // Message ID stream this chunk belongs to
  chat_id: string; // Chat session ID
  content?: string;
  steps?: Step[];
  plotly_json?: any;
  image_url?: string;
  attempt?: number; // For image_retry
  max_attempts?: number; // For image_retry
  phase?: ThinkingPhaseType;
}

export const ChatPage: React.FC = () => {
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [chatId, setChatId] = useState<string>('');
  const [isConnected, setIsConnected] = useState(false);
  const [input, setInput] = useState<string>('');
  const [messageHistory, setMessageHistory] = useState<HistoryMessage[]>([]);
  const [thinkingPhase, setThinkingPhase] = useState<ThinkingPhaseType | null>(null);
  const currentAssistantMessageIdRef = useRef<string | null>(null); // Use ref to avoid state update complexities in WS handler

  // State for the sidebar content (reflects the latest assistant message OR the one being interacted with for image gen)
  const [sidebarContent, setSidebarContent] = useState<SidebarContentData>({
    messageId: null,
    steps: null,
    plotJson: null,
    imageUrl: null,
    imageState: 'idle',
    imageError: null,
    imagePromptUsed: null,
    imageRetryCount: 0, // Add retry count to sidebar state
  });

  const chatContainerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  // Scroll when history changes or thinking phase changes
  useScrollToBottom(bottomRef, [messageHistory, thinkingPhase]);

  // --- WebSocket Connection ---
  useEffect(() => {
    const wsUrl = import.meta.env.VITE_WEBSOCKET_URL || `ws://${window.location.hostname}:8000/ws`;
    console.log("Attempting WebSocket connection to:", wsUrl);
    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      console.log("WebSocket connected");
      setWs(socket);
      setIsConnected(true);
    };

    socket.onclose = (event) => {
      console.log("WebSocket disconnected:", event.code, event.reason);
      setWs(null);
      setIsConnected(false);
      setThinkingPhase(null);
      currentAssistantMessageIdRef.current = null;
    };

    socket.onerror = (error) => {
      console.error("WebSocket error:", error);
      setIsConnected(false);
      setThinkingPhase(null);
      currentAssistantMessageIdRef.current = null;
    };

    socket.onmessage = (event) => {
      try {
        const chunk: WebSocketChunk = JSON.parse(event.data);
        console.debug("Received chunk:", chunk); // Debugging
        processWebSocketChunk(chunk);
      } catch (error) {
        console.error("Failed to parse WebSocket message:", event.data, error);
      }
    };

    // No cleanup function needed here that closes the socket,
    // as we want it to persist for the component lifetime.
    // Return a function to close ONLY if the component unmounts.
    return () => {
        if (socket && socket.readyState === WebSocket.OPEN) {
            console.log("Closing WebSocket connection on component unmount.");
            socket.close();
        }
        setWs(null);
        setIsConnected(false);
    };
  }, []); // Empty dependency array - run only once on mount


  // --- Process Incoming Chunks ---
  const processWebSocketChunk = (chunk: WebSocketChunk) => {
    const { type, id: messageId } = chunk;

    setMessageHistory(prevHistory => {
      let updatedHistory = [...prevHistory];
      const msgIndex = updatedHistory.findIndex(msg => msg.id === messageId && msg.role === 'assistant');

      let targetMessage: HistoryMessage;

      if (msgIndex === -1) {
        // If it's the first chunk for a new assistant message
        if (type !== 'init' && type !== 'end') { // Don't create history for init/end without content
             targetMessage = {
                 id: messageId,
                 role: 'assistant',
                 text: null,
                 isComplete: false, // Mark as in-progress
                 steps: null,
                 plotJson: null,
                 imageUrl: null,
                 imagePrompt: null,
                 isError: false,
                 errorContent: null,
             };
             updatedHistory.push(targetMessage);
             currentAssistantMessageIdRef.current = messageId; // Track the new message ID
        } else {
            return prevHistory; // Ignore init/end if no message exists yet
        }
      } else {
        // Get the existing message to update
        targetMessage = { ...updatedHistory[msgIndex] };
      }

      // Apply updates based on chunk type
      switch (type) {
        case 'progress':
          setThinkingPhase(chunk.phase || null);
          // Do not modify history for progress
          return prevHistory; // Return previous state to avoid unnecessary history update
        case 'text':
          targetMessage.text = (targetMessage.text || "") + (chunk.content || "");
          break;
        case 'steps':
          targetMessage.steps = chunk.steps || null;
          break;
        case 'plot':
          targetMessage.plotJson = chunk.plotly_json || null;
          break;
        case 'image':
          targetMessage.imageUrl = chunk.image_url || null;
          // If backend sent back the prompt used:
          // targetMessage.imagePrompt = chunk.image_prompt || null;
          // Update sidebar state ONLY if this message IS the one currently tracked by the sidebar
          setSidebarContent(prev => {
              if (prev.messageId === messageId) {
                  return { ...prev, imageState: 'success', imageUrl: targetMessage.imageUrl, imageError: null };
              }
              return prev;
          });
          break;
        case 'image_retry':
          // Update sidebar state ONLY if this message IS the one currently tracked by the sidebar
          setSidebarContent(prev => {
              if (prev.messageId === messageId) {
                  return { ...prev, imageState: 'retrying', imageRetryCount: chunk.attempt ?? prev.imageRetryCount + 1 };
              }
              return prev;
          });
          // Don't modify history for retry attempts
          return prevHistory; // Return previous state
        case 'image_error':
          // Update sidebar state ONLY if this message IS the one currently tracked by the sidebar
          setSidebarContent(prev => {
              if (prev.messageId === messageId) {
                  return { ...prev, imageState: 'error', imageError: chunk.content || "Image generation failed." };
              }
              return prev;
          });
           // Don't modify history for image errors, let the sidebar handle display
           return prevHistory; // Return previous state
        case 'error':
          targetMessage.isError = true;
          targetMessage.errorContent = chunk.content || "An error occurred.";
          targetMessage.isComplete = true; // Error marks completion
          setThinkingPhase(null); // Clear thinking phase
          currentAssistantMessageIdRef.current = null;
          // Update sidebar if this was the active message
          setSidebarContent(prev => prev.messageId === messageId ? { ...prev, imageState: 'idle' } : prev);
          break;
        case 'end':
          targetMessage.isComplete = true;
          setThinkingPhase(null);
          currentAssistantMessageIdRef.current = null;
          // Update the sidebar to reflect the final state of this message *if* it's the latest one
          if (targetMessage.id === updatedHistory[updatedHistory.length - 1]?.id) {
                updateSidebarFromMessage(targetMessage);
          }
          break;
        case 'init': // Ignore init after connection established
            return prevHistory;
        default:
          console.warn(`Unhandled chunk type: ${type}`);
          return prevHistory; // No change for unknown types
      }

      // Update the message in the history array
      if (msgIndex !== -1) {
           updatedHistory[msgIndex] = targetMessage;
      }
      // If it was a new message, it's already pushed

      // If this message is the latest one being tracked, update sidebar
      // (Avoid updating on 'end' as it's handled separately)
      if (targetMessage.id === currentAssistantMessageIdRef.current && type !== 'end' && type !== 'error') {
          updateSidebarFromMessage(targetMessage);
      }


      return updatedHistory;
    });
  };

  // --- Update Sidebar Content ---
  // Now focuses on reflecting a specific message's state in the sidebar
  const updateSidebarFromMessage = (message: HistoryMessage | null) => {
     if (message && message.role === 'assistant') {
         // Preserve image state if the message ID hasn't changed
         // Otherwise, reset image state based on the new message
         setSidebarContent(prev => {
             const isSameMessage = prev.messageId === message.id;
             const newImageState = message.imageUrl ? 'success' : (isSameMessage ? prev.imageState : 'idle');
             const newImageError = message.imageUrl ? null : (isSameMessage ? prev.imageError : null);

             return {
                 messageId: message.id,
                 steps: message.steps || null,
                 plotJson: message.plotJson || null,
                 imageUrl: message.imageUrl || null,
                 imagePromptUsed: message.imagePrompt || null, // Update prompt if available
                 imageState: newImageState,
                 imageError: newImageError,
                 // Preserve retry count only if staying on the same message and retrying/error
                 imageRetryCount: isSameMessage && (newImageState === 'retrying' || newImageState === 'error') ? prev.imageRetryCount : 0,
             };
         });
     } else {
          // Clear sidebar if no message or user message selected
          setSidebarContent({
               messageId: null, steps: null, plotJson: null, imageUrl: null,
               imageState: 'idle', imageError: null, imagePromptUsed: null, imageRetryCount: 0
          });
     }
  };

  // Effect to update sidebar when message history changes (to show latest *completed* one)
  // OR when the assistant starts responding (to show its progress)
  useEffect(() => {
      const assistantResponding = thinkingPhase !== null;
      if (assistantResponding && currentAssistantMessageIdRef.current) {
           // Find the message being generated
           const currentMsg = messageHistory.find(m => m.id === currentAssistantMessageIdRef.current);
           if (currentMsg) {
               updateSidebarFromMessage(currentMsg);
           }
      } else if (!assistantResponding) {
          // Show the latest completed assistant message
          const lastAssistantMessage = [...messageHistory].reverse().find(msg => msg.role === 'assistant');
          updateSidebarFromMessage(lastAssistantMessage || null);
      }
  }, [messageHistory, thinkingPhase]); // Trigger on history/phase change


  // --- Send Message ---
  const handleSendMessage = (messageText: string) => {
    if (!ws || !isConnected || !messageText.trim()) return;

    const userMessage: HistoryMessage = {
      id: uuidv4(),
      role: 'user',
      text: messageText.trim(),
      isComplete: true, // User messages are always complete
    };
    setMessageHistory(prev => [...prev, userMessage]);
    setInput('');

    // Reset state for the *next* assistant response
    currentAssistantMessageIdRef.current = null; // Clear ref for the new message
    setThinkingPhase('cache_check'); // Initial phase
    // Clear sidebar immediately for the upcoming response
    setSidebarContent({ messageId: null, steps: null, plotJson: null, imageUrl: null, imageState: 'idle', imageError: null, imagePromptUsed: null, imageRetryCount: 0 });

    ws.send(JSON.stringify({ type: "chat", chat_id: chatId, message: userMessage.text }));
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 50);
  };

  // --- User Trigger Image Generation ---
  const handleUserGenerateImage = useCallback((assistantMessage: HistoryMessage) => {
    if (!ws || !isConnected || !assistantMessage.id) return;
    // Find the user query that led to this assistant message
    const originalUserQuery = findOriginalUserQuery(assistantMessage.id) || assistantMessage.text; // Fallback needed

    if (!originalUserQuery) {
        console.error("Cannot trigger image generation: Could not find original user query for message ID:", assistantMessage.id);
        // Optionally show feedback to user
        return;
    }

    console.log(`Requesting user-triggered image for message ${assistantMessage.id}`);

    // Update sidebar state immediately to show loading *for this message*
    setSidebarContent({
      messageId: assistantMessage.id,
      steps: assistantMessage.steps || null, // Keep existing steps/plot
      plotJson: assistantMessage.plotJson || null,
      imageUrl: null, // Clear previous image
      imageState: 'loading',
      imageError: null,
      imageRetryCount: 0,
      imagePromptUsed: null, // Will be generated by backend
    });

    ws.send(JSON.stringify({
      type: "generate_image",
      chat_id: chatId,
      assistant_message_id: assistantMessage.id,
      original_user_query: originalUserQuery
    }));
  }, [ws, isConnected, chatId, messageHistory]); // Include messageHistory dependency

  // Helper to find the user message preceding an assistant message
  const findOriginalUserQuery = (assistantMsgId: string): string | null => {
      const assistantIndex = messageHistory.findIndex(msg => msg.id === assistantMsgId);
      if (assistantIndex > 0 && messageHistory[assistantIndex - 1]?.role === 'user') {
          return messageHistory[assistantIndex - 1].text;
      }
      console.warn(`Could not find preceding user query for assistant message ${assistantMsgId}`);
      return null;
  }

  // --- Handle Image Retry ---
  const handleImageRetry = useCallback(() => {
     const { messageId } = sidebarContent; // Get ID from sidebar state
     if (!ws || !isConnected || !messageId) return;

     // Find the original user query associated with the message needing retry
     const originalQuery = findOriginalUserQuery(messageId);
       if (!originalQuery) {
           console.error("Could not find original user query for retry.");
           setSidebarContent(prev => ({ ...prev, imageState: 'error', imageError: 'Cannot retry: original context lost.' }));
           return;
       }

     console.log(`Retrying image generation for message ${messageId}`);
     setSidebarContent(prev => ({ ...prev, imageState: 'retrying' })); // Update UI state

     ws.send(JSON.stringify({
       type: "generate_image", // Use the same trigger type
       chat_id: chatId,
       assistant_message_id: messageId,
       original_user_query: originalQuery // Send original query again
     }));

  }, [ws, isConnected, chatId, sidebarContent.messageId, messageHistory]); // Depend on sidebar messageId & history

  // --- Render Logic ---
  return (
    <div className="flex flex-col h-screen bg-background">
      <Header />
      <div className="flex flex-1 overflow-hidden">

        {/* Chat Message Area (Scrollable) */}
        <main ref={chatContainerRef} className="flex-1 overflow-y-auto p-4 space-y-4">
          {messageHistory.length === 0 && !thinkingPhase && <Overview />}

          {messageHistory.map((msg) => (
            <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-xl lg:max-w-2xl px-4 py-3 rounded-lg shadow-md ${msg.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-card text-card-foreground'}`}>
                {/* User Message */}
                {msg.role === 'user' && <p>{msg.text}</p>}

                {/* Assistant Message - Only Text/Error Rendered Here */}
                {msg.role === 'assistant' && (
                  <ChatMessage content={msg.text || ''} isError={msg.isError} errorContent={msg.errorContent} />
                )}

                {/* Add Generate Image button to *completed* Assistant messages */}
                {msg.role === 'assistant' && msg.isComplete && !msg.isError && msg.text && (
                    <div className="mt-2 text-right border-t border-border/50 pt-2">
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleUserGenerateImage(msg)}
                            // Disable if an image is already successfully loaded *in the sidebar for this message* OR if currently loading
                            disabled={ (sidebarContent.messageId === msg.id && (sidebarContent.imageState === 'loading' || sidebarContent.imageState === 'retrying' || sidebarContent.imageState === 'success'))}
                            className="text-muted-foreground hover:text-foreground text-xs h-7 px-2"
                            title="Generate related image"
                        >
                            <ImageIcon className="h-3.5 w-3.5 mr-1" /> Generate Image
                        </Button>
                    </div>
                )}
              </div>
            </div>
          ))}

          {/* Loading/Thinking Indicator at the end of chat */}
          {thinkingPhase && (
            <div className="flex justify-start">
                 <div className="max-w-xl lg:max-w-2xl p-3"> {/* No card background needed */}
                     <ThinkingMessage phase={thinkingPhase} />
                 </div>
            </div>
          )}

          <div ref={bottomRef} className="h-1" /> {/* Scroll anchor */}
        </main>

        {/* Fixed Sidebar */}
        <aside className="w-80 lg:w-96 border-l bg-muted/30 hidden md:block"> {/* Use muted bg for sidebar */}
          <Sidebar content={{ ...sidebarContent, onImageRetry: handleImageRetry }} />
        </aside>
      </div>

      {/* Input Area */}
      <div className="p-4 border-t bg-background">
        <ChatInput
          input={input}
          setInput={setInput}
          onSubmit={handleSendMessage}
          isLoading={thinkingPhase !== null} // Loading if any phase is active
          isConnected={isConnected}
        />
        {!isConnected && (
          <p className="text-center text-xs text-destructive mt-1">Connection lost. Please wait or refresh.</p>
        )}
      </div>
    </div>
  );
};
// frontend/src/pages/ChatPage.tsx
import React, { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChatInput } from '@/components/custom/ChatInput';
import { ChatMessage } from '@/components/custom/ChatMessage';
import { ThinkingMessage } from '@/components/custom/ThinkingMessage';
import { StepNavigator } from '@/components/custom/StepNavigator';
import { PlotDisplay } from '@/components/custom/PlotDisplay';
import { useScrollToBottom } from '@/hooks/useScrollToBottom';

interface WebSocketChunk {
  type: string;
  content?: string;
  steps?: { id: string; title: string }[];
  plotly_json?: any;
  phase?: 'reasoning' | 'steps' | 'plotting';
  chat_id?: string;
}

export const ChatPage: React.FC = () => {
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [chatId, setChatId] = useState<string>('');
  const [isConnected, setIsConnected] = useState(false);
  const [messages, setMessages] = useState<WebSocketChunk[]>([]);
  const [pendingPhases, setPendingPhases] = useState<Set<string>>(new Set());
  const [steps, setSteps] = useState<{ id: string; title: string }[]>([]);
  const [plotJson, setPlotJson] = useState<any>(null);
  const [input, setInput] = useState<string>('');
  const isLoading = pendingPhases.size > 0;
  const bottomRef = useRef<HTMLDivElement>(null);

  useScrollToBottom(bottomRef, [messages]);

  useEffect(() => {
    const socket = new WebSocket(`ws://localhost:8000/ws`);
    socket.onopen = () => {
      setWs(socket);
      setIsConnected(true);
    };
    socket.onmessage = (event) => {
      const chunk: WebSocketChunk = JSON.parse(event.data);
      switch (chunk.type) {
        case 'init':
          setChatId(chunk.chat_id || '');
          break;
        case 'progress':
          // add phase to pending
          setPendingPhases((prev) => new Set(prev).add(chunk.phase!));
          break;
        case 'text':
          setMessages((msgs) => [...msgs, chunk]);
          break;
        case 'steps':
          setSteps(chunk.steps || []);
          setMessages((msgs) => [...msgs, chunk]);
          break;
        case 'plot':
          setPlotJson(chunk.plotly_json);
          setMessages((msgs) => [...msgs, chunk]);
          break;
        case 'error':
          setMessages((msgs) => [...msgs, chunk]);
          break;
        case 'end':
          setPendingPhases(new Set());
          break;
        default:
          break;
      }
    };
    socket.onclose = () => setIsConnected(false);
    return () => {
      socket.close();
    };
  }, []);

  const handleSubmit = (message: string) => {
    if (ws && isConnected) {
      ws.send(JSON.stringify({ chat_id: chatId, message }));
      setPendingPhases(new Set(['reasoning']));
      setMessages([]);
      setSteps([]);
      setPlotJson(null);
      setInput('');
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-grow overflow-auto p-4">
        {/* Step Navigator Sidebar */}
        {steps.length > 0 && (
          <aside className="fixed right-4 top-24 w-48">
            <StepNavigator steps={steps} />
          </aside>
        )}

        {/* Chat Messages */}
        {messages.map((msg, idx) => (
          <div key={idx} id={msg.type === 'steps' ? msg.steps?.[0].id : undefined}>
            {msg.type === 'text' && <ChatMessage content={msg.content!} />}
            {msg.type === 'steps' && <ChatMessage content={'Steps available'} isMeta />}
            {msg.type === 'plot' && <PlotDisplay plotlyJson={plotJson} />}
            {msg.type === 'error' && <ChatMessage content={msg.content!} isError />}
          </div>
        ))}

        {/* Thinking Messages for pending phases */}
        {[...pendingPhases].map((phase) => (
          <ThinkingMessage key={phase} phase={phase as any} />
        ))}

        <div ref={bottomRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 border-t">
        <ChatInput
          input={input}
          setInput={setInput}
          onSubmit={handleSubmit}
          isLoading={isLoading}
          isConnected={isConnected}
        />
        {!isConnected && (
          <p className="text-center text-gray-500 mt-2">Connecting to server...</p>
        )}
      </div>
    </div>
  );
};

export default ChatPage;

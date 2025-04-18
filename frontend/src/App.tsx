// frontend/src/App.tsx

import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';

// Import page components (we'll create these later)
import { LandingPage } from '@/pages/LandingPage'; // Renamed for clarity
import { ChatPage } from '@/pages/ChatPage';     // Renamed for clarity

// Import the ThemeProvider (we'll create this next)
import { ThemeProvider } from '@/context/ThemeContext';

// Import base CSS specific to App if needed,
// but global styles are usually in index.css
// import './App.css'; // Optional App-specific styles

const App: React.FC = () => {
  return (
    // Wrap the entire app in the ThemeProvider
    <ThemeProvider defaultTheme="system" storageKey="grokstem-theme">
      {/* Use BrowserRouter for client-side routing */}
      <Router>
        {/* Main container - applies theme-based background/text color */}
        <div className="w-full min-h-screen bg-background text-foreground transition-colors duration-200">
          {/* Define application routes */}
          <Routes>
            {/* Route for the landing page */}
            <Route path="/" element={<LandingPage />} />
            {/* Route for the chat interface */}
            <Route path="/chat" element={<ChatPage />} />
            {/* Add other routes here if needed */}
          </Routes>
        </div>
      </Router>
    </ThemeProvider>
  );
};

export default App;
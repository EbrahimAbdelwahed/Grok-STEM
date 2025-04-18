// frontend/src/main.tsx

import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App' // Import the main application component
import './index.css'  // Import global styles & Tailwind

// Find the root DOM element where the React app will be mounted
const rootElement = document.getElementById('root');

// Ensure the root element exists before attempting to render
if (!rootElement) {
  throw new Error("Failed to find the root element with ID 'root'. Make sure it exists in your index.html.");
}

// Create a React root and render the application
ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    {/* App component contains the Router and ThemeProvider */}
    <App />
  </React.StrictMode>,
)
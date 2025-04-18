// frontend/src/context/ThemeContext.tsx

import React, { createContext, useContext, useState, useEffect } from 'react';

// Define the possible theme values
type Theme = "dark" | "light" | "system";

// Define the shape of the context state and actions
interface ThemeProviderState {
  theme: Theme;
  setTheme: (theme: Theme) => void;
}

// Define the initial state
const initialState: ThemeProviderState = {
  theme: "system", // Default to system preference
  setTheme: () => null, // Placeholder function
};

// Create the context
const ThemeProviderContext = createContext<ThemeProviderState>(initialState);

// Define the props for the provider component
interface ThemeProviderProps {
  children: React.ReactNode;
  defaultTheme?: Theme;
  storageKey?: string;
}

// Create the provider component
export function ThemeProvider({
  children,
  defaultTheme = "system",
  storageKey = "vite-ui-theme", // Unique key for localStorage
  ...props
}: ThemeProviderProps) {
  // State to hold the current theme
  const [theme, setTheme] = useState<Theme>(
    // Initialize state from localStorage or use default
    () => (localStorage.getItem(storageKey) as Theme) || defaultTheme
  );

  // Effect to apply the theme class to the root element and update localStorage
  useEffect(() => {
    const root = window.document.documentElement;

    root.classList.remove("light", "dark"); // Remove previous theme classes

    let systemTheme: Theme = 'light'; // Default system theme assumption
    if (theme === "system") {
      // Check the user's OS preference
      systemTheme = window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light";
    }

    const effectiveTheme = theme === "system" ? systemTheme : theme;
    root.classList.add(effectiveTheme); // Add the current theme class (light or dark)

    // Store the selected theme (even if it's "system")
    localStorage.setItem(storageKey, theme);

  }, [theme, storageKey]); // Re-run effect when theme or storageKey changes

  // Value provided by the context
  const value = {
    theme,
    setTheme: (newTheme: Theme) => {
      setTheme(newTheme); // Update state, which triggers the useEffect
    },
  };

  return (
    <ThemeProviderContext.Provider {...props} value={value}>
      {children}
    </ThemeProviderContext.Provider>
  );
}

// Custom hook to easily consume the theme context
export const useTheme = () => {
  const context = useContext(ThemeProviderContext);

  if (context === undefined) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }

  return context;
};
// frontend/tailwind.config.js

/** @type {import('tailwindcss').Config} */
export default {
  // Enable dark mode based on the 'class' strategy (requires adding 'dark' class to <html> tag)
  darkMode: ["class"],
  // Specify the files Tailwind should scan to find class names
  content: [
    "./index.html", // Scan the main HTML file
    "./src/**/*.{js,ts,jsx,tsx}", // Scan all JS/TS/JSX/TSX files in the src directory
  ],
  // Define theme customizations
  theme: {
    // Define custom fonts (requires importing fonts via CSS)
    fontFamily: {
      sans: ['Inter', 'sans-serif'], // Example sans-serif stack
      // Add mono font if needed:
      // mono: ['JetBrains Mono', 'monospace'],
    },
    // Extend the default theme
    extend: {
      // Define custom colors using CSS variables (shadcn/ui pattern)
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        // Custom color for GrokSTEM branding
        grokstem: {
          DEFAULT: 'hsl(262.1 83.3% 57.8%)', // Example Purple (adjust as needed)
          light: 'hsl(262.1 83.3% 65%)',
          dark: 'hsl(262.1 83.3% 50%)',
        }
      },
      // Define custom border radius using CSS variables (shadcn/ui pattern)
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      // Define custom keyframes for animations (used by tailwindcss-animate)
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
      },
      // Define custom animations
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
    },
  },
  // Include Tailwind plugins
  plugins: [
    require("tailwindcss-animate"), // For animation utilities
    require("@tailwindcss/typography") // For styling markdown content (`prose` classes)
  ],
}
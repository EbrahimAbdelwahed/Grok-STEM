// frontend/src/pages/LandingPage.tsx

import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, BrainCircuit, Beaker, Sigma, BarChart3, Lock } from 'lucide-react'; // Using more relevant icons
import { Button } from '@/components/ui/button'; // Assuming shadcn/ui button

export const LandingPage: React.FC = () => {
  const navigate = useNavigate();

  const handleStartChat = () => {
    console.debug("LandingPage: Start Chat button clicked.");  // NEW
    navigate('/chat');
  };

  return (
    <div className="flex flex-col min-h-screen">
      {/* Optional Header for Landing Page if needed */}
      {/* <header className="container mx-auto px-4 py-4 border-b"> */}
      {/*   <h1 className="text-2xl font-bold text-grokstem">GrokSTEM</h1> */}
      {/* </header> */}

      <main className="flex-grow">
        {/* Hero Section */}
        <section className="container mx-auto px-4 pt-24 pb-16 text-center">
          <h1 className="text-4xl md:text-6xl font-bold mb-6 bg-gradient-to-r from-purple-600 via-grokstem to-indigo-600 bg-clip-text text-transparent">
            Welcome to GrokSTEM
          </h1>
          <p className="text-lg md:text-xl text-muted-foreground mb-8 max-w-3xl mx-auto">
            Your AI-powered reasoning assistant for mastering complex STEM subjects. Get step-by-step explanations, generate visualizations, and deepen your understanding.
          </p>
          <Button
            onClick={handleStartChat}
            size="lg" // Larger button size
            className="bg-grokstem hover:bg-grokstem/90 text-primary-foreground px-8 py-6 rounded-lg text-lg font-semibold transition-transform hover:scale-105 shadow-md hover:shadow-lg"
          >
            Start Exploring
            <ArrowRight className="ml-2 h-5 w-5" />
          </Button>
        </section>

        {/* Features Section */}
        <section className="bg-secondary py-16">
          <div className="container mx-auto px-4">
            <h2 className="text-3xl font-bold text-center mb-12">How GrokSTEM Helps You</h2>
            <div className="grid md:grid-cols-3 gap-8">
              {/* Feature 1 */}
              <div className="bg-card p-6 rounded-xl shadow-sm hover:shadow-md transition-shadow text-center">
                <div className="inline-flex bg-primary/10 text-primary w-14 h-14 rounded-full items-center justify-center mb-4">
                  <BrainCircuit size={32} />
                </div>
                <h3 className="text-xl font-semibold mb-3">Step-by-Step Reasoning</h3>
                <p className="text-muted-foreground">
                  Breaks down complex problems into understandable steps, clarifying the logic behind each part of the solution.
                </p>
              </div>
              {/* Feature 2 */}
              <div className="bg-card p-6 rounded-xl shadow-sm hover:shadow-md transition-shadow text-center">
                <div className="inline-flex bg-grokstem/10 text-grokstem w-14 h-14 rounded-full items-center justify-center mb-4">
                  <BarChart3 size={32} />
                </div>
                <h3 className="text-xl font-semibold mb-3">Dynamic Plotting</h3>
                <p className="text-muted-foreground">
                  Generates relevant plots and visualizations on-the-fly to help you grasp data and functions visually.
                </p>
              </div>
              {/* Feature 3 */}
              <div className="bg-card p-6 rounded-xl shadow-sm hover:shadow-md transition-shadow text-center">
                <div className="inline-flex bg-destructive/10 text-destructive w-14 h-14 rounded-full items-center justify-center mb-4">
                  <Beaker size={32} /> {/* Or Sigma for Math */}
                </div>
                <h3 className="text-xl font-semibold mb-3">Broad STEM Coverage</h3>
                <p className="text-muted-foreground">
                  Tackles questions across Physics, Chemistry, Mathematics, Engineering, and more, powered by advanced AI.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* (Optional) Add more sections like Testimonials, How it Works, etc. */}

      </main>

      {/* Footer */}
      <footer className="container mx-auto px-4 py-6 text-center text-muted-foreground border-t">
        <p>© {new Date().getFullYear()} GrokSTEM. Built with Open Source.</p>
        {/* Add links to GitHub, etc. if desired */}
      </footer>
    </div>
  );
};

// Export the component
export default LandingPage;
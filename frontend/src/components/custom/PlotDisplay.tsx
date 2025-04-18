// frontend/src/components/custom/PlotDisplay.tsx
import React, { Suspense, lazy } from 'react';
import { PlotlyData } from '../../interfaces/interfaces';

// Lazy load Plotly component for better initial page load performance
const Plot = lazy(() => import('react-plotly.js'));

interface PlotDisplayProps {
  plotlyData: PlotlyData;
}

export const PlotDisplay: React.FC<PlotDisplayProps> = ({ plotlyData }) => {
  // Basic check if data is valid
  if (!plotlyData || !plotlyData.data || !plotlyData.layout) {
    return <div className="text-destructive text-sm">Invalid plot data received.</div>;
  }

  return (
    <div className="my-4 p-2 bg-card rounded-md border shadow-sm overflow-hidden">
       {/* Suspense fallback while the Plotly component loads */}
      <Suspense fallback={<div className="text-center p-4 text-muted-foreground">Loading plot...</div>}>
        <Plot
          data={plotlyData.data}
          layout={{
            ...plotlyData.layout,
            autosize: true, // Ensure layout adapts
             // Optional: Force a white background for plots even in dark mode for better contrast?
             // paper_bgcolor: 'white',
             // plot_bgcolor: 'rgba(240,240,240,0.8)', // Slightly off-white plot area
             // font: { color: '#333' } // Dark font color
          }}
          config={{
            responsive: true, // Make plot responsive
            displaylogo: false, // Hide Plotly logo
            // Add other config options if needed: https://plotly.com/javascript/configuration-options/
             // modeBarButtonsToRemove: ['toImage', 'sendDataToCloud']
          }}
          useResizeHandler={true} // Automatically handles resizing
          className="w-full h-full min-h-[300px]" // Ensure it takes space
          style={{ width: '100%', height: '100%' }}
        />
      </Suspense>
    </div>
  );
};
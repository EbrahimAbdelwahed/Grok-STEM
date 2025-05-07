// frontend/src/components/custom/PlotDisplay.tsx
import React from 'react';
import Plot from 'react-plotly.js';

interface PlotDisplayProps {
  plotlyJson: any;
}

export const PlotDisplay: React.FC<PlotDisplayProps> = ({ plotlyJson }) => {
  if (!plotlyJson) {
    return (
      <div className="flex items-center justify-center p-4">
        <svg
          className="animate-spin h-6 w-6 text-gray-500"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8v8H4z"
          />
        </svg>
      </div>
    );
  }

  return (
    <div className="w-full h-auto my-4">
      <Plot
        data={plotlyJson.data}
        layout={{ ...plotlyJson.layout, autosize: true }}
        config={{ responsive: true }}
        useResizeHandler={true}
        style={{ width: '100%', height: '100%' }}
      />
    </div>
  );
};

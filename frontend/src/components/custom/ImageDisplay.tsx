// frontend/src/components/custom/ImageDisplay.tsx
import React from 'react';
import { Card, CardContent, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Download, RotateCw, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils'; // Assuming you have this utility

export type ImageState = 'loading' | 'success' | 'error' | 'retrying' | 'idle';

interface ImageDisplayProps {
  imageUrl: string | null;
  imageState: ImageState;
  imageError: string | null;
  retryCount?: number; // Optional, maybe useful for retry state
  prompt?: string; // Optional prompt for alt text/context
  onRetry?: () => void; // Function to call when retry button is clicked
  className?: string;
}

export const ImageDisplay: React.FC<ImageDisplayProps> = ({
  imageUrl,
  imageState,
  imageError,
  prompt = 'Generated STEM illustration',
  onRetry,
  className,
}) => {

  const handleDownload = () => {
    if (imageUrl) {
      const link = document.createElement('a');
      link.href = imageUrl;
      // Suggest a filename (browser might override)
      link.download = prompt.replace(/[^a-z0-9]/gi, '_').toLowerCase() + '.png';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  const renderContent = () => {
    switch (imageState) {
      case 'loading':
      case 'retrying':
        return (
          <div className="flex flex-col items-center justify-center h-48 text-muted-foreground">
            <svg
              className="animate-spin h-8 w-8 mb-2"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            <p className="text-sm">{imageState === 'retrying' ? 'Retrying generation...' : 'Generating image...'}</p>
          </div>
        );

      case 'success':
        if (imageUrl) {
          return (
            <img
              src={imageUrl}
              alt={prompt}
              className="w-full h-auto object-contain max-h-[400px] rounded-t-lg" // Adjust max height as needed
            />
          );
        }
        // Fallthrough if URL is somehow missing on success state (shouldn't happen)
        return (
             <div className="flex flex-col items-center justify-center h-48 text-destructive">
                <AlertTriangle className="h-8 w-8 mb-2"/>
                <p className="text-sm font-medium">Image URL missing.</p>
             </div>
        );


      case 'error':
        return (
          <div className="flex flex-col items-center justify-center h-48 text-destructive p-4 text-center">
            <AlertTriangle className="h-8 w-8 mb-2"/>
            <p className="text-sm font-medium mb-2">Image Generation Failed</p>
            <p className="text-xs mb-4">{imageError || 'An unknown error occurred.'}</p>
            {onRetry && ( // Only show retry if handler is provided
              <Button size="sm" variant="destructive" onClick={onRetry}>
                <RotateCw className="mr-2 h-4 w-4" /> Retry
              </Button>
            )}
          </div>
        );

      case 'idle':
      default:
        return <div className="h-48 bg-muted/50 flex items-center justify-center text-muted-foreground text-sm">No image generated yet.</div>; // Placeholder
    }
  };

  return (
    <Card className={cn("overflow-hidden my-2", className)}>
      <CardContent className="p-0">
        {renderContent()}
      </CardContent>
      {imageState === 'success' && imageUrl && (
        <CardFooter className="p-2 justify-end">
          <Button size="sm" variant="outline" onClick={handleDownload}>
            <Download className="mr-2 h-4 w-4" /> Download
          </Button>
        </CardFooter>
      )}
    </Card>
  );
};
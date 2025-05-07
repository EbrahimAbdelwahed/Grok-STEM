// frontend/src/components/custom/Sidebar.tsx
import React from 'react';
import { StepNavigator } from './StepNavigator';
import { PlotDisplay } from './PlotDisplay';
import { ImageDisplay, ImageState } from './ImageDisplay';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';

interface Step {
  id: string;
  title: string;
}

export interface SidebarContentData {
  messageId: string | null; // ID of the message this content belongs to
  steps: Step[] | null;
  plotJson: any | null;
  imageUrl: string | null;
  imageState: ImageState;
  imageError: string | null;
  imagePromptUsed?: string | null; // Prompt used, for alt text or retry context
  onImageRetry?: () => void; // Callback for retry button
}

interface SidebarProps {
  content: SidebarContentData;
}

export const Sidebar: React.FC<SidebarProps> = ({ content }) => {
  const {
    messageId,
    steps,
    plotJson,
    imageUrl,
    imageState,
    imageError,
    imagePromptUsed,
    onImageRetry
  } = content;

  // Determine if anything should be shown in the sidebar
  const hasSteps = steps && steps.length > 0;
  const hasPlot = plotJson !== null;
  const showImageArea = imageState !== 'idle' || imageUrl !== null; // Show if loading, error, or success

  // If no content and no image activity, show nothing or a placeholder
  if (!messageId || (!hasSteps && !hasPlot && !showImageArea)) {
    return (
      <div className="p-4 text-sm text-muted-foreground h-full flex items-center justify-center">
        Visuals & Steps will appear here.
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4 h-full overflow-y-auto"> {/* Add scroll */}
      {/* Step Navigator */}
      {hasSteps && (
         <Card>
            <CardHeader className="p-3">
                <CardTitle className="text-base">Steps</CardTitle>
            </CardHeader>
            <CardContent className="p-3 pt-0">
                <StepNavigator steps={steps!} />
            </CardContent>
         </Card>
      )}

      {/* Plot Display */}
      {hasPlot && (
        <Card>
            <CardHeader className="p-3">
                <CardTitle className="text-base">Plot</CardTitle>
            </CardHeader>
             <CardContent className="p-0"> {/* Plotly manages its own padding */}
                 <PlotDisplay plotlyJson={plotJson} />
             </CardContent>
        </Card>
      )}

      {/* Image Display Area */}
      {showImageArea && (
         <Card>
            <CardHeader className="p-3">
                <CardTitle className="text-base">Illustration</CardTitle>
            </CardHeader>
             {/* CardContent padding is handled by ImageDisplay */}
            <ImageDisplay
                imageUrl={imageUrl}
                imageState={imageState}
                imageError={imageError}
                prompt={imagePromptUsed || 'Generated STEM illustration'}
                onRetry={onImageRetry}
            />
         </Card>
      )}
    </div>
  );
};
/**
 * UI › Alert primitives
 * ---------------------------------------------------------------------------
 * Provides three named exports used throughout the app:
 *   • Alert              – container, supports `variant="default" | "destructive"`
 *   • AlertTitle         – headline inside the alert
 *   • AlertDescription   – body text inside the alert
 *
 * Styling follows the shadcn/ui conventions so it integrates seamlessly with
 * the rest of the component library already used in the project.
 */

import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils"; // Project‑level className utility

/* ------------------------------------------------------------------------- */
/* Variants                                                                  */
/* ------------------------------------------------------------------------- */

const alertVariants = cva(
  // Base styles
  "relative w-full rounded-lg border p-4" +
    " [&>svg]:absolute [&>svg]:left-4 [&>svg]:top-4" +
    " [&>svg]:text-muted-foreground" +
    " [&>h5]:pl-7 [&>p]:pl-7",
  {
    variants: {
      variant: {
        default: "bg-background text-foreground",
        destructive:
          "border-destructive/50 text-destructive dark:border-destructive" +
          " [&>svg]:text-destructive",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

/* ------------------------------------------------------------------------- */
/* Alert container                                                            */
/* ------------------------------------------------------------------------- */

export interface AlertProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof alertVariants> {}

export const Alert = React.forwardRef<HTMLDivElement, AlertProps>(
  ({ className, variant, ...props }, ref) => (
    <div
      ref={ref}
      role="alert"
      className={cn(alertVariants({ variant }), className)}
      {...props}
    />
  )
);

Alert.displayName = "Alert";

/* ------------------------------------------------------------------------- */
/* AlertTitle                                                                 */
/* ------------------------------------------------------------------------- */

export const AlertTitle = React.forwardRef<
  HTMLHeadingElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h5
    ref={ref}
    className={cn("mb-1 font-medium leading-none tracking-tight", className)}
    {...props}
  />
));

AlertTitle.displayName = "AlertTitle";

/* ------------------------------------------------------------------------- */
/* AlertDescription                                                           */
/* ------------------------------------------------------------------------- */

export const AlertDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn("text-sm [&_p]:leading-relaxed", className)}
    {...props}
  />
));

AlertDescription.displayName = "AlertDescription";
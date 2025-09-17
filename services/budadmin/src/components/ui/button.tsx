import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";
import { Button } from "@radix-ui/themes";

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive:
          "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline:
          "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const pagButton = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  },
);
pagButton.displayName = "Button";

const ButtonInput = ({ children, className = "", onClick, ...props }) => (
  <Button
    onClick={onClick}
    className={`blockButton h-[1.7rem] text-[#FFFFFF] text-xs font-normal leading-3 rounded-md px-[0.8rem] shadow-none !border-solid hover:border-white ${className}`}
    {...props}
  >
    {children}
  </Button>
);
const ButtonNoBgInput = ({ children, className = "", onClick, ...props }) => (
  <Button
    onClick={onClick}
    className={`blockButton h-[1.7rem] text-[#FFFFFF] text-xs font-normal leading-3 rounded-md px-[0.8rem] shadow-none bg-transparent hover:border-white ${className}`}
    {...props}
  >
    {children}
  </Button>
);

export { pagButton, buttonVariants, ButtonInput, ButtonNoBgInput };

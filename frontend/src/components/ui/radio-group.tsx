import * as RadioGroupPrimitive from "@radix-ui/react-radio-group";
import { Circle } from "lucide-react";
import { type ComponentProps } from "react";
import { cn } from "@/lib/utils";

const RadioGroup = RadioGroupPrimitive.Root;
const RadioGroupItem = RadioGroupPrimitive.Item;

const RadioGroupIndicator = ({
  className,
  ...props
}: ComponentProps<typeof RadioGroupPrimitive.Indicator>) => (
  <RadioGroupPrimitive.Indicator
    className={cn("flex items-center justify-center", className)}
    {...props}
  >
    <Circle className="size-2.5 fill-current text-current" />
  </RadioGroupPrimitive.Indicator>
);

const RadioGroupItemStyled = ({
  className,
  ...props
}: ComponentProps<typeof RadioGroupPrimitive.Item>) => (
  <RadioGroupPrimitive.Item
    className={cn(
      "aspect-square size-4 rounded-full border border-primary text-primary",
      "focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
      "disabled:cursor-not-allowed disabled:opacity-50",
      "data-[state=checked]:border-primary",
      className
    )}
    {...props}
  >
    <RadioGroupIndicator />
  </RadioGroupPrimitive.Item>
);

export {
  RadioGroup,
  RadioGroupItem,
  RadioGroupItemStyled,
  RadioGroupIndicator,
};

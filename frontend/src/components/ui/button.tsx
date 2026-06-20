import type { ButtonHTMLAttributes } from "react";

import {
  buttonVariants,
  type ButtonSize,
  type ButtonVariant,
} from "./button-styles";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
};

export function Button({
  className,
  variant = "primary",
  size = "md",
  type = "button",
  ...props
}: ButtonProps) {
  return (
    <button
      className={buttonVariants({ className, variant, size })}
      type={type}
      {...props}
    />
  );
}

export function Logo({ variant = "black", className = "h-6" }: { variant?: "black" | "white"; className?: string }) {
  return <img src={`/brand/logo-${variant}.png`} alt="Huware" className={`w-auto max-w-none shrink-0 self-start object-contain select-none ${className}`} draggable={false} />;
}

"use client";

import React from "react";
import { cn } from "@/lib/utils";

interface CharacteristicChipProps {
  label: string;
  selected: boolean;
  onClick: () => void;
}

export function CharacteristicChip({
  label,
  selected,
  onClick,
}: CharacteristicChipProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "px-4 py-1.5 rounded-full text-sm font-medium transition-all border",
        selected
          ? "bg-accent/20 text-accent border-accent/50"
          : "bg-card text-muted-foreground border-input hover:border-muted-foreground hover:text-foreground"
      )}
    >
      {label.charAt(0).toUpperCase() + label.slice(1)}
    </button>
  );
}
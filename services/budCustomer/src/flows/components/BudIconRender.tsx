import React from 'react';

interface IconRenderProps {
  icon?: string;
  emoji?: string;
  size?: number;
  className?: string;
}

export default function IconRender({ icon, emoji, size = 24, className = "" }: IconRenderProps) {
  if (emoji) {
    return <span className={className} style={{ fontSize: size }}>{emoji}</span>;
  }
  
  if (icon) {
    return <img src={icon} alt="icon" width={size} height={size} className={className} />;
  }
  
  return <div className={`bg-gray-300 rounded ${className}`} style={{ width: size, height: size }} />;
}
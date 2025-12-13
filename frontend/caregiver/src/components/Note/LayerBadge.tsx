import clsx from 'clsx';
import type { MemoryLayer } from '../../types/note';
import { LAYER_CONFIG } from '../../types/note';

interface LayerBadgeProps {
  layer: MemoryLayer;
  size?: 'sm' | 'md';
}

export function LayerBadge({ layer, size = 'md' }: LayerBadgeProps) {
  const config = LAYER_CONFIG[layer];

  return (
    <span
      className={clsx(
        'inline-flex items-center font-medium rounded-full',
        config.bgColor,
        config.color,
        size === 'sm' && 'px-2 py-0.5 text-xs',
        size === 'md' && 'px-2.5 py-1 text-sm'
      )}
    >
      {config.label}
    </span>
  );
}

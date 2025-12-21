import clsx from 'clsx';
import type { MemoryLayer } from '../../types/note';
import { LAYER_CONFIG } from '../../types/note';

interface LayerBadgeProps {
  layer: MemoryLayer;
  size?: 'sm' | 'md' | 'lg';
  showIcon?: boolean;
  showLevel?: boolean;
}

export function LayerBadge({
  layer,
  size = 'md',
  showIcon = false,
  showLevel = false,
}: LayerBadgeProps) {
  const config = LAYER_CONFIG[layer];

  // 显示内容：图标 + 标签 或 短标签
  const displayText = showLevel ? config.shortLabel : config.label;

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 font-medium rounded-full',
        config.bgColor,
        config.color,
        size === 'sm' && 'px-2 py-0.5 text-xs',
        size === 'md' && 'px-2.5 py-1 text-sm',
        size === 'lg' && 'px-3 py-1.5 text-base'
      )}
      title={`${config.icon} ${config.label}`}
    >
      {showIcon && <span>{config.icon}</span>}
      {displayText}
    </span>
  );
}

import clsx from 'clsx';

interface LoadingProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  text?: string;
}

export function Loading({ size = 'md', className, text }: LoadingProps) {
  if (text) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <div
          className={clsx(
            'animate-spin rounded-full border-2 border-gray-300 border-t-blue-600',
            size === 'sm' && 'h-4 w-4',
            size === 'md' && 'h-8 w-8',
            size === 'lg' && 'h-12 w-12'
          )}
        />
        <p className="mt-4 text-gray-500">{text}</p>
      </div>
    );
  }
  return (
    <div className={clsx('flex items-center justify-center', className)}>
      <div
        className={clsx(
          'animate-spin rounded-full border-2 border-gray-300 border-t-blue-600',
          size === 'sm' && 'h-4 w-4',
          size === 'md' && 'h-8 w-8',
          size === 'lg' && 'h-12 w-12'
        )}
      />
    </div>
  );
}

interface LoadingOverlayProps {
  text?: string;
}

export function LoadingOverlay({ text = '加载中...' }: LoadingOverlayProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12">
      <Loading size="lg" />
      <p className="mt-4 text-gray-500">{text}</p>
    </div>
  );
}

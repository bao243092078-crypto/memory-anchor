import { useState } from 'react';
import { useTranslation } from 'react-i18next';

interface JsonViewerProps {
  data: unknown;
}

export function JsonViewer({ data }: JsonViewerProps) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  const jsonString = JSON.stringify(data, null, 2);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(jsonString);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <div className="relative">
      {/* Copy button */}
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-200 transition-colors z-10"
        title={t('json.copy')}
      >
        {copied ? (
          <svg className="w-4 h-4 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        ) : (
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
        )}
      </button>

      {/* JSON content */}
      <pre className="bg-gray-900 text-gray-100 rounded-xl p-4 overflow-x-auto text-xs font-mono leading-relaxed">
        <code>{highlightJson(jsonString)}</code>
      </pre>
    </div>
  );
}

// Simple JSON syntax highlighting
function highlightJson(json: string): React.ReactNode {
  const lines = json.split('\n');

  return lines.map((line, index) => {
    // Highlight different parts
    const highlighted = line
      // Keys
      .replace(/"([^"]+)":/g, '<span class="text-purple-400">"$1"</span>:')
      // String values
      .replace(/: "([^"]*)"/g, ': <span class="text-green-400">"$1"</span>')
      // Numbers
      .replace(/: (\d+\.?\d*)/g, ': <span class="text-amber-400">$1</span>')
      // Booleans
      .replace(/: (true|false)/g, ': <span class="text-blue-400">$1</span>')
      // Null
      .replace(/: (null)/g, ': <span class="text-gray-500">$1</span>');

    return (
      <span key={index}>
        <span dangerouslySetInnerHTML={{ __html: highlighted }} />
        {index < lines.length - 1 && '\n'}
      </span>
    );
  });
}

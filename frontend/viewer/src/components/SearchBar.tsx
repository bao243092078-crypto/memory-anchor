import { useState, useCallback } from 'react';

interface SearchBarProps {
  onSearch: (query: string) => void;
  onClear: () => void;
  isSearching: boolean;
  currentQuery: string;
}

export function SearchBar({ onSearch, onClear, isSearching, currentQuery }: SearchBarProps) {
  const [inputValue, setInputValue] = useState(currentQuery);

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    if (inputValue.trim()) {
      onSearch(inputValue.trim());
    }
  }, [inputValue, onSearch]);

  const handleClear = useCallback(() => {
    setInputValue('');
    onClear();
  }, [onClear]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      handleClear();
    }
  }, [handleClear]);

  return (
    <form onSubmit={handleSubmit} className="relative">
      <div className="relative">
        {/* Search Icon */}
        <div className="absolute left-4 top-1/2 -translate-y-1/2 pointer-events-none">
          {isSearching ? (
            <svg className="w-5 h-5 text-lime-500 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
          ) : (
            <svg className="w-5 h-5 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          )}
        </div>

        {/* Input */}
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Search memories semantically..."
          className="
            w-full h-14 pl-12 pr-32
            bg-white border border-gray-200 rounded-2xl
            text-sm text-gray-900 placeholder:text-gray-400
            focus:outline-none focus:ring-2 focus:ring-lime-500/20 focus:border-lime-500
            transition-all duration-200
          "
        />

        {/* Actions */}
        <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-2">
          {currentQuery && (
            <button
              type="button"
              onClick={handleClear}
              className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
          <button
            type="submit"
            disabled={isSearching || !inputValue.trim()}
            className="
              h-10 px-5 rounded-xl
              bg-gray-900 text-white text-sm font-medium
              hover:bg-gray-800
              disabled:bg-gray-100 disabled:text-gray-400 disabled:cursor-not-allowed
              transition-all duration-200
              flex items-center gap-2
            "
          >
            {isSearching ? (
              <>
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Searching
              </>
            ) : (
              <>
                Search
                <kbd className="hidden sm:inline-flex items-center px-1.5 py-0.5 rounded bg-white/10 text-[10px] font-mono">
                  ↵
                </kbd>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Helper text */}
      <p className="mt-2 text-xs text-gray-400 pl-1">
        {currentQuery ? (
          <>
            Showing results for "<span className="text-gray-600 font-medium">{currentQuery}</span>"
          </>
        ) : (
          'Search across all memory content using semantic similarity'
        )}
      </p>
    </form>
  );
}

import { useTranslation } from 'react-i18next';
import type { MemoryLayer, NoteCategory } from '../types';
import { LAYER_CONFIG, CATEGORY_CONFIG } from '../types';

interface FilterPanelProps {
  selectedLayer: MemoryLayer | null;
  selectedCategories: NoteCategory[];
  onLayerChange: (layer: MemoryLayer | null) => void;
  onCategoryToggle: (category: NoteCategory) => void;
  onClearFilters: () => void;
}

const LAYER_OPTIONS: { value: MemoryLayer | null; labelKey: string; shortLabel: string }[] = [
  { value: null, labelKey: 'common.all', shortLabel: '' },
  { value: 'identity_schema', labelKey: 'layer.identity_schema', shortLabel: 'L0' },
  { value: 'event_log', labelKey: 'layer.event_log', shortLabel: 'L2' },
  { value: 'verified_fact', labelKey: 'layer.verified_fact', shortLabel: 'L3' },
  { value: 'operational_knowledge', labelKey: 'layer.operational_knowledge', shortLabel: 'L4' },
];

const CATEGORY_OPTIONS: NoteCategory[] = ['person', 'place', 'event', 'item', 'routine'];

export function FilterPanel({
  selectedLayer,
  selectedCategories,
  onLayerChange,
  onCategoryToggle,
  onClearFilters,
}: FilterPanelProps) {
  const { t } = useTranslation();
  const hasFilters = selectedLayer !== null || selectedCategories.length > 0;

  return (
    <aside className="w-64 flex-shrink-0">
      <div className="sticky top-24 space-y-6">
        {/* Section: Layers */}
        <div className="bg-white rounded-2xl border border-gray-100 p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xs font-semibold text-gray-400 tracking-wider">
              {t('filter.layers')}
            </h3>
            {hasFilters && (
              <button
                onClick={onClearFilters}
                className="text-xs text-lime-600 hover:text-lime-700 font-medium transition-colors"
              >
                {t('filter.clearFilters')}
              </button>
            )}
          </div>

          <div className="space-y-1">
            {LAYER_OPTIONS.map((option) => {
              const isSelected = selectedLayer === option.value;
              const layerConfig = option.value ? LAYER_CONFIG[option.value] : null;

              return (
                <button
                  key={option.value ?? 'all'}
                  onClick={() => onLayerChange(option.value)}
                  className={`
                    w-full flex items-center gap-3 px-3 py-2.5 rounded-xl
                    text-left text-sm font-medium transition-all duration-200
                    ${isSelected
                      ? 'bg-gray-900 text-white shadow-sm'
                      : 'text-gray-600 hover:bg-gray-50'
                    }
                  `}
                >
                  {layerConfig ? (
                    <span
                      className={`
                        w-6 h-6 rounded-lg flex items-center justify-center text-[10px] font-bold
                        ${isSelected ? 'bg-white/20 text-white' : layerConfig.color + ' text-white'}
                      `}
                    >
                      {option.shortLabel}
                    </span>
                  ) : (
                    <span className={`
                      w-6 h-6 rounded-lg flex items-center justify-center
                      ${isSelected ? 'bg-white/20' : 'bg-gray-100'}
                    `}>
                      <svg className={`w-3.5 h-3.5 ${isSelected ? 'text-white' : 'text-gray-400'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                      </svg>
                    </span>
                  )}
                  <span className="flex-1">{t(option.labelKey)}</span>
                  {isSelected && (
                    <svg className="w-4 h-4 text-lime-400" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Section: Categories */}
        <div className="bg-white rounded-2xl border border-gray-100 p-5">
          <h3 className="text-xs font-semibold text-gray-400 tracking-wider mb-4">
            {t('filter.categories')}
          </h3>

          <div className="space-y-1">
            {CATEGORY_OPTIONS.map((category) => {
              const config = CATEGORY_CONFIG[category];
              const isSelected = selectedCategories.includes(category);

              return (
                <button
                  key={category}
                  onClick={() => onCategoryToggle(category)}
                  className={`
                    w-full flex items-center gap-3 px-3 py-2.5 rounded-xl
                    text-left text-sm font-medium transition-all duration-200
                    ${isSelected
                      ? 'bg-lime-50 text-lime-700 border border-lime-200'
                      : 'text-gray-600 hover:bg-gray-50 border border-transparent'
                    }
                  `}
                >
                  <span className="text-base">{config.emoji}</span>
                  <span className="flex-1">{t(`category.${category}`)}</span>
                  {isSelected && (
                    <svg className="w-4 h-4 text-lime-600" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Layer Legend */}
        <div className="px-2">
          <h4 className="text-[10px] font-semibold text-gray-300 tracking-wider mb-3">
            {t('filter.layers')}
          </h4>
          <div className="space-y-2 text-[11px]">
            <div className="flex items-center gap-2">
              <span className="w-5 h-5 rounded bg-red-500 flex items-center justify-center text-white text-[9px] font-bold">L0</span>
              <span className="text-gray-400">{t('layer.identity_schema')}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-5 h-5 rounded bg-yellow-500 flex items-center justify-center text-white text-[9px] font-bold">L2</span>
              <span className="text-gray-400">{t('layer.event_log')}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-5 h-5 rounded bg-lime-500 flex items-center justify-center text-white text-[9px] font-bold">L3</span>
              <span className="text-gray-400">{t('layer.verified_fact')}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-5 h-5 rounded bg-blue-500 flex items-center justify-center text-white text-[9px] font-bold">L4</span>
              <span className="text-gray-400">{t('layer.operational_knowledge')}</span>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}

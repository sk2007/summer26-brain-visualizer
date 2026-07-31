import React, { useState, useEffect } from 'react';

const baseURL = process.env.NEXT_PUBLIC_API_BASE_URL;

interface FilterItem {
  id: string;
  name: string;
  active: boolean;
  activeFilters: string[];
}

interface PlotlyConfig {
  data: any;
  layout: any;
}

interface NewChartModalProps {
  isOpen: boolean;
  onClose: () => void;
  onChartCreated: (chartId: string, config: PlotlyConfig) => void;
}

// Chart type options
const chartTypes = [
  { id: 'line_chart', name: 'Line Chart' },
  { id: 'bar_chart', name: 'Bar Chart' },
  { id: 'scatter_plot', name: 'Scatter Plot' },
  { id: 'histogram', name: 'Histogram' },
  { id: 'box_plot', name: 'Box Plot' },
  { id: 'bubble_chart', name: 'Bubble Chart' }
];

export default function NewChartModal({ isOpen, onClose, onChartCreated }: NewChartModalProps) {
  const [filters, setFilters] = useState<FilterItem[]>([]);
  const [selectedFilter, setSelectedFilter] = useState<string>('');
  const [selectedChartType, setSelectedChartType] = useState<string>('');
  const [chartSettings, setChartSettings] = useState({
    title: '',
    xaxis_title: '',
    yaxis_title: ''
  });

  const [fieldDefs, setFieldDefs] = useState<{ key: string; label: string; type: string }[]>([]);
  const [selectedXField, setSelectedXField] = useState<string>('');
  const [selectedYField, setSelectedYField] = useState<string>('');
  const [isFetchingData, setIsFetchingData] = useState(false);
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);

  // Fetch filters on component mount
  useEffect(() => {
    if (isOpen) {
      fetch(`${baseURL}/api/filters`, {
        method: 'GET',
        headers: {
          'Accept': 'application/json'
        },
        credentials: 'include'  // Include session cookies
      })
      .then(response => response.json())
      .then(data => {
        const filterItems: FilterItem[] = [];
        Object.keys(data).forEach((id) => {
          const curFilter: FilterItem = {
            id: id,
            name: data[id].name,
            active: (id === 'default_id') ? true : false,
            activeFilters: data[id].options
          };
          filterItems.push(curFilter);
        });
        setFilters(filterItems);

        // Set default selected filter to the active one
        const activeFilter = filterItems.find(f => f.active);
        if (activeFilter) {
          setSelectedFilter(activeFilter.id);
        }
      })
      .catch(error => {
        console.error('Error fetching filters:', error);
      });
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    fetch(`${baseURL}/api/chart-fields`, { credentials: 'include' })
      .then((r) => r.json())
      .then((data) => { if (!cancelled) setFieldDefs(data.fields || []); })
      .catch((e) => { if (!cancelled) console.error('Error fetching chart fields:', e); });
    return () => { cancelled = true; };
  }, [isOpen]);

  // Handle form input changes
  const handleSettingsChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setChartSettings(prev => ({
      ...prev,
      [name]: value
    }));
  };

  // Reset the form
  const resetForm = () => {
    setSelectedChartType('');
    setChartSettings({
      title: '',
      xaxis_title: '',
      yaxis_title: ''
    });
    setSelectedXField('');
    setSelectedYField('');
    setIsFetchingData(false);
    setErrorMessage(null);
  };

  // Handle chart creation
  const createChart = async () => {
    if (!selectedChartType || !selectedXField || !selectedYField) return;
    setErrorMessage(null);
    setIsFetchingData(true);
    try {
      // 1. Fetch field data from the backend for the active filter
      const dataRes = await fetch(`${baseURL}/api/chart-data`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify({
          filter_id: selectedFilter || 'default_id',
          x_field: selectedXField,
          y_field: selectedYField,
        }),
      });
      if (!dataRes.ok) {
        console.error('Failed to fetch chart data');
        setErrorMessage('Failed to fetch chart data. Please try again.');
        return;
      }
      const { x, y } = await dataRes.json();

      // 2. Build chart payload using the resolved data
      const chartId = crypto.randomUUID();
      const xLabel = fieldDefs.find((f) => f.key === selectedXField)?.label || selectedXField;
      const yLabel = fieldDefs.find((f) => f.key === selectedYField)?.label || selectedYField;

      const chartData = {
        id: chartId,
        type: selectedChartType,
        title: chartSettings.title || `${xLabel} vs ${yLabel}`,
        data: {
          xaxis_title: chartSettings.xaxis_title || xLabel,
          yaxis_title: chartSettings.yaxis_title || yLabel,
          series: [
            {
              name: 'Data',
              trace: { x, y },
            },
          ],
        },
      };

      // 3. POST to charts endpoint (unchanged format)
      const chartRes = await fetch(`${baseURL}/api/charts`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify(chartData),
      });
      if (!chartRes.ok) {
        console.error('Failed to create chart');
        setErrorMessage('Failed to create chart. Please try again.');
        return;
      }
      const config = await chartRes.json();
      onChartCreated(chartId, config);
      closeModal();
    } catch (e) {
      console.error('Error creating chart:', e);
    } finally {
      setIsFetchingData(false);
    }
  };

  // Handle modal close
  const closeModal = () => {
    resetForm();
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className='fixed inset-0 flex justify-center items-center bg-black bg-opacity-30 z-[100]'>
      <div className='bg-white rounded-lg shadow-lg p-6 max-w-2xl w-full overflow-y-auto max-h-[80vh]'>
        <div className='flex justify-between items-center mb-4'>
          <h2 className='text-lg font-semibold'>Create New Chart</h2>
          <button
            onClick={closeModal}
            className='text-gray-600 hover:text-gray-800'
          >
            Close
          </button>
        </div>

        {/* Filter Selection */}
        <div className='mb-4'>
          <label className='block text-sm font-medium text-gray-700 mb-1'>Select Filter</label>
          <select
            value={selectedFilter}
            onChange={(e) => setSelectedFilter(e.target.value)}
            className='w-full border border-gray-300 rounded p-2'
          >
            {filters.map((filter) => (
              <option key={filter.id} value={filter.id}>
                {filter.name}
              </option>
            ))}
          </select>
        </div>

        {/* Chart Type Selection */}
        <div className='mb-4'>
          <label className='block text-sm font-medium text-gray-700 mb-1'>Chart Type</label>
          <select
            value={selectedChartType}
            onChange={(e) => setSelectedChartType(e.target.value)}
            className='w-full border border-gray-300 rounded p-2'
          >
            <option value="">Select Chart Type</option>
            {chartTypes.map((chartType) => (
              <option key={chartType.id} value={chartType.id}>
                {chartType.name}
              </option>
            ))}
          </select>
        </div>

        {/* Chart Settings (if chart type is selected) */}
        {selectedChartType && (
          <div>
            <div className='mb-4'>
              <label className='block text-sm font-medium text-gray-700 mb-1'>Chart Title</label>
              <input
                type='text'
                name='title'
                value={chartSettings.title}
                onChange={handleSettingsChange}
                className='w-full border border-gray-300 rounded p-2'
                placeholder='Enter chart title'
              />
            </div>

            <div className='mb-4'>
              <label className='block text-sm font-medium text-gray-700 mb-1'>X-Axis Title</label>
              <input
                type='text'
                name='xaxis_title'
                value={chartSettings.xaxis_title}
                onChange={handleSettingsChange}
                className='w-full border border-gray-300 rounded p-2'
                placeholder='Enter x-axis title'
              />
            </div>

            <div className='mb-4'>
              <label className='block text-sm font-medium text-gray-700 mb-1'>Y-Axis Title</label>
              <input
                type='text'
                name='yaxis_title'
                value={chartSettings.yaxis_title}
                onChange={handleSettingsChange}
                className='w-full border border-gray-300 rounded p-2'
                placeholder='Enter y-axis title'
              />
            </div>

            {/* Field Selection */}
            <div className='mb-4'>
              <label className='block text-sm font-medium text-gray-700 mb-1'>X Axis Field</label>
              <select
                value={selectedXField}
                onChange={(e) => setSelectedXField(e.target.value)}
                className='w-full border border-gray-300 rounded p-2'
              >
                <option value="">Select a field…</option>
                {fieldDefs.map((f) => (
                  <option key={f.key} value={f.key}>{f.label}</option>
                ))}
              </select>
            </div>

            <div className='mb-4'>
              <label className='block text-sm font-medium text-gray-700 mb-1'>Y Axis Field</label>
              <select
                value={selectedYField}
                onChange={(e) => setSelectedYField(e.target.value)}
                className='w-full border border-gray-300 rounded p-2'
              >
                <option value="">Select a field…</option>
                {fieldDefs.map((f) => (
                  <option key={f.key} value={f.key}>{f.label}</option>
                ))}
              </select>
            </div>
          </div>
        )}

        <div className='flex justify-end space-x-2 mt-4'>
          <button
            onClick={closeModal}
            className='px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 transition-colors text-sm'
          >
            Cancel
          </button>
          <button
            onClick={createChart}
            disabled={!selectedChartType || !selectedXField || !selectedYField || isFetchingData}
            className={`px-4 py-2 bg-[#2774AE] text-white rounded-md transition-colors text-sm flex items-center gap-2 ${
              !selectedChartType || !selectedXField || !selectedYField || isFetchingData
                ? 'opacity-50 cursor-not-allowed'
                : 'hover:bg-blue-700'
            }`}
          >
            {isFetchingData && (
              <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
              </svg>
            )}
            {isFetchingData ? 'Loading data…' : 'Create Chart'}
          </button>
        </div>
        {errorMessage && (
          <p className="text-xs text-red-600 mt-1">{errorMessage}</p>
        )}
      </div>
    </div>
  );
}

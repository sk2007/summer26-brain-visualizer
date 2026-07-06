import React from 'react';
import { X, Maximize2, Minimize2, Brain } from 'lucide-react';

interface TumorItem {
  id: string;
  location: string;
  volume_mm3: number;
}

interface BrainViewerModalProps {
  isOpen: boolean;
  onClose: () => void;
  niftiId: string;
  title: string;
  dataType: 'mri' | 'tumor' | 'dose';
  tumorList?: TumorItem[];
}

export default function BrainViewerModal({
  isOpen,
  onClose,
  niftiId,
  title,
  dataType,
  tumorList = [],
}: BrainViewerModalProps) {
  const [isFullscreen, setIsFullscreen] = React.useState(false);

  if (!isOpen) return null;

  const viewerUrl = `/api/viewer/${niftiId}/test_db_nifti`;

  return (
    <div className="fixed inset-0 z-[100] bg-black bg-opacity-50 flex items-center justify-center p-4">
      <div
        className={`bg-white rounded-lg shadow-xl flex flex-col ${
          isFullscreen ? 'w-full h-full' : 'w-[90vw] h-[80vh] max-w-6xl'
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b bg-gray-50 rounded-t-lg">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
            <p className="text-sm text-gray-500 capitalize">{dataType} visualization</p>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setIsFullscreen(!isFullscreen)}
              className="p-2 hover:bg-gray-200 rounded-md transition-colors"
              title={isFullscreen ? 'Exit Fullscreen' : 'Enter Fullscreen'}
            >
              {isFullscreen ? (
                <Minimize2 className="w-5 h-5" />
              ) : (
                <Maximize2 className="w-5 h-5" />
              )}
            </button>
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-200 rounded-md transition-colors"
              title="Close"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Body: tumor panel + brain viewer */}
        <div className="flex flex-1 overflow-hidden rounded-b-lg">
          {/* Tumor info panel */}
          <div className="w-64 flex-shrink-0 bg-gray-900 text-white overflow-y-auto p-4 space-y-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-gray-400 mb-3">
                Tumor Summary
              </p>
              <p className="text-sm font-medium text-white">
                {tumorList.length === 0
                  ? 'No tumor data'
                  : `${tumorList.length} tumor${tumorList.length !== 1 ? 's' : ''} detected`}
              </p>
            </div>

            {tumorList.length > 0 && (
              <div className="space-y-3">
                {tumorList.map((tumor) => (
                  <div key={tumor.id} className="flex items-start space-x-2">
                    <Brain className="w-4 h-4 text-[#2774AE] mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="text-sm font-medium text-white">{tumor.location}</p>
                      <p className="text-xs text-gray-400">{tumor.volume_mm3.toFixed(1)} mm³</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Brain viewer iframe */}
          <div className="flex-1 bg-gray-100 overflow-hidden">
            <iframe
              src={viewerUrl}
              className="w-full h-full border-0"
              title={`Brain Viewer - ${title}`}
              sandbox="allow-scripts allow-same-origin allow-forms"
            />
          </div>
        </div>
      </div>
    </div>
  );
}

import React from 'react';
import { X, Maximize2, Minimize2, Brain, RotateCcw } from 'lucide-react';

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
  const [reloadKey, setReloadKey] = React.useState(0);
  const [niftiMeta, setNiftiMeta] = React.useState<{
    dims: number[];
    voxel_size_mm: number[];
  } | null>(null);
  const [metaError, setMetaError] = React.useState(false);

  React.useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    setNiftiMeta(null);
    setMetaError(false);
    fetch(`/api/nifti-info/${niftiId}`)
      .then((r) => {
        if (!r.ok) throw new Error('not found');
        return r.json();
      })
      .then((data) => { if (!cancelled) setNiftiMeta(data); })
      .catch(() => { if (!cancelled) setMetaError(true); });
    return () => { cancelled = true; };
  }, [isOpen, niftiId]);

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
              onClick={() => setReloadKey((k) => k + 1)}
              className="p-2 hover:bg-gray-200 rounded-md transition-colors"
              title="Reload viewer"
            >
              <RotateCcw className="w-5 h-5" />
            </button>
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

            {/* NIfTI Metadata */}
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-gray-400 mb-3">
                File Info
              </p>
              {niftiMeta ? (
                <div className="space-y-1.5 text-xs">
                  <div className="flex justify-between">
                    <span className="text-gray-400">Dimensions</span>
                    <span className="text-white font-mono">{niftiMeta.dims.join(' × ')}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Voxel size</span>
                    <span className="text-white font-mono">
                      {niftiMeta.voxel_size_mm.map((v) => v.toFixed(2)).join(' × ')} mm
                    </span>
                  </div>
                </div>
              ) : metaError ? (
                <p className="text-xs text-gray-500">Not available</p>
              ) : (
                <p className="text-xs text-gray-500 animate-pulse">Loading…</p>
              )}
            </div>
          </div>

          {/* Brain viewer iframe */}
          <div className="flex-1 bg-gray-100 overflow-hidden relative">
            <iframe
              key={reloadKey}
              src={viewerUrl}
              className="w-full h-full border-0"
              title={`Brain Viewer - ${title}`}
              sandbox="allow-scripts allow-same-origin allow-forms"
            />
            <div className="absolute bottom-3 right-3 pointer-events-none flex gap-3 bg-black/50 text-white text-xs rounded-md px-3 py-1.5 select-none">
              <span>Drag · Rotate</span>
              <span className="text-white/40">|</span>
              <span>Right-drag · Pan</span>
              <span className="text-white/40">|</span>
              <span>Scroll · Zoom</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

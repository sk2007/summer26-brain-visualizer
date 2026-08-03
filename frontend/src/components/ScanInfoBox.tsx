'use client';

import React, { useEffect, useState } from 'react';

interface FilterStats {
  filter_name: string;
  total_patients: number;
  current_mask_type: string;
}

interface PatientOverview {
  id: string;
  sex: string;
  height_cm: number;
  weight_kg: number;
  date_of_original_diagnosis: string | null;
  date_of_metastatic_diagnosis: string | null;
  data_summary: {
    tumor_masks: number;
    mri_masks: number;
    dose_masks: number;
  };
}

interface ScanInfoBoxProps {
  activeFilterId: string | null;
  activeMaskType: string;
  activeViewType: string;
  selectedPatient: { id: string; name: string } | null;
  sidebarWidth: number;
}

const MASK_LABELS: Record<string, string> = {
  tumor: 'Tumor mask',
  mri: 'MRI mask',
  dose: 'Dose mask',
};

const VIEW_LABELS: Record<string, string> = {
  surface: 'Surface',
  glass: 'Glass brain',
};

function Skeleton() {
  return (
    <div className="animate-pulse bg-gray-200 dark:bg-gray-600 rounded h-3 w-32" />
  );
}

export default function ScanInfoBox({
  activeFilterId,
  activeMaskType,
  activeViewType,
  selectedPatient,
  sidebarWidth,
}: ScanInfoBoxProps) {
  const [filterStats, setFilterStats] = useState<FilterStats | null>(null);
  const [filterLoading, setFilterLoading] = useState(false);
  const [filterError, setFilterError] = useState(false);

  const [patientOverview, setPatientOverview] = useState<PatientOverview | null>(null);
  const [patientLoading, setPatientLoading] = useState(false);
  const [patientError, setPatientError] = useState(false);

  // Fetch filter stats
  useEffect(() => {
    if (!activeFilterId) {
      setFilterStats(null);
      setFilterError(false);
      return;
    }
    const controller = new AbortController();
    setFilterLoading(true);
    setFilterError(false);
    fetch(`/api/filters/stats/${activeFilterId}?maskType=${activeMaskType}`, {
      signal: controller.signal,
      credentials: 'include',
    })
      .then((r) => {
        if (!r.ok) throw new Error('stats fetch failed');
        return r.json();
      })
      .then((data: FilterStats) => {
        setFilterStats(data);
        setFilterLoading(false);
      })
      .catch((err) => {
        if (err.name === 'AbortError') return;
        setFilterError(true);
        setFilterLoading(false);
      });
    return () => controller.abort();
  }, [activeFilterId, activeMaskType]);

  // Fetch patient overview
  useEffect(() => {
    if (!selectedPatient) {
      setPatientOverview(null);
      setPatientError(false);
      return;
    }
    const controller = new AbortController();
    setPatientLoading(true);
    setPatientError(false);
    fetch(`/api/patients/${selectedPatient.id}/overview`, {
      signal: controller.signal,
      credentials: 'include',
    })
      .then((r) => {
        if (!r.ok) throw new Error('overview fetch failed');
        return r.json();
      })
      .then((data: PatientOverview) => {
        setPatientOverview(data);
        setPatientLoading(false);
      })
      .catch((err) => {
        if (err.name === 'AbortError') return;
        setPatientError(true);
        setPatientLoading(false);
      });
    return () => controller.abort();
  }, [selectedPatient]);

  const leftOffset = sidebarWidth + 16;

  return (
    <div
      className="fixed bottom-4 z-30 w-72 bg-white/90 dark:bg-gray-800/90 backdrop-blur-sm shadow-md rounded-xl p-3 text-sm transition-[left] duration-300 ease-in-out"
      style={{ left: leftOffset }}
    >
      {/* Cohort section */}
      <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 mb-1">
        Current View
      </p>
      {!activeFilterId ? (
        <p className="text-gray-400 text-xs">No filter selected</p>
      ) : filterLoading ? (
        <div className="space-y-1.5">
          <Skeleton />
          <Skeleton />
        </div>
      ) : filterError ? (
        <p className="text-gray-400 text-xs">Filter unavailable</p>
      ) : filterStats ? (
        <div className="space-y-0.5">
          <p className="text-gray-700 dark:text-gray-300">
            {filterStats.filter_name} · {filterStats.total_patients} patient{filterStats.total_patients !== 1 ? 's' : ''}
          </p>
          <p className="text-gray-700 dark:text-gray-300">
            {MASK_LABELS[activeMaskType] ?? activeMaskType} · {VIEW_LABELS[activeViewType] ?? activeViewType}
          </p>
        </div>
      ) : null}

      {/* Patient section */}
      {selectedPatient && (
        <div className="border-t border-gray-200 dark:border-gray-700 mt-2 pt-2">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 mb-1">
            Selected Patient
          </p>
          {patientLoading ? (
            <div className="space-y-1.5">
              <Skeleton />
              <Skeleton />
              <Skeleton />
            </div>
          ) : patientError ? (
            <p className="text-gray-400 text-xs">Patient data unavailable</p>
          ) : patientOverview ? (
            <div className="space-y-0.5">
              <p className="text-gray-700 dark:text-gray-300">{selectedPatient.name}</p>
              {(patientOverview.sex || patientOverview.height_cm || patientOverview.weight_kg) && (
                <p className="text-gray-700 dark:text-gray-300">
                  {[
                    patientOverview.sex,
                    patientOverview.height_cm ? `${patientOverview.height_cm} cm` : null,
                    patientOverview.weight_kg ? `${patientOverview.weight_kg} kg` : null,
                  ]
                    .filter(Boolean)
                    .join(' · ')}
                </p>
              )}
              {patientOverview.date_of_original_diagnosis && (
                <p className="text-gray-700 dark:text-gray-300">
                  Dx: {patientOverview.date_of_original_diagnosis.slice(0, 10)}
                </p>
              )}
              {patientOverview.date_of_metastatic_diagnosis && (
                <p className="text-gray-700 dark:text-gray-300">
                  Met: {patientOverview.date_of_metastatic_diagnosis.slice(0, 10)}
                </p>
              )}
              <p className="text-gray-700 dark:text-gray-300">
                Tumors {patientOverview.data_summary.tumor_masks} · MRI {patientOverview.data_summary.mri_masks} · Dose {patientOverview.data_summary.dose_masks}
              </p>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}

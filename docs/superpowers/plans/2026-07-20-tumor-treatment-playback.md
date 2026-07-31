# Tumor & Treatment Timeline Playback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add "Play" modal functionality to the Tumor Summary and Treatment Summary sections of the Patient Stats panel, reusing the existing MRI playback infrastructure.

**Architecture:** Generalize `MRIPlaybackModal` in-place to accept a generic `PlaybackItem` interface (`id`, `label`, `sublabel`). `PatientSearch` maps its `tumorList` and `treatmentList` arrays to `PlaybackItem[]` and opens the modal from the two currently-commented-out Play buttons.

**Tech Stack:** React 19, TypeScript, Next.js 15. No new backend endpoints — all NIfTI IDs already route through `/api/viewer/:id/test_db_nifti`.

## Global Constraints

- The ±1 iframe windowing strategy from `MRIPlaybackModal` must be preserved exactly — it exists to prevent WebGL context overflow.
- No new npm dependencies.
- No backend changes.

---

### Task 1: Generalize MRIPlaybackModal into a generic PlaybackModal

**Files:**
- Modify: `frontend/src/components/MRIPlaybackModal.tsx`

**Interfaces:**
- Produces: exported type `PlaybackItem { id: string; label: string; sublabel?: string }`
- Produces: default export `PlaybackModal` with props `{ isOpen: boolean; onClose: () => void; items: PlaybackItem[]; modalTitle: string; patientName: string }`

- [ ] **Step 1: Replace the MRITimelineItem interface with PlaybackItem and update props**

In `frontend/src/components/MRIPlaybackModal.tsx`, replace lines 6–17:

```typescript
export interface PlaybackItem {
  id: string;
  label: string;       // main text shown in scrubber tick and metadata row
  sublabel?: string;   // secondary text (timepoint, volume, dose, etc.)
}

interface PlaybackModalProps {
  isOpen: boolean;
  onClose: () => void;
  items: PlaybackItem[];
  modalTitle: string;
  patientName: string;
}
```

- [ ] **Step 2: Update the function signature**

Replace:
```typescript
export default function MRIPlaybackModal({
  isOpen,
  onClose,
  mriScans,
  patientName,
}: MRIPlaybackModalProps) {
```
With:
```typescript
export default function PlaybackModal({
  isOpen,
  onClose,
  items,
  modalTitle,
  patientName,
}: PlaybackModalProps) {
```

- [ ] **Step 3: Replace all mriScans references with items**

- `const n = mriScans.length;` → `const n = items.length;`
- `if (!isOpen || n === 0) return null;` stays the same
- `const activeScan = mriScans[activeIndex];` → `const activeItem = items[activeIndex];`
- Remove `formatDate` and `formatTickLabel` helper functions — they're MRI-specific
- Remove the `isMultiple` variable reuse is fine — keep it

- [ ] **Step 4: Update the top-bar subtitle**

Replace `<span className="text-gray-400 text-sm flex-shrink-0">MRI Timeline</span>` with:
```typescript
<span className="text-gray-400 text-sm flex-shrink-0">{modalTitle}</span>
```

- [ ] **Step 5: Update the iframe map**

Replace the entire iframe `.map()` block with:
```typescript
{items.map((item, index) => {
  const isActive = index === activeIndex;
  const isAdjacent = Math.abs(index - activeIndex) <= 1;
  if (!isAdjacent) return null;
  return (
    <iframe
      key={item.id}
      src={`/api/viewer/${item.id}/test_db_nifti`}
      title={`${modalTitle} ${index + 1} — ${item.label}`}
      onLoad={() => markLoaded(index)}
      sandbox="allow-scripts allow-same-origin allow-forms"
      style={{
        border: 'none',
        width: '100%',
        height: '100%',
        position: isActive ? 'relative' : 'absolute',
        top: 0,
        left: 0,
        opacity: isActive ? 1 : 0,
        pointerEvents: isActive ? 'auto' : 'none',
        zIndex: isActive ? 1 : 0,
      }}
    />
  );
})}
```

- [ ] **Step 6: Update the metadata row in the bottom bar**

Replace the metadata row content:
```typescript
<div className="flex items-center space-x-3 text-sm text-gray-300">
  <span className="font-medium text-white">{activeItem.label}</span>
  <span className="text-gray-600">·</span>
  <span>Item {activeIndex + 1} of {n}</span>
  {activeItem.sublabel && (
    <>
      <span className="text-gray-600">·</span>
      <span className="text-gray-500">{activeItem.sublabel}</span>
    </>
  )}
</div>
```

- [ ] **Step 7: Update the scrubber tick labels**

Replace the tick labels span inside the scrubber:
```typescript
{items.map((item, index) => (
  <span
    key={item.id}
    className={`absolute text-xs transform -translate-x-1/2 whitespace-nowrap transition-colors ${
      index === activeIndex ? 'text-[#2774AE] font-medium' : 'text-gray-500'
    }`}
    style={{ left: n > 1 ? `${(index / (n - 1)) * 100}%` : '50%' }}
  >
    {item.label}
  </span>
))}
```

- [ ] **Step 8: Verify TypeScript**

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer/frontend && npx tsc --noEmit 2>&1 | head -40
```
Expected: zero errors in `MRIPlaybackModal.tsx`.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/MRIPlaybackModal.tsx
git commit -m "refactor: generalize MRIPlaybackModal into generic PlaybackModal"
```

---

### Task 2: Wire tumor and treatment playback in PatientSearch

**Files:**
- Modify: `frontend/src/components/PatientSearch.tsx`

**Interfaces:**
- Consumes: `PlaybackModal` (default export from `./MRIPlaybackModal`), `PlaybackItem` (named export)
- Consumes: existing state `tumorList: TumorItem[]`, `treatmentList: TreatmentItem[]`, `mriTimeline: MRITimelineItem[]`

- [ ] **Step 1: Update the import**

Change the import at the top of `PatientSearch.tsx`:
```typescript
import MRIPlaybackModal from './MRIPlaybackModal';
```
→
```typescript
import PlaybackModal, { PlaybackItem } from './MRIPlaybackModal';
```

- [ ] **Step 2: Add playback state for tumor and treatment**

After `const [playbackOpen, setPlaybackOpen] = useState(false);`, add:
```typescript
const [tumorPlaybackOpen, setTumorPlaybackOpen] = useState(false);
const [treatmentPlaybackOpen, setTreatmentPlaybackOpen] = useState(false);
```

- [ ] **Step 3: Add the three PlaybackItem conversion arrays**

Add these derived values after `handleCloseBrainViewer` (before the `formatDate` helper or alongside other helpers):
```typescript
const mriPlaybackItems: PlaybackItem[] = mriTimeline.map((mri) => ({
  id: mri.id,
  label: new Date(mri.date).toLocaleDateString('en-US', {
    month: 'numeric', day: 'numeric', year: 'numeric',
  }),
  sublabel: mri.timepoint || undefined,
}));

const tumorPlaybackItems: PlaybackItem[] = tumorList.map((tumor) => ({
  id: tumor.id,
  label: tumor.location,
  sublabel: `${tumor.volume_mm3.toFixed(1)} mm³`,
}));

const treatmentPlaybackItems: PlaybackItem[] = treatmentList.map((treatment) => ({
  id: treatment.id,
  label: treatment.type,
  sublabel: [
    treatment.dose != null ? `${treatment.dose} Gy` : null,
    treatment.date ? formatDate(treatment.date) : null,
  ]
    .filter(Boolean)
    .join(' · ') || undefined,
}));
```

- [ ] **Step 4: Wire the Tumor Summary Play button**

Find the Tumor Summary header button (~line 541). Replace the entire `<button>` element (which has `// onClick={() => handlePlayTumor()` commented out):
```typescript
<button
  onClick={() => setTumorPlaybackOpen(true)}
  disabled={tumorList.length === 0}
  className='p-2 text-green-600 hover:bg-green-600 hover:text-white rounded-md transition-colors disabled:opacity-30 disabled:cursor-not-allowed'
  title={tumorList.length === 0 ? 'No tumor data available' : 'Play Tumor Masks'}
>
  <Play className='w-4 h-4' />
</button>
```

- [ ] **Step 5: Wire the Treatment Summary Play button**

Find the Treatment Summary header button (~line 581). Replace the entire `<button>` element (which has `// onClick={() => handlePlayTreatment()` commented out):
```typescript
<button
  onClick={() => setTreatmentPlaybackOpen(true)}
  disabled={treatmentList.length === 0}
  className='p-2 text-purple-600 hover:bg-purple-600 hover:text-white rounded-md transition-colors disabled:opacity-30 disabled:cursor-not-allowed'
  title={treatmentList.length === 0 ? 'No treatment data available' : 'Play Treatment Masks'}
>
  <Play className='w-4 h-4' />
</button>
```

- [ ] **Step 6: Replace the MRIPlaybackModal render with three PlaybackModal renders**

Find the `<MRIPlaybackModal ... />` at the bottom of the component and replace it with:
```typescript
{/* MRI Playback */}
<PlaybackModal
  isOpen={playbackOpen}
  onClose={() => setPlaybackOpen(false)}
  items={mriPlaybackItems}
  modalTitle="MRI Timeline"
  patientName={selectedPatient ? selectedPatient.display_name : ''}
/>

{/* Tumor Playback */}
<PlaybackModal
  isOpen={tumorPlaybackOpen}
  onClose={() => setTumorPlaybackOpen(false)}
  items={tumorPlaybackItems}
  modalTitle="Tumor Masks"
  patientName={selectedPatient ? selectedPatient.display_name : ''}
/>

{/* Treatment Playback */}
<PlaybackModal
  isOpen={treatmentPlaybackOpen}
  onClose={() => setTreatmentPlaybackOpen(false)}
  items={treatmentPlaybackItems}
  modalTitle="Treatment / Dose Masks"
  patientName={selectedPatient ? selectedPatient.display_name : ''}
/>
```

- [ ] **Step 7: Verify TypeScript**

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer/frontend && npx tsc --noEmit 2>&1 | head -40
```
Expected: zero TypeScript errors.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/PatientSearch.tsx
git commit -m "feat: add tumor and treatment playback modals to Patient Stats panel"
```

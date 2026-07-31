# Brain Visualizer — User Guide

A complete walkthrough of every feature in the Brain Visualizer, a full‑stack
application for exploring synthetic brain‑tumor data. This guide covers the
interface top to bottom: the sidebar, the 3D brain views, and the three side
panels (Filters, Charts, Patient Stats) along with every modal and control they
contain.

---

## Table of Contents

1. [What the App Does](#1-what-the-app-does)
2. [Launching the App](#2-launching-the-app)
3. [The Interface at a Glance](#3-the-interface-at-a-glance)
4. [The Left Sidebar](#4-the-left-sidebar)
   - [Collapse / Expand](#collapse--expand)
   - [Navigation: Filters, Charts, Patient Stats](#navigation-filters-charts-patient-stats)
   - [View Types: Surface vs. Glass](#view-types-surface-vs-glass)
   - [Mask Types: Tumor, MRI, Dose](#mask-types-tumor-mri-dose)
5. [The Main Brain Viewer](#5-the-main-brain-viewer)
   - [Surface View](#surface-view)
   - [Glass Brain View](#glass-brain-view)
6. [The Filters Panel](#6-the-filters-panel)
7. [The Charts Panel](#7-the-charts-panel)
8. [The Patient Stats Panel](#8-the-patient-stats-panel)
   - [Searching for a Patient](#searching-for-a-patient)
   - [The Patient Overview](#the-patient-overview)
   - [MRI Timeline, Tumor & Treatment Summaries](#mri-timeline-tumor--treatment-summaries)
   - [The Brain Viewer Modal](#the-brain-viewer-modal)
   - [The Playback Modal](#the-playback-modal)
9. [Panel Behaviors (Resize, Fullscreen, Switching)](#9-panel-behaviors-resize-fullscreen-switching)
10. [Data Persistence & Sessions](#10-data-persistence--sessions)
11. [Tips & Troubleshooting](#11-tips--troubleshooting)

---

## 1. What the App Does

The Brain Visualizer lets you:

- **Render brains in 3D** two different ways — a detailed cortical **Surface**
  view and a translucent **Glass Brain** volume view.
- **Overlay three kinds of data** on the brain: **Tumor** masks, **MRI** scans,
  and radiation **Dose** masks.
- **Build and save filters** that narrow the patient population by
  demographics, clinical measurements, tumor characteristics, and treatment
  data — then render only the matching cohort.
- **Create charts** from patient/tumor/dose fields, scoped to any filter.
- **Search individual patients** and inspect their demographics, diagnosis
  timeline, MRI history, tumors, and treatments — including per‑item 3D views
  and animated playback.

Everything runs in the browser against a Flask backend, a PostgreSQL database,
and a Redis cache.

---

## 2. Launching the App

The app is a Dockerized stack (frontend, backend, PostgreSQL, Redis). From the
project root:

```bash
docker-compose up
```

Then open **http://localhost:3000** in your browser.

- Frontend (Next.js): port **3000**
- Backend (Flask API): port **5001**
- PostgreSQL: port **5432**
- Redis: internal to the Docker network

> For local development against a separately‑run frontend, you can start the
> Next.js dev server on another port, e.g. `npm run dev -- --port 3001`, and
> reach it at http://localhost:3001. The frontend proxies all `/api/*` calls to
> the backend, so no extra configuration is needed.

The first time the viewer loads, it shows **"Loading viewer…"** while the 3D
components initialize (they render client‑side only).

---

## 3. The Interface at a Glance

The screen has two persistent regions:

- **The Left Sidebar** (blue, fixed to the left edge) — your control center for
  navigation, view type, and mask type.
- **The Main Viewer** — fills the rest of the screen and shows the 3D brain.

On top of these, one **side panel** at a time can slide in from the left
(Filters, Charts, or Patient Stats). When a panel opens, the brain view smoothly
shifts to stay centered in the remaining space.

---

## 4. The Left Sidebar

The sidebar is always visible. It carries the UCLA logo at the top and a version
label at the bottom, with three sections in between: **Navigation**, **View
Types**, and **Mask Types**.

### Collapse / Expand

Click the **chevron button** in the sidebar header to collapse the sidebar to a
narrow icon‑only rail (or expand it back to full width with labels). This gives
the brain view more room. The collapse state animates smoothly and every button
remains usable in the collapsed state via its icon.

### Navigation: Filters, Charts, Patient Stats

Three buttons open the three side panels. They are **mutually exclusive** —
opening one automatically closes any other that was open, and clicking an active
one again closes it.

| Button | Icon | Opens |
| --- | --- | --- |
| **Filters** | sliders | The Filters panel (create/apply cohort filters) |
| **Charts** | bar chart | The Data Visualizations panel |
| **Patient Stats** | people | The Patient Search panel |

The active panel's button is highlighted.

### View Types: Surface vs. Glass

Choose how the brain is rendered. This toggle affects the main viewer only.

- **Surface** — a detailed cortical surface rendering (pycortex). Best for
  seeing anatomy and where data sits on the cortex.
- **Glass** — a translucent "glass brain" with the data volume rendered inside
  it. Best for seeing the 3D distribution of an overlay through the whole brain.

### Mask Types: Tumor, MRI, Dose

Choose **which data layer** is drawn on the brain. Switching mask type reloads
the current view with the new overlay.

- **Tumor** — tumor segmentation masks.
- **MRI** — MRI scan intensity.
- **Dose** — radiation dose masks.

While a mask type is loading, a spinner appears in this section and the mask
buttons are temporarily disabled to prevent overlapping requests. The active
mask type is highlighted.

> The View Type and Mask Type selections combine with the **active filter**
> (from the Filters panel) to determine exactly what the main viewer renders.

---

## 5. The Main Brain Viewer

### Surface View

The Surface view is an embedded interactive cortical renderer. It reloads
automatically whenever you:

- change the **active filter**,
- change the **mask type**, or
- trigger a refresh (e.g. after applying a new filter).

**Interacting with the surface:**

- **Drag** to rotate the brain.
- **Scroll** to zoom.
- Use the renderer's built‑in controls for panning and colormap adjustments.

If no NIfTI file exists yet for the current filter/mask combination, the backend
generates one on demand, so the first load of a new combination may take a
moment.

### Glass Brain View

The Glass Brain view renders a semi‑transparent brain mesh with the data volume
inside it, using a blue→red intensity colormap. It has its own **on‑canvas
control panel** in the bottom‑left corner.

**Camera controls (orbit):**

- **Left‑drag** — rotate.
- **Right‑drag** — pan.
- **Scroll** — zoom.

**Control panel:**

- **Threshold slider** (0.001 – 0.5) — hides voxels below the chosen intensity.
  Raise it to strip away low‑intensity noise and isolate the strongest signal;
  lower it to reveal faint structure. The current value is shown to three
  decimals.
- **Opacity slider** (1 – 100) — scales how opaque the volume appears. Higher
  values make the overlay denser and more solid; lower values make it wispier so
  you can see through it.
- **Intensity legend** — a blue‑to‑red gradient strip labeled **Low → High**,
  matching the colormap baked into the render so you can read voxel intensity by
  color.
- **Reset button** — returns Threshold to `0.010` and Opacity to `20.0`.

The control panel captures pointer events, so dragging the sliders never
accidentally rotates the brain behind it.

> Adjusting the sliders updates the render live without reloading the volume
> data, so it stays smooth even while dragging.

---

## 6. The Filters Panel

Open it from **Filters** in the sidebar. A filter defines a cohort of patients;
the **active** filter drives what the main viewer renders and scopes the data
available to charts.

**Panel layout:**

- A **New Filter** button at the top.
- A list of existing filters, each with a **radio button** (to make it active)
  and **Edit / View / Delete** actions.

### Creating a Filter

1. Click **New Filter**.
2. Give the filter a **name**.
3. Select any combination of criteria across four categories. Within a single
   range field, checking multiple ranges **unions** them (OR); across different
   fields the criteria **intersect** (AND).
4. Click **Create**.

**Available criteria:**

- **Patient Demographics**
  - Origin cancer (cancer type)
  - Sex
  - Age range
  - Height range
  - Weight range
  - Tumor count range
- **Clinical Data**
  - Systolic BP range
  - Diastolic BP range
- **Tumor Characteristics**
  - Tumor location
  - Tumor volume range
- **Treatment Data**
  - Dose range

When you create a filter, the backend also tries to generate the brain
visualization (NIfTI) for it. If the filter saves but the visualization can't be
generated, an **amber warning banner** appears on that filter's row:
*"Filter saved, but brain visualization could not be generated. The filter will
not render on the viewer."* The filter still exists and can be edited; you can
**Dismiss** the banner, and it also clears automatically if you successfully edit
that filter.

### Applying a Filter

Click a filter's **radio button** (or its row) to make it **active**. The main
viewer reloads to show that cohort with the current view and mask type.

### Editing a Filter

Click **Edit** to reopen the criteria form with the filter's current name and
selections. Adjust and click **Update**.

### Viewing Filter Impact

Click **View** to open a details modal showing:

- **Total Patients** matched by the filter.
- A highlighted count for the **currently active mask type** (Tumors, MRI Scans,
  or Dose Masks).
- Counts for the **other** two data types.
- A plain‑language summary of the **applied criteria**.

The highlighted card is color‑coded to the active mask type (green = Tumor,
purple = MRI, orange = Dose).

### Deleting a Filter

Click **Delete** to remove a filter. In narrow panel widths the buttons collapse
to single letters (**E / V / D**) to stay usable.

---

## 7. The Charts Panel

Open it from **Charts** in the sidebar (titled **Data Visualizations**). It shows
your charts and lets you build new ones from real patient/tumor/dose data.

**Default charts:** The panel ships with six example charts (line, bar, scatter,
histogram, box plot, bubble) so it's never empty.

### Creating a Chart

1. Click **New Chart**.
2. **Select Filter** — the cohort whose data the chart will use.
3. **Chart Type** — Line, Bar, Scatter Plot, Histogram, Box Plot, or Bubble.
4. Optionally set a **Chart Title**, **X‑Axis Title**, and **Y‑Axis Title**.
5. Pick an **X Axis Field** and a **Y Axis Field** from the available data
   fields.
6. Click **Create Chart**. The app fetches the field data for the chosen filter,
   builds the chart, and adds it to the panel.

**Available fields:**

- *Patient‑level:* Patient Age, Height, Weight, Systolic BP, Diastolic BP, Tumor
  Count, Sex, Cancer Type
- *Tumor‑level:* Tumor Volume (mm³), Tumor Location
- *Dose‑level:* Max Dose (Gy), Dose Volume (mm³)

> **Keep X and Y in the same category.** Mixing a patient‑level field with a
> mask‑level field (e.g. Patient Age vs. Tumor Volume) produces mismatched array
> lengths, so the app rejects it with an explanatory error. Choose both fields
> from the same group.

While the chart data loads, the Create button shows a spinner and **"Loading
data…"**. If the fetch or creation fails, an inline red error message explains
what happened.

### Managing Charts

- **Delete a chart:** hover over any chart and click the **✕** button that
  appears in its top‑right corner. It's disabled while a delete is in flight to
  avoid duplicate requests.
- **Layout (fullscreen only):** in fullscreen you can toggle between a **grid**
  layout and a **vertical** (stacked) layout using the two layout buttons.

### Persistence

Charts you create are saved per session and survive page reloads and backend
restarts (see [Data Persistence & Sessions](#10-data-persistence--sessions)). The
six default charts are always available and are never written to the database.

---

## 8. The Patient Stats Panel

Open it from **Patient Stats** in the sidebar (titled **Patient Search**). This
is the deepest part of the app — a per‑patient dossier with 3D views and
playback.

### Searching for a Patient

Type in the **search box** to find patients by ID (partial matches work). Results
are debounced (they update ~300 ms after you stop typing). Each result shows the
patient's display name, ID, and total number of data points. Click a result to
open that patient's overview.

### The Patient Overview

The overview header shows the patient's name with a **back arrow** to return to
search. Below, the dossier is organized into sections:

- **Patient ID** — the full identifier.
- **Demographics** — Sex, Height, Weight, and a computed **BMI** with category
  (Underweight / Normal / Overweight / Obese).
- **Medical Information** — Origin Cancer, Tumor Count, and Blood Pressure
  (systolic/diastolic).
- **Diagnosis Timeline** — dates of Original Diagnosis and Metastatic Diagnosis.

### MRI Timeline, Tumor & Treatment Summaries

Three list sections follow, each with individual items and a **Play** button in
its header for animated playback:

- **MRI Timeline** (blue) — each MRI scan with its date and timepoint. Click the
  **eye** icon on a row to open that scan in the Brain Viewer Modal.
- **Tumor Summary** (green) — each tumor with its location and volume (mm³).
  Click the **eye** icon to view that tumor mask in 3D.
- **Treatment Summary** (purple) — each treatment with its type and any of dose
  (Gy), volume (mm³), and date. Click the **eye** icon to view the dose mask.

If a section has no data, it says so, and its Play button is disabled.

### The Brain Viewer Modal

Clicking an **eye** icon on any MRI, tumor, or treatment opens a large modal that
renders that single NIfTI in an interactive viewer.

**Left info panel (dark):**

- **Tumor Summary** — a count of tumors and a list of each tumor's location and
  volume.
- **File Info** — the NIfTI's **Dimensions** and **Voxel size (mm)**, fetched
  from the file header. Shows **Loading…** while fetching and **Not available**
  if the header can't be read.

**Header controls:**

- **Reload** (circular arrow) — remounts the viewer if it needs a fresh load.
- **Fullscreen** — expands the modal to the full window (and back).
- **Close** (✕).

**Viewer controls** (shown as a hint overlay in the bottom‑right):

- **Drag** — rotate.
- **Right‑drag** — pan.
- **Scroll** — zoom.

### The Playback Modal

Clicking a section's **Play** button opens a fullscreen playback view that steps
through every item in that section (MRI scans, tumor masks, or dose masks) one at
a time.

- **Top bar** — patient name, section title, and a **"N of N"** position counter,
  plus a Close (✕) button.
- **Viewer area** — renders the current item; a spinner shows while a scan
  loads. To stay within the browser's WebGL limits, only the current item and its
  immediate neighbors are kept mounted at once.
- **Bottom bar** — the current item's label and any sub‑label (date, dose,
  volume), plus a **scrubber** when there's more than one item.

**Navigation:**

- **Scrubber slider** — jump to any item.
- **Prev / Next arrows** — step one item at a time.
- **Keyboard:** **←** / **→** to move between items, **Esc** to close.

The scrubber shows a tick label under each position, with the current one
highlighted.

---

## 9. Panel Behaviors (Resize, Fullscreen, Switching)

All three side panels (Filters, Charts, Patient Stats) share the same window
behaviors:

- **Only one panel is open at a time.** Opening a second closes the first.
- **Resize** — drag the panel's right edge (the resize handle) to make it wider
  or narrower, roughly 15%–60% of the screen. The brain view re‑centers as you
  drag.
- **Fullscreen** — click the fullscreen (expand) button in the panel header to
  make the panel take the whole window; click again to restore. The Charts panel
  exposes its grid/vertical layout toggle only in fullscreen.
- **Close** — click the ✕ in the panel header.

As panels open, close, resize, or go fullscreen, the main brain viewer smoothly
translates so it stays centered in whatever space remains.

---

## 10. Data Persistence & Sessions

- **Per‑session scoping:** Your filters and charts are tied to your browser
  session (a unique ID assigned automatically). Different browser sessions see
  their own independent filters and charts, not each other's.
- **Charts persist durably:** Charts you create are written to both a fast cache
  (Redis) and the database (PostgreSQL), so they survive page reloads *and*
  backend restarts. The six built‑in default charts are always present and are
  never saved to the database.
- **Filters** are likewise stored per session and drive both the viewer and the
  chart data queries.

---

## 11. Tips & Troubleshooting

- **The brain looks empty or a view won't load.** The first time you select a new
  filter + mask combination, the backend may need to generate the NIfTI on
  demand — give it a moment, then it's cached for next time.
- **A filter row shows an amber warning.** The filter saved but its
  visualization couldn't be generated; the cohort/statistics still work, and the
  banner clears if you successfully edit the filter.
- **Chart creation is rejected with a "can't mix fields" error.** Your X and Y
  fields come from different categories (patient vs. tumor vs. dose). Pick both
  from the same group.
- **Glass Brain overlay is too noisy or too faint.** Raise the **Threshold** to
  remove low‑intensity voxels, or adjust **Opacity**; use **Reset** to return to
  defaults.
- **Playback feels heavy with many scans.** That's expected — only the current
  scan and its neighbors stay loaded to respect browser WebGL limits; stepping
  through re‑loads them as needed.
- **Nothing happens when I click a panel button.** Panels are mutually
  exclusive; the button may be toggling a panel closed. Click again to reopen, or
  check that another panel didn't just take its place.

---

*Brain Visualizer v1.0*

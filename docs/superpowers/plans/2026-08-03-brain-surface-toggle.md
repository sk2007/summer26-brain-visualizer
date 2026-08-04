# Brain Surface Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an Eye/EyeOff toggle button to BrainViewerModal that hides/shows the pycortex brain surface mesh via postMessage, leaving only the mapped data volume visible.

**Architecture:** The toggle button in `BrainViewerModal` sends a `postMessage` to the pycortex iframe; `custom_viewer.html` listens and sets Three.js surface mesh opacity. A `load` event listener re-applies the current `brainVisible` state after every iframe reload.

**Tech Stack:** React 19 / TypeScript, lucide-react (Eye/EyeOff icons), pycortex WebGL viewer (Three.js internals), browser postMessage API.

## Global Constraints

- Button classes match existing toolbar buttons exactly: `p-2 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-md transition-colors dark:text-gray-300`
- Button position: between the Reload button and the Fullscreen button in the header
- `brainVisible` initialized to `true`
- postMessage payload: `{ type: 'set-brain-opacity', value: 0 }` (hide) or `{ type: 'set-brain-opacity', value: 1 }` (show)
- When `brainVisible === true`: show `EyeOff` icon, title `"Hide brain surface"`
- When `brainVisible === false`: show `Eye` icon, title `"Show brain surface"`
- `custom_viewer.html` listener guards on `event.data.type === 'set-brain-opacity'` before acting
- Renderer re-render call is guarded: `if (viewer && viewer.renderer)`
- TypeScript compilation (`cd frontend && npx tsc --noEmit`) is the verification step — no frontend test suite exists

---

### Task 1: Add postMessage listener to custom_viewer.html

Add a `window.addEventListener('message', ...)` handler to the pycortex viewer template that receives `set-brain-opacity` messages and sets surface mesh opacity.

**Files:**
- Modify: `frontend/src/app/custom_templates/custom_viewer.html`

**Interfaces:**
- Produces for Task 2: `window.postMessage({ type: 'set-brain-opacity', value: 0 | 1 }, '*')` — the contract the BrainViewerModal button must use

- [ ] **Step 1: Add the postMessage listener inside the existing `{% block extrahtml %}` script**

The file currently has a `<script>` tag inside `{% block extrahtml %}` (lines 25–81). Add the listener at the end of that script block, before the closing `</script>` tag:

```js
    // Brain surface opacity toggle via postMessage
    window.addEventListener('message', function(event) {
      if (!event.data || event.data.type !== 'set-brain-opacity') return;
      var opacity = Number(event.data.value);
      for (var name in subjects) {
        var surf = subjects[name];
        ['left', 'right'].forEach(function(hemi) {
          if (surf[hemi] && surf[hemi].mesh) {
            surf[hemi].mesh.material.opacity = opacity;
            surf[hemi].mesh.material.transparent = opacity < 1;
            surf[hemi].mesh.material.needsUpdate = true;
          }
        });
      }
      if (viewer && viewer.renderer) {
        viewer.renderer.render(viewer.scene, viewer.camera);
      }
    });
```

The full updated `{% block extrahtml %}` should look like:

```html
{% block extrahtml %}
  <script>
    document.addEventListener("DOMContentLoaded", function() {
      document.getElementById('figure_ui').style.display = 'none';
    });
    
    // Function to handle brain clicks and send data to API
    function setupBrainClickHandler(viewer) {
      var canvas = document.getElementById('brain');
      
      canvas.addEventListener('click', function(event) {
        // Get mouse position relative to canvas
        var rect = canvas.getBoundingClientRect();
        var x = event.clientX - rect.left;
        var y = event.clientY - rect.top;
        
        // Use the facepicker to get vertex information
        if (viewer.picker && viewer.renderer) {
          try {
            // Get vertex information from the current scene
            viewer.picker.draw(viewer.renderer, viewer.camera);
            var pick = viewer.picker._pick(x, y, viewer.renderer.context);
            
            if (pick) {
              console.log('Brain clicked:', pick);
              
              // Prepare the data to send to the API
              var clickData = {
                hemi: pick.hemi,
                vertex: pick.ptidx,
                coords: [pick.pos.x, pick.pos.y, pick.pos.z]
              };
              
              // Send the data to our API endpoint
              fetch(apiBaseUrl + '/api/brain-clicks', {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                  'Accept': 'application/json'
                },
                mode: 'cors',
                body: JSON.stringify(clickData)
              })
              .then(response => response.json())
              .then(data => {
                console.log('Brain click stored:', data);
              })
              .catch(error => {
                console.error('Error storing brain click:', error);
              });
            }
          } catch (e) {
            console.error('Error picking vertex:', e);
          }
        }
      });
    }

    // Brain surface opacity toggle via postMessage
    window.addEventListener('message', function(event) {
      if (!event.data || event.data.type !== 'set-brain-opacity') return;
      var opacity = Number(event.data.value);
      for (var name in subjects) {
        var surf = subjects[name];
        ['left', 'right'].forEach(function(hemi) {
          if (surf[hemi] && surf[hemi].mesh) {
            surf[hemi].mesh.material.opacity = opacity;
            surf[hemi].mesh.material.transparent = opacity < 1;
            surf[hemi].mesh.material.needsUpdate = true;
          }
        });
      }
      if (viewer && viewer.renderer) {
        viewer.renderer.render(viewer.scene, viewer.camera);
      }
    });
  </script>
{% end %}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/custom_templates/custom_viewer.html
git commit -m "feat: add postMessage listener for brain surface opacity toggle"
```

---

### Task 2: Add toggle button to BrainViewerModal

Add `brainVisible` state, an iframe ref, a `load` event handler that re-applies opacity on reload, and the Eye/EyeOff toggle button to the modal header.

**Files:**
- Modify: `frontend/src/components/BrainViewerModal.tsx`

**Interfaces:**
- Consumes from Task 1: `postMessage({ type: 'set-brain-opacity', value: 0 | 1 }, '*')` sent to `iframeRef.current.contentWindow`

- [ ] **Step 1: Add Eye and EyeOff to the lucide-react import**

Line 2 currently reads:
```tsx
import { X, Maximize2, Minimize2, Brain, RotateCcw } from 'lucide-react';
```

Change it to:
```tsx
import { X, Maximize2, Minimize2, Brain, RotateCcw, Eye, EyeOff } from 'lucide-react';
```

- [ ] **Step 2: Add `brainVisible` state and `iframeRef`**

After line 27 (`const [reloadKey, setReloadKey] = React.useState(0);`), add:

```tsx
  const [brainVisible, setBrainVisible] = React.useState(true);
  const iframeRef = React.useRef<HTMLIFrameElement>(null);
```

- [ ] **Step 3: Add a helper to send the opacity message**

After the two new state declarations, add:

```tsx
  const sendOpacity = React.useCallback((visible: boolean) => {
    iframeRef.current?.contentWindow?.postMessage(
      { type: 'set-brain-opacity', value: visible ? 1 : 0 },
      '*'
    );
  }, []);
```

- [ ] **Step 4: Add `useEffect` to re-apply opacity on iframe load**

After `sendOpacity`, add:

```tsx
  React.useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;
    const onLoad = () => sendOpacity(brainVisible);
    iframe.addEventListener('load', onLoad);
    return () => iframe.removeEventListener('load', onLoad);
  }, [brainVisible, sendOpacity]);
```

- [ ] **Step 5: Add `ref` to the iframe element**

The iframe element (around line 153) currently is:
```tsx
<iframe
  key={reloadKey}
  src={viewerUrl}
  className="w-full h-full border-0"
  title={`Brain Viewer - ${title}`}
  sandbox="allow-scripts allow-same-origin allow-forms"
/>
```

Add `ref={iframeRef}`:
```tsx
<iframe
  ref={iframeRef}
  key={reloadKey}
  src={viewerUrl}
  className="w-full h-full border-0"
  title={`Brain Viewer - ${title}`}
  sandbox="allow-scripts allow-same-origin allow-forms"
/>
```

- [ ] **Step 6: Add the toggle button to the header**

The header toolbar currently has three buttons in this order: Reload, Fullscreen, Close (around lines 68–93). Insert the new button between Reload and Fullscreen:

```tsx
            <button
              onClick={() => {
                setBrainVisible((v) => {
                  sendOpacity(!v);
                  return !v;
                });
              }}
              className="p-2 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-md transition-colors dark:text-gray-300"
              title={brainVisible ? 'Hide brain surface' : 'Show brain surface'}
            >
              {brainVisible ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
            </button>
```

The full updated button group should read: Reload → **Toggle** → Fullscreen → Close.

- [ ] **Step 7: Reset `brainVisible` when modal closes and reopens**

The modal already gates on `if (!isOpen) return null`. Add a `useEffect` that resets `brainVisible` to `true` when `isOpen` becomes `true` (so reopening the modal starts with the brain visible):

```tsx
  React.useEffect(() => {
    if (isOpen) setBrainVisible(true);
  }, [isOpen]);
```

- [ ] **Step 8: Verify TypeScript compilation**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/BrainViewerModal.tsx
git commit -m "feat: add brain surface toggle button to BrainViewerModal"
```

# Brain Surface Toggle Design

## Overview

A toggle button in `BrainViewerModal` that hides the pycortex brain surface mesh, leaving only the mapped data volume (tumor/MRI/dose colors) visible in the 3D WebGL viewer.

---

## Architecture & Data Flow

### Button

A new toggle button added to the `BrainViewerModal` header toolbar, between the existing Reload and Fullscreen buttons. Uses the `Eye` / `EyeOff` icon from `lucide-react`. State: `brainVisible: boolean`, initialized to `true`, local to `BrainViewerModal`.

On click:
1. Flip `brainVisible`.
2. Call `iframeRef.current.contentWindow.postMessage({ type: 'set-brain-opacity', value: brainVisible ? 0 : 1 }, '*')`.

### iframe ref

`BrainViewerModal` already renders an `<iframe>`. Add `ref={iframeRef}` (a `useRef<HTMLIFrameElement>(null)`) to it so the button handler can reach `contentWindow`.

### Timing

The postMessage must be sent after the iframe's viewer is initialized. Send it inside a `load` event listener on the iframe (`iframeRef.current.addEventListener('load', ...)`) so it fires after every page load, including reloads. On each `load` event, re-apply the current `brainVisible` state so the toggle survives a Reload.

### `custom_viewer.html` changes

Add a `window.addEventListener('message', ...)` handler in the `{% block extrahtml %}` script block. On receiving `{ type: 'set-brain-opacity', value }`:

```js
window.addEventListener('message', function(event) {
  if (!event.data || event.data.type !== 'set-brain-opacity') return;
  var opacity = event.data.value;
  for (var name in subjects) {
    var surf = subjects[name];
    // pycortex Surface exposes left/right Three.js mesh objects
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

### Reset on Reload

The existing Reload button increments `reloadKey`, which remounts the iframe. On the new `load` event, the handler re-applies `brainVisible` so the toggle state is preserved across reloads.

---

## Visual Spec

Button classes (matching existing toolbar buttons):
```
p-2 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-md transition-colors dark:text-gray-300
```

- When `brainVisible === true`: show `EyeOff` icon, title `"Hide brain surface"`
- When `brainVisible === false`: show `Eye` icon, title `"Show brain surface"`

Position: between the Reload button and the Fullscreen button in the header.

---

## Edge Cases

- **Viewer not yet loaded**: postMessage before load is a no-op — the `load` event handler re-applies state after the viewer initializes, so this is safe.
- **Reload while hidden**: `load` event fires, re-applies `value: 0` — brain stays hidden as expected.
- **Multiple subjects**: the loop over `subjects` handles all subjects in the scene.
- **No renderer**: the final `renderer.render(...)` call is guarded with an existence check — safe if the viewer is mid-load.

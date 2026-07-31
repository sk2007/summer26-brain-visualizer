# Glass Brain Colormap Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an overlay UI panel on the Glass Brain view with sliders for opacity and threshold, and a color legend strip, so users can tune what they're seeing without hardcoded shader values.

**Architecture:** `GlassBrainViewer` gains two state variables (`threshold: number`, `opacityMultiplier: number`) and renders an absolute-positioned control panel in the bottom-left corner. Both values are passed as props to `VolumeRenderer`, which uses a `useEffect` to update Three.js shader uniforms reactively. The color legend is a CSS gradient strip that mirrors the HSL colormap already baked into the shader.

**Tech Stack:** React 19, TypeScript, Three.js via `@react-three/fiber`. No new dependencies.

## Global Constraints

- No backend changes.
- The colormap itself (HSL sweep from blue to red, hue 0.7 → 0.0) stays unchanged — only threshold and opacity multiplier are exposed.
- Controls must not interfere with the canvas `OrbitControls` (pointer events on the overlay panel stop propagation).

---

### Task 1: Accept threshold and opacityMultiplier props in VolumeRenderer

**Files:**
- Modify: `frontend/src/components/VolumeRenderer.tsx`

**Interfaces:**
- Produces: `VolumeRendererProps` extended with `threshold?: number` (default `0.01`) and `opacityMultiplier?: number` (default `20.0`)

- [ ] **Step 1: Update the VolumeRendererProps interface**

In `frontend/src/components/VolumeRenderer.tsx`, find:
```typescript
interface VolumeRendererProps {
    brainSize: THREE.Vector3;
    refreshTrigger?: number;
}
```

Replace with:
```typescript
interface VolumeRendererProps {
    brainSize: THREE.Vector3;
    refreshTrigger?: number;
    threshold?: number;
    opacityMultiplier?: number;
}
```

- [ ] **Step 2: Destructure the new props in the component signature**

Find:
```typescript
export default function VolumeRenderer({ brainSize, refreshTrigger = 0 }: VolumeRendererProps) {
```
Replace with:
```typescript
export default function VolumeRenderer({
    brainSize,
    refreshTrigger = 0,
    threshold = 0.01,
    opacityMultiplier = 20.0,
}: VolumeRendererProps) {
```

- [ ] **Step 3: Keep a ref to the shader material to update uniforms**

Add a ref for the shader material after the existing state declarations:
```typescript
const materialRef = useRef<THREE.ShaderMaterial>(null!);
```

- [ ] **Step 4: Update uniforms reactively when threshold or opacityMultiplier change**

Add a `useEffect` after the existing `useEffect` that fetches volume data:
```typescript
useEffect(() => {
    if (materialRef.current) {
        materialRef.current.uniforms.u_threshold.value = threshold;
        materialRef.current.uniforms.u_opacity_multiplier.value = opacityMultiplier;
    }
}, [threshold, opacityMultiplier]);
```

- [ ] **Step 5: Add u_opacity_multiplier uniform to the initial uniforms object**

In the `useMemo` that creates `uniforms`, add the new uniform:
```typescript
const uni = {
    u_volume_dims: { value: new THREE.Vector3(...dims) },
    u_volume_tex: { value: tex },
    u_cm_texture: { value: cmap },
    u_threshold: { value: threshold },
    u_opacity_multiplier: { value: opacityMultiplier },
    u_steps: { value: 100.0 },
};
```

- [ ] **Step 6: Update the fragment shader to use u_opacity_multiplier**

In `volumeFragmentShader`, find:
```glsl
uniform float u_threshold;
uniform float u_steps;
```
Replace with:
```glsl
uniform float u_threshold;
uniform float u_opacity_multiplier;
uniform float u_steps;
```

Then find the opacity calculation line:
```glsl
float opacity = color_sample.a * 20.0 / u_steps;
```
Replace with:
```glsl
float opacity = color_sample.a * u_opacity_multiplier / u_steps;
```

- [ ] **Step 7: Attach the ref to the shaderMaterial**

Find the `<shaderMaterial .../>` JSX. Add `ref={materialRef}`:
```typescript
<shaderMaterial
    ref={materialRef}
    uniforms={uniforms}
    vertexShader={volumeVertexShader}
    fragmentShader={volumeFragmentShader}
    side={THREE.BackSide}
    transparent
/>
```

- [ ] **Step 8: Verify TypeScript**

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer/frontend && npx tsc --noEmit 2>&1 | head -40
```
Expected: zero errors.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/VolumeRenderer.tsx
git commit -m "feat: make VolumeRenderer threshold and opacity controllable via props"
```

---

### Task 2: Add overlay controls and color legend to GlassBrainViewer

**Files:**
- Modify: `frontend/src/components/GlassBrainViewer.tsx`

**Interfaces:**
- Consumes: `VolumeRenderer` accepting `threshold?: number` and `opacityMultiplier?: number` props from Task 1

- [ ] **Step 1: Add state for controls**

After `const [error, setError] = useState<string | null>(null);`, add:
```typescript
const [threshold, setThreshold] = useState(0.01);
const [opacityMultiplier, setOpacityMultiplier] = useState(20.0);
```

- [ ] **Step 2: Pass the new props to VolumeRenderer**

Find the `<VolumeRenderer .../>` element:
```typescript
<VolumeRenderer brainSize={brainBounds.size} refreshTrigger={refreshTrigger} />
```
Replace with:
```typescript
<VolumeRenderer
    brainSize={brainBounds.size}
    refreshTrigger={refreshTrigger}
    threshold={threshold}
    opacityMultiplier={opacityMultiplier}
/>
```

- [ ] **Step 3: Add the overlay control panel**

The `return` block renders a `<Canvas>`. Wrap the whole return in a `<div className="relative w-full h-full">` and add the overlay panel after `</Canvas>`:

```typescript
return (
  <div className="relative w-full h-full">
    <Canvas
      camera={{ position: [0, 0, 250], fov: 50, up: [0, 1, 0] }}
      style={{ background: '#e0e0e0', width: '100%', height: '100%' }}
    >
      {/* ... existing Canvas children unchanged ... */}
    </Canvas>

    {/* Overlay controls — pointer events stop at this panel so OrbitControls underneath still work */}
    <div
      className="absolute bottom-4 left-4 bg-black/60 text-white rounded-lg p-3 space-y-3 select-none"
      style={{ minWidth: 200 }}
      onPointerDown={(e) => e.stopPropagation()}
    >
      {/* Threshold slider */}
      <div className="space-y-1">
        <div className="flex justify-between text-xs">
          <span>Threshold</span>
          <span>{threshold.toFixed(3)}</span>
        </div>
        <input
          type="range"
          min={0.001}
          max={0.5}
          step={0.001}
          value={threshold}
          onChange={(e) => setThreshold(parseFloat(e.target.value))}
          className="w-full h-1.5 rounded-full appearance-none cursor-pointer accent-[#2774AE]"
        />
      </div>

      {/* Opacity multiplier slider */}
      <div className="space-y-1">
        <div className="flex justify-between text-xs">
          <span>Opacity</span>
          <span>{opacityMultiplier.toFixed(1)}</span>
        </div>
        <input
          type="range"
          min={1}
          max={100}
          step={1}
          value={opacityMultiplier}
          onChange={(e) => setOpacityMultiplier(parseFloat(e.target.value))}
          className="w-full h-1.5 rounded-full appearance-none cursor-pointer accent-[#2774AE]"
        />
      </div>

      {/* Color legend strip — matches the HSL colormap: blue (low) → red (high) */}
      <div className="space-y-1">
        <div className="text-xs">Intensity</div>
        <div
          className="w-full h-3 rounded-sm"
          style={{
            background: 'linear-gradient(to right, hsl(252,100%,50%), hsl(180,100%,50%), hsl(72,100%,50%), hsl(0,100%,50%))',
          }}
        />
        <div className="flex justify-between text-[10px] text-white/60">
          <span>Low</span>
          <span>High</span>
        </div>
      </div>

      {/* Reset button */}
      <button
        onClick={() => { setThreshold(0.01); setOpacityMultiplier(20.0); }}
        className="w-full text-xs py-1 rounded bg-white/10 hover:bg-white/20 transition-colors"
      >
        Reset
      </button>
    </div>
  </div>
);
```

- [ ] **Step 4: Verify TypeScript**

```bash
cd /Users/sampath/Coding/summer26-brain-visualizer/frontend && npx tsc --noEmit 2>&1 | head -40
```
Expected: zero errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/GlassBrainViewer.tsx
git commit -m "feat: add threshold/opacity overlay controls and color legend to Glass Brain view"
```

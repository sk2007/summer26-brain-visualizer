'use client';

import React, { useRef, useState, useEffect, useMemo } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, useProgress, Html } from '@react-three/drei';
import * as THREE from 'three';
import VolumeRenderer from './VolumeRenderer';

function Loader() {
  const { progress } = useProgress();
  return <Html center>{progress ? `${progress.toFixed(0)} % loaded` : 'Loading...'}</Html>;
}

interface MeshData {
    vertices: number[][];
    faces: number[][];
}

interface GlassBrainViewerProps {
    refreshTrigger?: number;
}

interface BrainMeshProps {
    geometry: THREE.BufferGeometry;
    position: THREE.Vector3;
}

const BrainMesh = React.forwardRef<THREE.Mesh, BrainMeshProps>(({ geometry, position }, ref) => {
    return (
        <mesh 
            ref={ref}
            geometry={geometry}
            position={position}
        >
            <meshStandardMaterial
                color="#f0f0f0"
                transparent={true}
                opacity={0.2}
                depthWrite={false}
                side={THREE.DoubleSide}
            />
        </mesh>
    );
});
BrainMesh.displayName = 'BrainMesh';

export default function GlassBrainViewer({ refreshTrigger = 0 }: GlassBrainViewerProps) {
    const brainMeshRef = useRef<THREE.Mesh>(null!);
    const [meshData, setMeshData] = useState<MeshData | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [threshold, setThreshold] = useState(0.01);
    const [opacityMultiplier, setOpacityMultiplier] = useState(20.0);

    // Fetch brain mesh data
    useEffect(() => {
        fetch('/api/glass_brain/brain_surface')
            .then(res => res.json())
            .then(data => {
                if (data.error) throw new Error(data.error);
                setMeshData(data);
            }).catch(e => {
                console.error("Fetch error:", e);
                setError(e.message);
            });
    }, [refreshTrigger]);

    const brainGeometry = useMemo(() => {
        if (!meshData) return null;
        const geom = new THREE.BufferGeometry();
        geom.setAttribute('position', new THREE.Float32BufferAttribute(meshData.vertices.flat(), 3));
        geom.setIndex(meshData.faces.flat());
        geom.computeVertexNormals();
        return geom;
    }, [meshData]);

    // After the geometry is created, calculate its intrinsic (un-rotated) bounding box
    const brainBounds = useMemo(() => {
        if (!brainGeometry) return null;
        brainGeometry.computeBoundingBox();
        const box = brainGeometry.boundingBox!;
        const center = new THREE.Vector3();
        const size = new THREE.Vector3();
        box.getCenter(center);
        box.getSize(size);
        return { center, size };
    }, [brainGeometry]);

    if (error) {
        return <div style={{ color: 'red', padding: '20px' }}>Error: {error}</div>;
    }

  return (
    <div className="relative w-full h-full">
      <Canvas
        camera={{ position: [0, 0, 250], fov: 50, up: [0, 1, 0] }}
        style={{ background: '#e0e0e0', width: '100%', height: '100%' }}
      >
        <ambientLight intensity={0.5} />
        <pointLight position={[100, 100, 100]} intensity={1} />
        <React.Suspense fallback={<Loader />}>
            {brainGeometry && brainBounds && (
                <group rotation={[-Math.PI / 2, 0, 0]}>
                    <BrainMesh geometry={brainGeometry} position={brainBounds.center.clone().negate()} />
                    <VolumeRenderer
                      brainSize={brainBounds.size}
                      refreshTrigger={refreshTrigger}
                      threshold={threshold}
                      opacityMultiplier={opacityMultiplier}
                    />
                </group>
            )}
            <OrbitControls
               enablePan={true}
               enableZoom={true}
               enableRotate={true}
             />
        </React.Suspense>
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
              background: 'linear-gradient(to right, hsl(252,100%,50%), hsl(168,100%,50%), hsl(84,100%,50%), hsl(0,100%,50%))',
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
}

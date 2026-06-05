import React, { useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { MeshDistortMaterial, Sphere, OrbitControls, Environment } from '@react-three/drei';
import * as THREE from 'three';

interface MoodGlobeProps {
  emotion: string;
}

const EMOTION_PROPS: Record<string, { color: string; distort: number; speed: number }> = {
  neutral: { color: '#6b7280', distort: 0.2, speed: 1 },
  calm: { color: '#14b8a6', distort: 0.1, speed: 0.5 },
  happy: { color: '#f59e0b', distort: 0.3, speed: 2 },
  sad: { color: '#3b82f6', distort: 0.15, speed: 0.8 },
  angry: { color: '#ef4444', distort: 0.6, speed: 4 },
  fearful: { color: '#8b5cf6', distort: 0.4, speed: 3 },
  disgust: { color: '#10b981', distort: 0.5, speed: 1.5 },
  surprised: { color: '#ec4899', distort: 0.3, speed: 3.5 },
};

function AnimatedSphere({ emotion }: { emotion: string }) {
  const meshRef = useRef<THREE.Mesh>(null);
  const props = EMOTION_PROPS[emotion] || EMOTION_PROPS.neutral;

  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.rotation.x = state.clock.getElapsedTime() * 0.2;
      meshRef.current.rotation.y = state.clock.getElapsedTime() * 0.3;
    }
  });

  return (
    <Sphere ref={meshRef} args={[1, 64, 64]} scale={1.5}>
      <MeshDistortMaterial
        color={props.color}
        envMapIntensity={0.8}
        clearcoat={0.8}
        clearcoatRoughness={0.2}
        metalness={0.1}
        roughness={0.4}
        distort={props.distort}
        speed={props.speed}
      />
    </Sphere>
  );
}

export default function MoodGlobe({ emotion }: MoodGlobeProps) {
  return (
    <div className="w-full h-full min-h-[200px] relative rounded-2xl overflow-hidden bg-black/20 flex items-center justify-center">
      <Canvas camera={{ position: [0, 0, 4], fov: 45 }}>
        <ambientLight intensity={0.5} />
        <directionalLight position={[10, 10, 5]} intensity={1} />
        <directionalLight position={[-10, -10, -5]} intensity={0.5} color="#4338ca" />
        <AnimatedSphere emotion={emotion} />
        <OrbitControls enableZoom={false} enablePan={false} autoRotate autoRotateSpeed={1} />
        <Environment preset="city" />
      </Canvas>
      <div className="absolute bottom-4 left-0 w-full text-center pointer-events-none">
        <span className="px-3 py-1 bg-black/40 backdrop-blur-md rounded-full text-xs font-medium text-white capitalize border border-white/10">
          Dominant Mood: {emotion}
        </span>
      </div>
    </div>
  );
}

import React from 'react';
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import { theme } from '../theme';

interface HookSceneProps {
  hook: string;
  frame: number;
  fps: number;
}

export const HookScene: React.FC<HookSceneProps> = ({ hook, frame, fps }) => {
  const { width, height } = useVideoConfig();

  // Animation: spring in with scale + fade
  const animation = spring({
    frame,
    fps,
    config: {
      damping: 200,
      stiffness: 100,
      mass: 0.5,
    },
  });

  const scale = interpolate(animation, [0, 1], [0.8, 1]);
  const opacity = interpolate(animation, [0, 1], [0, 1]);

  return (
    <AbsoluteFill
      style={{
        backgroundColor: theme.colors.background,
        justifyContent: 'center',
        alignItems: 'center',
        padding: theme.spacing.large,
      }}
    >
      <div
        style={{
          transform: `scale(${scale})`,
          opacity,
          maxWidth: theme.layout.contentWidth,
          textAlign: 'center',
        }}
      >
        <h1
          style={{
            fontFamily: theme.fonts.primary,
            fontSize: 72,
            fontWeight: theme.fonts.weight.extrabold,
            color: theme.colors.primary,
            lineHeight: 1.2,
            margin: 0,
            textShadow: `0 4px 8px ${theme.colors.shadow}`,
          }}
        >
          {hook}
        </h1>
      </div>
    </AbsoluteFill>
  );
};

import React from 'react';
import {
  AbsoluteFill,
  interpolate,
  spring,
  useVideoConfig,
} from 'remotion';
import { theme } from '../theme';

interface ValueSceneProps {
  bulletPoints: string[];
  frame: number;
  fps: number;
}

export const ValueScene: React.FC<ValueSceneProps> = ({
  bulletPoints,
  frame,
  fps,
}) => {
  const { width, height } = useVideoConfig();

  // Stagger bullet point animations
  const getBulletAnimation = (index: number) => {
    const delay = index * 15; // 0.5s delay between bullets
    const adjustedFrame = Math.max(0, frame - delay);

    return spring({
      frame: adjustedFrame,
      fps,
      config: {
        damping: 200,
        stiffness: 100,
      },
    });
  };

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
          maxWidth: theme.layout.contentWidth,
          width: '100%',
        }}
      >
        {bulletPoints.map((bullet, index) => {
          const animation = getBulletAnimation(index);
          const translateY = interpolate(animation, [0, 1], [30, 0]);
          const opacity = interpolate(animation, [0, 1], [0, 1]);

          return (
            <div
              key={index}
              style={{
                transform: `translateY(${translateY}px)`,
                opacity,
                marginBottom: theme.spacing.medium,
                display: 'flex',
                alignItems: 'flex-start',
              }}
            >
              {/* Bullet icon/number */}
              <div
                style={{
                  width: 60,
                  height: 60,
                  borderRadius: '50%',
                  backgroundColor: theme.colors.accent,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginRight: theme.spacing.small,
                  flexShrink: 0,
                }}
              >
                <span
                  style={{
                    fontFamily: theme.fonts.primary,
                    fontSize: 32,
                    fontWeight: theme.fonts.weight.bold,
                    color: theme.colors.background,
                  }}
                >
                  {index + 1}
                </span>
              </div>

              {/* Bullet text */}
              <p
                style={{
                  fontFamily: theme.fonts.primary,
                  fontSize: 42,
                  fontWeight: theme.fonts.weight.semibold,
                  color: theme.colors.primary,
                  lineHeight: 1.4,
                  margin: 0,
                  textShadow: `0 2px 4px ${theme.colors.shadow}`,
                }}
              >
                {bullet}
              </p>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

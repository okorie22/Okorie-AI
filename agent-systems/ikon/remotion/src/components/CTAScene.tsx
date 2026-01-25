import React from 'react';
import {
  AbsoluteFill,
  interpolate,
  spring,
  useVideoConfig,
} from 'remotion';
import { theme } from '../theme';

interface CTASceneProps {
  cta: string;
  disclaimer: string;
  frame: number;
  fps: number;
}

export const CTAScene: React.FC<CTASceneProps> = ({
  cta,
  disclaimer,
  frame,
  fps,
}) => {
  const { width, height } = useVideoConfig();

  // CTA animation
  const ctaAnimation = spring({
    frame,
    fps,
    config: {
      damping: 200,
      stiffness: 100,
    },
  });

  const ctaScale = interpolate(ctaAnimation, [0, 1], [0.9, 1]);
  const ctaOpacity = interpolate(ctaAnimation, [0, 1], [0, 1]);

  // Disclaimer fades in slightly later
  const disclaimerDelay = 30; // 1 second delay
  const disclaimerAnimation = spring({
    frame: Math.max(0, frame - disclaimerDelay),
    fps,
    config: {
      damping: 200,
      stiffness: 80,
    },
  });

  const disclaimerOpacity = interpolate(disclaimerAnimation, [0, 1], [0, 1]);

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
          textAlign: 'center',
        }}
      >
        {/* CTA Box */}
        <div
          style={{
            transform: `scale(${ctaScale})`,
            opacity: ctaOpacity,
            backgroundColor: theme.colors.accent,
            padding: `${theme.spacing.medium}px ${theme.spacing.large}px`,
            borderRadius: 20,
            marginBottom: theme.spacing.large,
          }}
        >
          <h2
            style={{
              fontFamily: theme.fonts.primary,
              fontSize: 56,
              fontWeight: theme.fonts.weight.bold,
              color: theme.colors.background,
              lineHeight: 1.3,
              margin: 0,
            }}
          >
            {cta}
          </h2>
        </div>

        {/* Arrow pointing down */}
        <div
          style={{
            opacity: ctaOpacity,
            marginBottom: theme.spacing.medium,
          }}
        >
          <svg
            width="60"
            height="60"
            viewBox="0 0 24 24"
            fill="none"
            stroke={theme.colors.accent}
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="12" y1="5" x2="12" y2="19" />
            <polyline points="19 12 12 19 5 12" />
          </svg>
        </div>

        {/* Disclaimer */}
        <p
          style={{
            opacity: disclaimerOpacity,
            fontFamily: theme.fonts.primary,
            fontSize: 24,
            fontWeight: theme.fonts.weight.normal,
            color: theme.colors.disclaimer,
            lineHeight: 1.4,
            margin: 0,
            maxWidth: 800,
          }}
        >
          {disclaimer}
        </p>
      </div>
    </AbsoluteFill>
  );
};

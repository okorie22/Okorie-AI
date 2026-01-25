import React from 'react';
import {
  AbsoluteFill,
  Audio,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import { HookScene } from '../components/HookScene';
import { ValueScene } from '../components/ValueScene';
import { CTAScene } from '../components/CTAScene';

export interface IULShortV1Props {
  hook: string;
  bulletPoints: string[];
  cta: string;
  disclaimer: string;
  audioPath: string;
}

export const IULShortV1: React.FC<IULShortV1Props> = ({
  hook,
  bulletPoints,
  cta,
  disclaimer,
  audioPath,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Scene timing (30 seconds = 900 frames at 30fps)
  // Hook: 0-2s (0-60 frames)
  // Value: 2-24s (60-720 frames)
  // CTA: 24-30s (720-900 frames)
  
  const hookEnd = 60;
  const valueEnd = 720;
  const ctaEnd = 900;

  const showHook = frame < hookEnd;
  const showValue = frame >= hookEnd && frame < valueEnd;
  const showCTA = frame >= valueEnd && frame < ctaEnd;

  return (
    <AbsoluteFill>
      {/* Audio track */}
      {audioPath && <Audio src={audioPath} />}

      {/* Hook Scene (0-2s) */}
      {showHook && <HookScene hook={hook} frame={frame} fps={fps} />}

      {/* Value Scene (2-24s) */}
      {showValue && (
        <ValueScene
          bulletPoints={bulletPoints}
          frame={frame - hookEnd}
          fps={fps}
        />
      )}

      {/* CTA Scene (24-30s) */}
      {showCTA && (
        <CTAScene
          cta={cta}
          disclaimer={disclaimer}
          frame={frame - valueEnd}
          fps={fps}
        />
      )}
    </AbsoluteFill>
  );
};

import { Composition } from 'remotion';
import { IULShortV1 } from './compositions/IULShortV1';

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="IULShortV1"
        component={IULShortV1}
        durationInFrames={900}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={{
          hook: "Most people don't understand how IUL cash value actually works...",
          bulletPoints: [
            "Cash value grows based on index performance",
            "Participation rates and caps limit gains",
            "Not a replacement for qualified plans"
          ],
          cta: "Download our free IUL checklist",
          disclaimer: "Educational only. Not financial or insurance advice. Consult a licensed professional.",
          audioPath: ""
        }}
      />
    </>
  );
};

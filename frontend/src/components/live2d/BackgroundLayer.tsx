'use client';

type Props = {
  imageUrl: string;
};

export function BackgroundLayer({ imageUrl }: Props) {
  return (
    <div
      className="background-layer"
      style={{ backgroundImage: `url(${imageUrl})`, backgroundSize: 'cover' }}
    />
  );
}

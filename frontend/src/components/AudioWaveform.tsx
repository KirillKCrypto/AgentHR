import { useEffect, useRef } from 'react'

/** Простая звуковая дорожка для индикации записи. */
export function AudioWaveform({
  stream,
  active,
}: {
  stream: MediaStream | null
  active: boolean
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  useEffect(() => {
    if (!active || !stream || !canvasRef.current) {
      return
    }
    const canvas = canvasRef.current
    const context = canvas.getContext('2d')
    if (!context) {
      return
    }
    const audioContext = new AudioContext()
    const source = audioContext.createMediaStreamSource(stream)
    const analyser = audioContext.createAnalyser()
    analyser.fftSize = 256
    source.connect(analyser)
    const data = new Uint8Array(analyser.frequencyBinCount)
    let frame = 0

    const draw = () => {
      analyser.getByteFrequencyData(data)
      context.clearRect(0, 0, canvas.width, canvas.height)
      const bars = 32
      const step = Math.floor(data.length / bars)
      const width = canvas.width / bars
      for (let index = 0; index < bars; index += 1) {
        const value = data[index * step] / 255
        const height = Math.max(2, value * canvas.height)
        context.fillStyle = 'currentColor'
        context.fillRect(
          index * width + 1,
          (canvas.height - height) / 2,
          Math.max(1, width - 2),
          height,
        )
      }
      frame = requestAnimationFrame(draw)
    }
    draw()

    return () => {
      cancelAnimationFrame(frame)
      source.disconnect()
      void audioContext.close()
    }
  }, [active, stream])

  return (
    <canvas
      ref={canvasRef}
      width={320}
      height={48}
      className="h-12 w-full text-primary"
      aria-label="Уровень записи"
    />
  )
}

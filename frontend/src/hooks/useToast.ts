import { toast } from 'sonner'

// Singleton AudioContext for efficient resource management
let audioContext: AudioContext | null = null

// Get or create AudioContext
const getAudioContext = (): AudioContext | null => {
  try {
    if (!audioContext) {
      const AudioContextClass = window.AudioContext || (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
      if (AudioContextClass) {
        audioContext = new AudioContextClass()
      }
    }
    return audioContext
  } catch (error) {
    console.error('Failed to create AudioContext:', error)
    return null
  }
}

// Play notification sound
const playNotificationSound = () => {
  try {
    const ctx = getAudioContext()
    if (!ctx) return

    const oscillator = ctx.createOscillator()
    const gainNode = ctx.createGain()

    oscillator.connect(gainNode)
    gainNode.connect(ctx.destination)

    oscillator.frequency.value = 800
    oscillator.type = 'sine'

    gainNode.gain.setValueAtTime(0.3, ctx.currentTime)
    gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3)

    oscillator.start(ctx.currentTime)
    oscillator.stop(ctx.currentTime + 0.3)
  } catch (error) {
    console.error('Failed to play notification sound:', error)
  }
}

const formatTime = () => {
  const now = new Date()
  return now.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

type ToastType = 'success' | 'error' | 'warning' | 'info'

// Helper to show toast with consistent configuration (DRY)
const showToast = (type: ToastType, message: string, description?: string) => {
  playNotificationSound()
  const timestamp = formatTime()
  const enhancedDescription = description
    ? `${description}\n\nTime: ${timestamp}`
    : `Time: ${timestamp}`

  const options = {
    description: enhancedDescription,
    duration: Infinity,
    dismissible: true,
    closeButton: true
  }

  toast[type](message, options)
}

export const useToast = () => {
  return {
    success: (message: string, description?: string) => showToast('success', message, description),
    error: (message: string, description?: string) => showToast('error', message, description),
    warning: (message: string, description?: string) => showToast('warning', message, description),
    info: (message: string, description?: string) => showToast('info', message, description),
  }
}

import { create } from 'zustand'
import { auth as authApi, setAccessToken } from '@/lib/api'

interface User { id: string; email: string }

interface AuthState {
  user: User | null
  isLoading: boolean
  signIn: (identifier: string, password: string) => Promise<void>
  signOut: () => Promise<void>
  refresh: () => Promise<boolean>
  setUser: (user: User | null) => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoading: false,

  signIn: async (identifier, password) => {
    set({ isLoading: true })
    try {
      const data = await authApi.signIn(identifier, password)
      setAccessToken(data.access_token)
      set({ user: data.user, isLoading: false })
    } catch (e) {
      set({ isLoading: false })
      throw e
    }
  },

  signOut: async () => {
    await authApi.signOut().catch(() => {})
    setAccessToken(null)
    set({ user: null })
  },

  refresh: async () => {
    try {
      const data = await authApi.refresh()
      setAccessToken(data.access_token)
      return true
    } catch {
      setAccessToken(null)
      set({ user: null })
      return false
    }
  },

  setUser: (user) => set({ user }),
}))


// ── UI Store ──────────────────────────────────────────────────────────────────
interface UIState {
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
}

export const useUIStore = create<UIState>()((set) => ({
  sidebarOpen: true,
  setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
}));

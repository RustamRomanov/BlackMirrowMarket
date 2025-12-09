import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { initData } from '@twa-dev/sdk'
import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface User {
  id: number
  telegram_id: number
  username?: string
  first_name?: string
  age?: number
  gender?: string
  country?: string
  referral_code?: string
  terms_accepted?: boolean
  is_banned?: boolean
  ban_until?: string
  ban_reason?: string
}

interface AuthContextType {
  user: User | null
  loading: boolean
  updateUser: (userData: Partial<User>) => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [autoFilled, setAutoFilled] = useState(false)

  useEffect(() => {
    async function initUser() {
      try {
        // Production: инициализация из Telegram Mini App
        if (initData?.user) {
          const telegramUser = initData.user
          const telegramId = telegramUser.id

          // 1) Пытаемся получить пользователя
          try {
            const getResp = await axios.get(`${API_URL}/api/users/${telegramId}`)
            setUser(getResp.data)
            return
          } catch (getErr: any) {
            if (getErr?.response?.status !== 404) {
              throw getErr
            }
          }

          // 2) Если 404 — создаем
          const createResp = await axios.post(`${API_URL}/api/users/`, {
            telegram_id: telegramId,
            username: telegramUser.username,
            first_name: telegramUser.firstName,
            last_name: telegramUser.lastName
          })
          setUser(createResp.data)
          return
        }

        // Dev fallback: тестовый пользователь
        const testTelegramId = 123456789
        console.log('Development mode: creating test user')
        try {
          const urlParams = new URLSearchParams(window.location.search)
          const referrerCode = urlParams.get('start') || urlParams.get('ref')

          const response = await axios.post(`${API_URL}/api/users/`, {
            telegram_id: testTelegramId,
            username: 'test_user',
            first_name: 'Test',
            last_name: 'User',
            referrer_code: referrerCode || undefined,
            age: 25,
            gender: 'male',
            country: 'Россия',
            terms_accepted: true
          })
          setUser(response.data)
        } catch (error: any) {
          if (error.response?.status === 422 || error.response?.status === 400 || error.response?.status === 500) {
            try {
              const response = await axios.get(`${API_URL}/api/users/${testTelegramId}`)
              setUser(response.data)
            } catch (getError) {
              console.error('Error getting user:', getError)
              try {
                const createResponse = await axios.post(`${API_URL}/api/users/`, {
                  telegram_id: testTelegramId,
                  username: 'test_user',
                  first_name: 'Test',
                  age: 25,
                  gender: 'male',
                  country: 'Россия',
                  terms_accepted: true
                })
                setUser(createResponse.data)
              } catch (createError) {
                console.error('Error creating user:', createError)
              }
            }
          } else {
            console.error('Error initializing user:', error)
          }
        }
      } catch (error) {
        console.error('Error initializing user:', error)
      } finally {
        setLoading(false)
      }
    }

    initUser()
  }, [])

  // Автозаполнение обязательных полей в дев-режиме, чтобы не просить заново
  useEffect(() => {
    async function ensureProfileDefaults() {
      if (loading || autoFilled) return
      if (!user) return

      const needsDefaults =
        !user.age ||
        !user.gender ||
        !user.country ||
        user.terms_accepted === false ||
        user.terms_accepted === undefined

      if (!needsDefaults) return

      try {
        const defaults = {
          age: user.age || 25,
          gender: user.gender || 'male',
          country: user.country || 'Россия',
          terms_accepted: true
        }
        const updated = await updateUser(defaults)
        setUser(updated || { ...user, ...defaults })
        setAutoFilled(true)
      } catch (err) {
        console.error('Error auto-filling profile defaults:', err)
      }
    }

    ensureProfileDefaults()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, loading])

  const updateUser = async (userData: Partial<User> | User) => {
    // Если пользователя нет, пытаемся создать/получить его перед обновлением
    if (!user && initData?.user) {
      try {
        const telegramUser = initData.user
        const resp = await axios.post(`${API_URL}/api/users/`, {
          telegram_id: telegramUser.id,
          username: telegramUser.username,
          first_name: telegramUser.firstName,
          last_name: telegramUser.lastName
        })
        setUser(resp.data)
      } catch (err: any) {
        // если уже есть — пробуем получить
        if (err?.response?.status === 400 || err?.response?.status === 422) {
          try {
            const getResp = await axios.get(`${API_URL}/api/users/${initData.user.id}`)
            setUser(getResp.data)
          } catch (getErr) {
            console.error('Error getting user during update:', getErr)
          }
        } else {
          console.error('Error creating user during update:', err)
        }
      }
    }

    if (!user && !('telegram_id' in userData)) return

    try {
      const telegramId = user?.telegram_id || (userData as User).telegram_id
      if ('telegram_id' in userData && !user) {
        // Если передан полный объект пользователя, просто устанавливаем его
        setUser(userData as User)
        return
      }
      
      const response = await axios.put(
        `${API_URL}/api/users/${telegramId}`,
        userData
      )
      // Обновляем состояние пользователя
      setUser(response.data)
      return response.data
    } catch (error) {
      console.error('Error updating user:', error)
      throw error
    }
  }

  return (
    <AuthContext.Provider value={{ user, loading, updateUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}


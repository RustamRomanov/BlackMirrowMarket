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
        // Режим разработки: если нет initData, создаем тестового пользователя
        if (initData?.user) {
          const telegramUser = initData.user
          
          // Создаем или получаем пользователя
          const response = await axios.post(`${API_URL}/api/users/`, {
            telegram_id: telegramUser.id,
            username: telegramUser.username,
            first_name: telegramUser.firstName,
            last_name: telegramUser.lastName
          })
          
          setUser(response.data)
        } else {
          // Режим разработки: создаем тестового пользователя для локальной разработки
          console.log('Development mode: creating test user')
          const testTelegramId = 123456789 // Тестовый ID
          try {
            // Проверяем, есть ли referrer_code в URL
            const urlParams = new URLSearchParams(window.location.search)
            const referrerCode = urlParams.get('start') || urlParams.get('ref')
            
            const response = await axios.post(`${API_URL}/api/users/`, {
              telegram_id: testTelegramId,
              username: 'test_user',
              first_name: 'Test',
              last_name: 'User',
              referrer_code: referrerCode || undefined,
              // Автоматически заполняем обязательные поля для тестового пользователя
              age: 25,
              gender: 'male',
              country: 'Россия',
              terms_accepted: true
            })
            setUser(response.data)
          } catch (error: any) {
            // Если пользователь уже существует или ошибка, пытаемся получить его
            if (error.response?.status === 422 || error.response?.status === 400 || error.response?.status === 500) {
              try {
                const response = await axios.get(`${API_URL}/api/users/${testTelegramId}`)
                setUser(response.data)
              } catch (getError) {
                console.error('Error getting user:', getError)
                // Создаем пользователя с минимальными данными
                try {
                  const createResponse = await axios.post(`${API_URL}/api/users/`, {
                    telegram_id: testTelegramId,
                    username: 'test_user',
                    first_name: 'Test',
                    // Автоматически заполняем обязательные поля
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


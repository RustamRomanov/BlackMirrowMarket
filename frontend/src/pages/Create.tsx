import { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import axios from 'axios'
import { Bell, MessageSquare, Eye, Pause, Play } from 'lucide-react'
import CreateTaskModal, { TaskFormData } from '../components/CreateTaskModal'
import './Create.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface MyTask {
  id: number
  title: string
  description?: string
  task_type: 'subscription' | 'comment' | 'view'
  price_per_slot_ton: string
  total_slots: number
  completed_slots: number
  status: 'active' | 'paused' | 'completed' | 'cancelled'
  created_at: string
}

export default function Create() {
  const { user } = useAuth()
  const { showSuccess, showError } = useToast()
  const [showModal, setShowModal] = useState(false)
  const [myTasks, setMyTasks] = useState<MyTask[]>([])
  const [loading, setLoading] = useState(true)
  const [fiatCurrency, setFiatCurrency] = useState<string>('RUB')
  const [fiatRate, setFiatRate] = useState<number>(250)

  useEffect(() => {
    if (user) {
      loadFiatInfo()
      loadMyTasks()
    }
  }, [user])

  useEffect(() => {
    const handleFocus = () => {
      if (user) {
        loadFiatInfo()
        loadMyTasks()
      }
    }
    window.addEventListener('focus', handleFocus)
    return () => window.removeEventListener('focus', handleFocus)
  }, [user])

  async function loadFiatInfo() {
    if (!user) return
    try {
      // Загружаем валюту из localStorage, если есть
      const storedCurrency = typeof window !== 'undefined' 
        ? localStorage.getItem('fiatCurrency')
        : null
      if (storedCurrency && ['RUB', 'USD', 'EUR', 'TON'].includes(storedCurrency)) {
        setFiatCurrency(storedCurrency)
      }
      
      // Загружаем курс из localStorage, если есть
      const storedRate = typeof window !== 'undefined'
        ? parseFloat(localStorage.getItem('fiatRatePerTon') || '0')
        : 0
      if (storedRate > 0) {
        setFiatRate(storedRate)
      }
      
      // Если нет в localStorage, загружаем с бэкенда
      const response = await axios.get(`${API_URL}/api/balance/${user.telegram_id}`)
      if (!storedCurrency && response.data?.fiat_currency) {
        setFiatCurrency(response.data.fiat_currency)
        if (typeof window !== 'undefined') {
          localStorage.setItem('fiatCurrency', response.data.fiat_currency)
        }
      }
      if (storedRate === 0) {
        if (response.data?.last_fiat_rate) {
          const rate = parseFloat(response.data.last_fiat_rate) || 250
          setFiatRate(rate)
          if (typeof window !== 'undefined') {
            localStorage.setItem('fiatRatePerTon', rate.toString())
          }
        } else if (response.data?.fiat_currency) {
          const rates: Record<string, number> = { RUB: 250, USD: 3.5, EUR: 3.2, TON: 1 }
          const rate = rates[response.data.fiat_currency] ?? 250
          setFiatRate(rate)
          if (typeof window !== 'undefined') {
            localStorage.setItem('fiatRatePerTon', rate.toString())
          }
        }
      }
    } catch (error) {
      console.error('Error loading fiat info:', error)
    }
  }

  async function loadMyTasks() {
    if (!user) {
      console.log('No user, skipping loadMyTasks')
      return
    }
    setLoading(true)
    try {
      const response = await axios.get(`${API_URL}/api/tasks/my`, {
        params: { telegram_id: user.telegram_id }
      })
      const tasks = (response.data || []).map((task: any) => ({
        ...task,
        status: task.status?.toLowerCase() || task.status,
        task_type: task.task_type?.toLowerCase() || task.task_type
      }))
      setMyTasks(tasks)
    } catch (error: any) {
      console.error('Error loading my tasks:', error)
      setMyTasks([])
    } finally {
      setLoading(false)
    }
  }

  async function handleCreateTask(formData: TaskFormData) {
    if (!user) {
      showError('Необходимо войти в систему')
      return
    }

    const priceInNanoTon = parseFloat(formData.price_per_slot_ton) * 10**9

    try {
      const response = await axios.post(
        `${API_URL}/api/tasks/`,
        {
          ...formData,
          price_per_slot_ton: priceInNanoTon.toString(),
          total_slots: parseInt(formData.total_slots),
          telegram_post_id: formData.telegram_post_id ? parseInt(formData.telegram_post_id) : null,
          target_country: formData.target_country || null,
          target_gender: formData.target_gender === 'both' ? null : formData.target_gender,
          target_age_min: formData.target_age_min ? parseInt(formData.target_age_min) : null,
          target_age_max: formData.target_age_max ? parseInt(formData.target_age_max) : null
        },
        {
          params: { telegram_id: user.telegram_id }
        }
      )

      console.log('Task created successfully:', response.data)
      showSuccess('Задание создано успешно!')
      setShowModal(false)

      setTimeout(async () => {
        await loadMyTasks()
      }, 500)
    } catch (error: any) {
      console.error('Error creating task:', error)
      showError(error.response?.data?.detail || 'Ошибка при создании задания')
    }
  }

  async function handlePauseTask(taskId: number) {
    if (!user) return
    try {
      await axios.patch(`${API_URL}/api/tasks/${taskId}/pause`, null, {
        params: { telegram_id: user.telegram_id }
      })
      showSuccess('Задание остановлено')
      loadMyTasks()
    } catch (error: any) {
      showError(error.response?.data?.detail || 'Ошибка при остановке задания')
    }
  }

  async function handleResumeTask(taskId: number) {
    if (!user) return
    try {
      await axios.patch(`${API_URL}/api/tasks/${taskId}/resume`, null, {
        params: { telegram_id: user.telegram_id }
      })
      showSuccess('Задание возобновлено')
      loadMyTasks()
    } catch (error: any) {
      showError(error.response?.data?.detail || 'Ошибка при возобновлении задания')
    }
  }

  async function handleCancelTask(taskId: number) {
    if (!user) return
    if (!confirm('Вы уверены? Остаток средств будет возвращен на баланс.')) return
    try {
      await axios.patch(`${API_URL}/api/tasks/${taskId}/cancel`, null, {
        params: { telegram_id: user.telegram_id }
      })
      showSuccess('Задание остановлено, остаток возвращен на баланс')
      loadMyTasks()
    } catch (error: any) {
      showError(error.response?.data?.detail || 'Ошибка при остановке задания')
    }
  }

  const taskTypeConfig = {
    subscription: { icon: Bell, color: '#4CAF50', label: 'Подписка' },
    comment: { icon: MessageSquare, color: '#2196F3', label: 'Комментарий' },
    view: { icon: Eye, color: '#FF9800', label: 'Просмотр' }
  }

  return (
    <div className="create-page">
      <button
        className="create-task-button"
        onClick={() => setShowModal(true)}
      >
        Создать задание
      </button>

      {!loading && (
        <>
          {myTasks.length > 0 && (
            <div className="example-tasks-section">
              <h2>Мои задания</h2>
              <div className="example-tasks-list">
                {myTasks.map((task) => {
                  const taskType = task.task_type?.toLowerCase() || task.task_type
                  const taskStatus = task.status?.toLowerCase() || task.status
                  const config = taskTypeConfig[taskType as keyof typeof taskTypeConfig]
                  if (!config) return null
                  const Icon = config.icon
                  const priceTon = parseFloat(String(task.price_per_slot_ton)) / 10**9
                  const priceFiat = fiatCurrency === 'TON' 
                    ? priceTon 
                    : priceTon * fiatRate
                  const priceDisplay = fiatCurrency === 'TON'
                    ? `${priceTon.toFixed(4)} TON`
                    : `${priceFiat.toFixed(2)} ${fiatCurrency === 'USD' ? '$' : fiatCurrency === 'EUR' ? '€' : '₽'}`
                  const budgetDisplay = fiatCurrency === 'TON'
                    ? `${(priceTon * task.total_slots).toFixed(4)} TON`
                    : `${(priceFiat * task.total_slots).toFixed(2)} ${fiatCurrency === 'USD' ? '$' : fiatCurrency === 'EUR' ? '€' : '₽'}`
                  return (
                    <div key={task.id} className="example-task-card">
                      <div className="example-task-header">
                        <Icon size={16} color={config.color} />
                        <span style={{ color: config.color, fontWeight: 600 }}>{config.label}</span>
                        <span className={`example-status status-${taskStatus}`}>
                          {taskStatus === 'active' ? 'Активно' :
                           taskStatus === 'paused' ? 'Остановлено' :
                           taskStatus === 'completed' ? 'Завершено' : 'Отменено'}
                        </span>
                      </div>
                      <h4>{task.title}</h4>
                      {task.description && <p>{task.description}</p>}
                      <div className="example-task-stats">
                        <span>Цена за слот: {priceDisplay}</span>
                        <span>Общий бюджет: {budgetDisplay}</span>
                        <span>Выполнено: {task.completed_slots || 0} / {task.total_slots}</span>
                      </div>
                      <div className="example-task-actions">
                        {taskStatus === 'active' && (
                          <button 
                            className="example-pause-btn"
                            onClick={() => handlePauseTask(task.id)}
                          >
                            <Pause size={14} />
                            Пауза
                          </button>
                        )}
                        {taskStatus === 'paused' && (
                          <button 
                            className="example-pause-btn"
                            onClick={() => handleResumeTask(task.id)}
                          >
                            <Play size={14} />
                            Возобновить
                          </button>
                        )}
                        {(taskStatus === 'active' || taskStatus === 'paused') && (
                          <button 
                            className="example-stop-btn"
                            onClick={() => handleCancelTask(task.id)}
                          >
                            Остановить
                          </button>
                        )}
                      </div>
                    </div>
                  )
                }).filter(Boolean)}
              </div>
            </div>
          )}
          {myTasks.length === 0 && (
            <div style={{ padding: '20px', textAlign: 'center', color: '#666' }}>
              <p>У вас пока нет созданных заданий.</p>
              <p>Создайте первое задание, нажав кнопку "Создать задание" выше.</p>
            </div>
          )}
        </>
      )}

      {loading && (
        <div className="tasks-loading">Загрузка заданий...</div>
      )}

      {showModal && (
        <CreateTaskModal
          onClose={() => setShowModal(false)}
          onSubmit={handleCreateTask}
        />
      )}
    </div>
  )
}

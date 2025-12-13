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
      loadFiat()
      loadMyTasks()
    }
  }, [user])

  // Обновляем список при фокусе на странице (если пользователь вернулся на вкладку)
  useEffect(() => {
    const handleFocus = () => {
      if (user) {
        loadMyTasks()
      }
    }
    window.addEventListener('focus', handleFocus)
    return () => window.removeEventListener('focus', handleFocus)
  }, [user])

  async function loadFiat() {
    if (!user) return
    try {
      const balanceResponse = await axios.get(`${API_URL}/api/balance/${user.telegram_id}`)
      if (balanceResponse.data) {
        const selectedCurrency = balanceResponse.data.fiat_currency || 'RUB'
        setFiatCurrency(selectedCurrency)
        
        const tonActive = parseFloat(balanceResponse.data.ton_active_balance) / 10**9
        const fiatActive = parseFloat(balanceResponse.data.fiat_balance)
        
        if (tonActive > 0 && fiatActive > 0) {
          setFiatRate(fiatActive / tonActive)
        } else {
          const defaultRates: Record<string, number> = { 'RUB': 250, 'USD': 2.5, 'EUR': 2.3, 'TON': 1 }
          setFiatRate(defaultRates[selectedCurrency] || 250)
        }
      }
    } catch (error) {
      console.error('Error loading fiat:', error)
    }
  }

  async function loadMyTasks() {
    if (!user) {
      console.log('No user, skipping loadMyTasks')
      return
    }
    
    setLoading(true)
    try {
      console.log('Loading tasks for user:', user.telegram_id)
      const response = await axios.get(`${API_URL}/api/tasks/my`, {
        params: { telegram_id: user.telegram_id }
      })
      console.log('Loaded my tasks response:', response)
      console.log('Loaded my tasks data:', response.data)
      console.log('Tasks count:', response.data?.length || 0)
      
      const tasks = (response.data || []).map((task: any) => ({
        ...task,
        status: task.status?.toLowerCase() || task.status, // Приводим статус к нижнему регистру
        task_type: task.task_type?.toLowerCase() || task.task_type // Приводим тип к нижнему регистру
      }))
      console.log('Processed tasks:', tasks)
      setMyTasks(tasks)
    } catch (error: any) {
      console.error('Error loading my tasks:', error)
      console.error('Error response:', error.response)
      console.error('Error details:', error.response?.data)
      setMyTasks([])
    } finally {
      setLoading(false)
    }
  }

  // Функция для парсинга ссылки на пост Telegram
  function parseTelegramPostId(postLink: string | undefined): number | null {
    if (!postLink) return null
    
    const trimmedLink = postLink.trim()
    
    // Парсим публичные каналы: https://t.me/channel/123
    const publicChannelRegex = /^https?:\/\/(?:www\.)?t\.me\/[^\/]+\/(\d+)/i
    let match = trimmedLink.match(publicChannelRegex)
    
    if (match && match[1]) {
      const postId = parseInt(match[1])
      if (!isNaN(postId) && postId > 0) {
        return postId
      }
    }
    
    // Парсим приватные каналы/группы: https://t.me/c/3503023298/3
    const privateChannelRegex = /^https?:\/\/(?:www\.)?t\.me\/c\/\d+\/(\d+)/i
    match = trimmedLink.match(privateChannelRegex)
    
    if (match && match[1]) {
      const postId = parseInt(match[1])
      if (!isNaN(postId) && postId > 0) {
        return postId
      }
    }
    
    return null
  }

  async function handleCreateTask(formData: TaskFormData) {
    console.log('[CREATE TASK] handleCreateTask called with:', formData)
    
    if (!user) {
      console.error('[CREATE TASK] No user found')
      showError('Необходимо войти в систему')
      return
    }

    // formData.price_per_slot_ton уже содержит цену в TON (после конвертации из фиатной валюты в CreateTaskModal)
    // Бэкенд ожидает цену в TON и сам конвертирует в нано-TON
    const priceInTon = parseFloat(formData.price_per_slot_ton) || 0
    
    console.log('[CREATE TASK] Form data processed:', {
      price_per_slot_ton: formData.price_per_slot_ton,
      priceInTon: priceInTon,
      total_slots: formData.total_slots,
      task_type: formData.task_type,
      telegram_id: user.telegram_id
    })
    
    // Парсим ссылку на пост, если она есть
    const parsedPostId = formData.telegram_post_id ? parseTelegramPostId(formData.telegram_post_id) : null
    
    // Проверяем, что ссылка на пост валидна (только для comment и view)
    if ((formData.task_type === 'comment' || formData.task_type === 'view') && formData.telegram_post_id && !parsedPostId) {
      showError('Ссылка на пост должна быть из Telegram (https://t.me/channel/123)')
      return
    }
    
    // Убеждаемся, что title не пустой (обязательное поле в схеме)
    const taskTitle = formData.title.trim() || 'Задание'
    
    const requestData = {
      ...formData,
      title: taskTitle, // Обязательное поле
      price_per_slot_ton: priceInTon.toString(), // Отправляем в TON, бэкенд сам конвертирует в нано-TON
      total_slots: parseInt(formData.total_slots),
      telegram_post_id: parsedPostId,
      target_country: formData.target_country || null,
      target_gender: formData.target_gender === 'both' ? null : formData.target_gender,
      target_age_min: formData.target_age_min ? parseInt(formData.target_age_min) : null,
      target_age_max: formData.target_age_max ? parseInt(formData.target_age_max) : null
    }
    
    // Дополнительная проверка перед отправкой
    if (!requestData.title || requestData.title.trim() === '') {
      console.error('[CREATE TASK] Title is empty!')
      showError('Название задания обязательно')
      return
    }
    
    if (!requestData.price_per_slot_ton || parseFloat(requestData.price_per_slot_ton) <= 0) {
      console.error('[CREATE TASK] Invalid price:', requestData.price_per_slot_ton)
      showError('Цена должна быть больше 0')
      return
    }
    
    if (!requestData.total_slots || requestData.total_slots < 1) {
      console.error('[CREATE TASK] Invalid slots:', requestData.total_slots)
      showError('Количество слотов должно быть не менее 1')
      return
    }
    
    console.log('[CREATE TASK] Sending request to:', `${API_URL}/api/tasks/`)
    console.log('[CREATE TASK] Request data:', requestData)
    console.log('[CREATE TASK] Request params:', { telegram_id: user.telegram_id })
    
    try {
      const response = await axios.post(
        `${API_URL}/api/tasks/`,
        requestData,
        {
          params: { telegram_id: user.telegram_id }
        }
      )
      
      console.log('Task created successfully:', response.data)
      showSuccess('Задание создано успешно!')
      setShowModal(false)
      
      // Небольшая задержка перед обновлением, чтобы сервер успел сохранить
      setTimeout(async () => {
        await loadMyTasks()
      }, 500)
    } catch (error: any) {
      console.error('[CREATE TASK] Error creating task:', error)
      console.error('[CREATE TASK] Error response:', error.response)
      console.error('[CREATE TASK] Error data:', error.response?.data)
      console.error('[CREATE TASK] Error message:', error.message)
      console.error('[CREATE TASK] Error stack:', error.stack)
      
      // Проверяем тип ошибки
      if (error.code === 'ERR_NETWORK' || error.message?.includes('Network Error')) {
        console.error('[CREATE TASK] Network error - check API_URL:', API_URL)
        showError('Ошибка сети. Проверьте подключение к интернету.')
      } else if (error.response) {
        // Ошибка от сервера
        const errorMessage = error.response?.data?.detail || error.response?.data?.message || 'Ошибка при создании задания'
        console.error('[CREATE TASK] Server error:', errorMessage)
        showError(errorMessage)
      } else {
        // Другая ошибка
        console.error('[CREATE TASK] Unknown error:', error)
        showError(error.message || 'Ошибка при создании задания')
      }
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
    
    if (!confirm('Вы уверены? Остаток средств будет возвращен на баланс.')) {
      return
    }
    
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


      {/* Созданные задания пользователя (показываем после примеров) */}
      {!loading && (
        <>
          {myTasks.length > 0 && (
            <div className="example-tasks-section">
              <h2>Мои задания</h2>
              <div className="example-tasks-list">
                {myTasks.map((task) => {
                  console.log('Rendering task:', task)
                  const taskType = task.task_type?.toLowerCase() || task.task_type
                  const taskStatus = task.status?.toLowerCase() || task.status
                  const config = taskTypeConfig[taskType as keyof typeof taskTypeConfig]
                  
                  if (!config) {
                    console.error('Unknown task type:', taskType)
                    return null
                  }
                  
                  const Icon = config.icon
                  const priceTon = parseFloat(String(task.price_per_slot_ton)) / 10**9
                  const priceFiat = priceTon * fiatRate
                  const currencySymbol = fiatCurrency === 'USD' ? '$' : fiatCurrency === 'EUR' ? '€' : fiatCurrency === 'TON' ? 'TON' : '₽'
                  
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
                        <span>Цена за слот: {priceFiat.toFixed(2)} {currencySymbol}</span>
                        <span>Общий бюджет: {(priceFiat * task.total_slots).toFixed(2)} {currencySymbol}</span>
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


import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import axios from 'axios'
import { Bell, MessageSquare, Eye, AlertCircle, X } from 'lucide-react'
import TaskCard from '../components/TaskCard'
import { TaskCardSkeleton } from '../components/Skeleton'
import './Earn.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function getChannelLink(channelId: string | undefined): string | null {
  if (!channelId) return null
  
  if (channelId.startsWith('http://') || channelId.startsWith('https://')) {
    return channelId
  }
  
  const cleanId = channelId.replace(/^@/, '')
  return `https://t.me/${cleanId}`
}

function getPostLink(channelId: string | undefined, postId: string | number | undefined): string | null {
  if (channelId && (channelId.startsWith('http://') || channelId.startsWith('https://'))) {
    return channelId
  }
  
  if (channelId && postId) {
    const cleanChannelId = channelId.replace(/^@/, '')
    return `https://t.me/${cleanChannelId}/${postId}`
  }
  
  if (channelId) {
    return getChannelLink(channelId)
  }
  
  return null
}

function openTelegramLink(url: string) {
  if (!url) return
  
  const tg = (window as any).Telegram?.WebApp
  if (tg) {
    if (url.startsWith('https://t.me/') || url.startsWith('http://t.me/')) {
      tg.openTelegramLink(url)
    } else {
      tg.openLink(url)
    }
  } else {
    const newWindow = window.open(url, '_blank')
    if (!newWindow) {
      window.location.href = url
    }
  }
}

interface Task {
  id: number
  title: string
  description?: string
  task_type: 'subscription' | 'comment' | 'view'
  price_per_slot_ton: string
  price_per_slot_fiat: string
  fiat_currency: string
  total_slots: number
  completed_slots: number
  remaining_slots: number
  telegram_channel_id?: string
  comment_instruction?: string
  telegram_post_id?: string | number
}

interface TaskDetail extends Task {
  is_test?: boolean
}

export default function Earn() {
  const { user } = useAuth()
  const { showError, showSuccess } = useToast()
  const navigate = useNavigate()
  const [tasks, setTasks] = useState<Task[]>([])
  const [allTasks, setAllTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)
  const [sortOrder, setSortOrder] = useState<'desc' | 'asc'>('desc')
  const [selectedTaskType, setSelectedTaskType] = useState<'subscription' | 'comment' | 'view' | null>(null)
  const [selectedTask, setSelectedTask] = useState<TaskDetail | null>(null)
  const [showTaskModal, setShowTaskModal] = useState(false)
  const [loadingTaskDetail, setLoadingTaskDetail] = useState(false)
  const [processing, setProcessing] = useState(false)

  // Debounce для оптимизации запросов
  const [updateCounter, setUpdateCounter] = useState(0)

  useEffect(() => {
    if (!user) {
      setLoading(false)
      return
    }
    
    // Загружаем задания
    loadTasks()
    
    // Обновляем счетчик каждые 3 секунды (вместо каждой секунды)
    const interval = setInterval(() => {
      setUpdateCounter(prev => prev + 1)
    }, 3000)

    return () => clearInterval(interval)
  }, [user, sortOrder, selectedTaskType])

  useEffect(() => {
    if (!user || updateCounter === 0) return
    loadTasks()
  }, [updateCounter, user])

  async function loadTaskDetail(taskId: number) {
    if (!user) return
    setLoadingTaskDetail(true)
    try {
      const response = await axios.get(`${API_URL}/api/tasks/${taskId}`)
      setSelectedTask(response.data)
      setShowTaskModal(true)
    } catch (error: any) {
      console.error('Error loading task detail:', error)
      showError('Ошибка при загрузке задания')
    } finally {
      setLoadingTaskDetail(false)
    }
  }

  async function loadTasks() {
    if (!user) return
    
    try {
      const response = await axios.get(`${API_URL}/api/tasks/`, {
        params: { telegram_id: user.telegram_id }
      })
      
      setAllTasks(response.data || [])
      
      // Фильтрация по типу задания
      let filteredTasks = [...(response.data || [])]
      if (selectedTaskType) {
        filteredTasks = filteredTasks.filter(task => task.task_type === selectedTaskType)
      }
      
      // Сортировка только по цене
      let sortedTasks = [...filteredTasks]
      sortedTasks.sort((a, b) => {
        const priceA = parseFloat(a.price_per_slot_fiat || '0')
        const priceB = parseFloat(b.price_per_slot_fiat || '0')
        return sortOrder === 'desc' ? priceB - priceA : priceA - priceB
      })
      
      setTasks(sortedTasks)
    } catch (error: any) {
      console.error('Error loading tasks:', error)
      // Если пользователь не найден, попробуем создать его
      if (error.response?.status === 404) {
        try {
          await axios.post(`${API_URL}/api/users/`, {
            telegram_id: user.telegram_id,
            username: user.username,
            first_name: user.first_name
          })
          // Повторно загружаем задания
          const retryResponse = await axios.get(`${API_URL}/api/tasks/`, {
            params: { telegram_id: user.telegram_id }
          })
          setAllTasks(retryResponse.data || [])
          
          // Применяем фильтрацию и сортировку
          let filteredTasks = [...(retryResponse.data || [])]
          if (selectedTaskType) {
            filteredTasks = filteredTasks.filter(task => task.task_type === selectedTaskType)
          }
          
          let sortedTasks = [...filteredTasks]
          sortedTasks.sort((a, b) => {
            const priceA = parseFloat(a.price_per_slot_fiat || '0')
            const priceB = parseFloat(b.price_per_slot_fiat || '0')
            return sortOrder === 'desc' ? priceB - priceA : priceA - priceB
          })
          
          setTasks(sortedTasks)
        } catch (createError) {
          console.error('Error creating user:', createError)
          setTasks([])
        }
      } else {
        setTasks([])
      }
    } finally {
      setLoading(false)
    }
  }

  function currencySymbol(currency?: string) {
    switch (currency) {
      case 'USD': return '$'
      case 'EUR': return '€'
      case 'TON': return 'TON'
      default: return '₽'
    }
  }

  async function handleStartTask() {
    if (!user || !selectedTask) return
    
    setProcessing(true)
    try {
      if (selectedTask.task_type === 'view') {
        await axios.post(`${API_URL}/api/tasks/${selectedTask.id}/start`, null, {
          params: { telegram_id: user.telegram_id }
        })
        const channelLink = getChannelLink(selectedTask.telegram_channel_id)
        if (channelLink) {
          openTelegramLink(channelLink)
        }
        showSuccess('Задание выполнено! Средства зачислены на ваш баланс.')
        setShowTaskModal(false)
        loadTasks()
      } else if (selectedTask.task_type === 'subscription') {
        await axios.post(`${API_URL}/api/tasks/${selectedTask.id}/start`, null, {
          params: { telegram_id: user.telegram_id }
        })
        const channelLink = getChannelLink(selectedTask.telegram_channel_id)
        if (channelLink) {
          openTelegramLink(channelLink)
        }
        showSuccess('Задание начато! После проверки ботом средства будут зачислены.')
        setShowTaskModal(false)
        loadTasks()
      } else if (selectedTask.task_type === 'comment') {
        let postLink: string | null = null
        
        if (selectedTask.telegram_channel_id) {
          if (selectedTask.telegram_channel_id.startsWith('http://') || selectedTask.telegram_channel_id.startsWith('https://')) {
            postLink = selectedTask.telegram_channel_id
          } else {
            postLink = getPostLink(selectedTask.telegram_channel_id, selectedTask.telegram_post_id)
          }
        } else {
          postLink = getPostLink(selectedTask.telegram_channel_id, selectedTask.telegram_post_id)
        }
        
        if (!postLink) {
          showError('Ссылка на пост не найдена')
          setProcessing(false)
          return
        }
        
        await axios.post(`${API_URL}/api/tasks/${selectedTask.id}/start`, null, {
          params: { telegram_id: user.telegram_id }
        })
        
        openTelegramLink(postLink)
        showSuccess('Задание начато! После проверки ботом средства будут зачислены.')
        setShowTaskModal(false)
        loadTasks()
      }
    } catch (error: any) {
      console.error('Error starting task:', error)
      showError(error.response?.data?.detail || 'Ошибка при старте задания')
    } finally {
      setProcessing(false)
    }
  }

  if (loading) {
    return (
      <div className="earn-page">
        <div style={{ height: '20px' }}></div>
        <div className="earn-header">
          <button
            className="all-tasks-filter-btn active"
            disabled
          >
            Все задания
          </button>
        </div>
        <div style={{ padding: '20px', color: '#9ca3af', textAlign: 'center', fontSize: '14px' }}>
          Загрузка заданий…
        </div>
      </div>
    )
  }

  // Показываем все задания, проверка профиля будет при нажатии "Заработать"

  return (
    <div className="earn-page">
      {/* Отступ сверху */}
      <div style={{ height: '10px' }}></div>
      
      <div className="earn-header">
        <button
          onClick={() => setSelectedTaskType(null)}
          className={`all-tasks-filter-btn ${selectedTaskType === null ? 'active' : ''}`}
        >
          Все задания
        </button>
        <div className="sort-controls-minimal">
          <div className="task-type-filters">
            <button
              onClick={() => setSelectedTaskType(selectedTaskType === 'subscription' ? null : 'subscription')}
              className={`task-type-filter-btn ${selectedTaskType === 'subscription' ? 'active' : ''}`}
              title="Подписка"
            >
              <Bell size={18} />
            </button>
            <button
              onClick={() => setSelectedTaskType(selectedTaskType === 'comment' ? null : 'comment')}
              className={`task-type-filter-btn ${selectedTaskType === 'comment' ? 'active' : ''}`}
              title="Комментарий"
            >
              <MessageSquare size={18} />
            </button>
            <button
              onClick={() => setSelectedTaskType(selectedTaskType === 'view' ? null : 'view')}
              className={`task-type-filter-btn ${selectedTaskType === 'view' ? 'active' : ''}`}
              title="Просмотр"
            >
              <Eye size={18} />
            </button>
          </div>
          <button
            onClick={() => setSortOrder(sortOrder === 'desc' ? 'asc' : 'desc')}
            className="sort-order-btn-minimal"
            title={sortOrder === 'desc' ? 'По убыванию цены' : 'По возрастанию цены'}
          >
            {sortOrder === 'desc' ? '↓' : '↑'}
          </button>
        </div>
      </div>

      {/* Задания пользователей */}
      <div className="tasks-list">
        {tasks.length === 0 ? (
          <div className="no-tasks">Нет доступных заданий</div>
        ) : (
          tasks.map((task) => (
            <TaskCard
              key={task.id}
              task={task}
              fiatCurrency={task.fiat_currency}
              onStart={() => {
                // Проверяем профиль при нажатии "Заработать"
                if (!user?.age || !user?.gender || !user?.country) {
                  showError('Для выполнения заданий необходимо заполнить профиль')
                  navigate('/profile')
                  return
                }
                loadTaskDetail(task.id)
              }}
              onRefresh={loadTasks}
            />
          ))
        )}
      </div>

      {/* Модальное окно с деталями задания */}
      {showTaskModal && selectedTask && (
        <div className="task-modal-overlay" onClick={() => setShowTaskModal(false)}>
          <div className="task-modal-content" onClick={(e) => e.stopPropagation()}>
            <button className="task-modal-close" onClick={() => setShowTaskModal(false)}>
              <X size={20} />
            </button>
            
            {loadingTaskDetail ? (
              <div className="loading">Загрузка...</div>
            ) : (
              <>
                <div className="task-modal-header">
                  {selectedTask.task_type !== 'subscription' && selectedTask.task_type !== 'comment' && (
                    <div className="task-type-badge">
                      {selectedTask.task_type === 'comment' && <MessageSquare size={16} color="#2196F3" />}
                      {selectedTask.task_type === 'view' && <Eye size={16} color="#FF9800" />}
                      <span>
                        {selectedTask.task_type === 'comment' && 'Комментарий'}
                        {selectedTask.task_type === 'view' && 'Просмотр'}
                      </span>
                    </div>
                  )}
                  <h2 className={selectedTask.task_type === "subscription" || selectedTask.task_type === "comment" ? "task-modal-title-small" : "task-modal-title"}>
                    {selectedTask.title}
                  </h2>
                  {selectedTask.description && (
                    <p className="task-modal-description">{selectedTask.description}</p>
                  )}
                </div>

                <div className="task-modal-rules">
                  <div className="rules-header">
                    <AlertCircle size={18} />
                    <h3>Правила выполнения</h3>
                  </div>
                  <ul>
                    {selectedTask.task_type === 'subscription' && (
                      <>
                        <li>Не отписывайтесь в течение 7 дней, иначе средства не поступят на ваш баланс</li>
                        <li>Средства будут зачислены на ваш баланс через 7 дней после проверки</li>
                        <li>Проверяйте канал, перед тем, как подписаться. Не подписывайтесь на сомнительные каналы.</li>
                      </>
                    )}
                    {selectedTask.task_type === 'comment' && (
                      <>
                        <li>Не публиковать оскорбительные и нарушающие правила телеграма сообщения.</li>
                        <li>Нельзя удалять комментарий после публикации, иначе бан.</li>
                        <li>За невыполнения правил - бан.</li>
                        <li>Проверяйте пост, перед тем, как оставлять в нем сообщения. Не оставляйте комментарии под сомнительными постами.</li>
                      </>
                    )}
                    {selectedTask.task_type === 'view' && (
                      <>
                        <li>Откройте и просмотрите публикацию</li>
                        <li>Средства будут зачислены автоматически</li>
                      </>
                    )}
                  </ul>
                </div>

                {selectedTask.task_type !== "subscription" && selectedTask.task_type !== "comment" && (
                  <div className="task-modal-price">
                    <span className="price-label">Награда:</span>
                    <span className="price-value">
                      {parseFloat(selectedTask.price_per_slot_fiat).toFixed(2)} {currencySymbol(selectedTask.fiat_currency)}
                    </span>
                  </div>
                )}

                <button
                  className="task-modal-button"
                  onClick={handleStartTask}
                  disabled={processing}
                >
                  {processing ? 'Обработка...' : 
                    selectedTask.task_type === 'subscription' ? 'Подписаться' : 
                    selectedTask.task_type === 'comment' ? 'Оставить комментарий' : 
                    'Заработать'}
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}


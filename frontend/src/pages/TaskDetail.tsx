import { useEffect, useState } from 'react'
import { WebApp } from '@twa-dev/sdk'
import { useParams, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import axios from 'axios'
import { Bell, MessageSquare, Eye, AlertCircle } from 'lucide-react'
import './TaskDetail.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function getChannelLink(channelId: string | undefined): string | null {
    if (!channelId) return null
    
    // Если это полная ссылка (http:// или https://), используем напрямую
    if (channelId.startsWith('http://') || channelId.startsWith('https://')) {
      return channelId
    }
    
    // Если начинается с @, убираем его
    const cleanId = channelId.replace(/^@/, '')
    
    // Формируем ссылку
    return `https://t.me/${cleanId}`
}

// Функция для формирования ссылки на пост Telegram
function getPostLink(channelId: string | undefined, postId: string | number | undefined): string | null {
    // Если channelId - это уже полная ссылка (для заданий с комментариями), используем её напрямую
    if (channelId && (channelId.startsWith('http://') || channelId.startsWith('https://'))) {
      return channelId
    }
    
    // Если есть и channelId, и postId, формируем ссылку
    if (channelId && postId) {
      const cleanChannelId = channelId.replace(/^@/, '')
      return `https://t.me/${cleanChannelId}/${postId}`
    }
    
    // Если только channelId, возвращаем ссылку на канал
    if (channelId) {
      return getChannelLink(channelId)
    }
    
    return null
}

interface Task {
  id: number
  title: string
  description?: string
  task_type: 'subscription' | 'comment' | 'view'
  price_per_slot_ton: string
  price_per_slot_fiat: string
  fiat_currency?: string
  telegram_channel_id?: string
  comment_instruction?: string
  telegram_post_id?: string | number
}


// Функция для открытия ссылки через Telegram WebApp API
function openTelegramLink(url: string) {
  if (!url) {
    console.error('URL is empty!')
    return
  }
  
  console.log('Opening link:', url)
  
  // Проверяем наличие Telegram WebApp API
  const tg = (window as any).Telegram?.WebApp
  if (tg) {
    console.log('Using Telegram WebApp API')
    // Для Telegram-ссылок используем openTelegramLink, для остальных - openLink
    if (url.startsWith('https://t.me/') || url.startsWith('http://t.me/')) {
      tg.openTelegramLink(url)
    } else {
      tg.openLink(url)
    }
  } else {
    console.log('Telegram WebApp not available, using window.open')
    // Fallback на обычный window.open
    const newWindow = window.open(url, '_blank')
    if (!newWindow) {
      // Если popup заблокирован, пробуем через location
      window.location.href = url
    }
  }
}

export default function TaskDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const { showSuccess, showError } = useToast()
  const [task, setTask] = useState<Task | null>(null)
  const [loading, setLoading] = useState(true)
  const [processing, setProcessing] = useState(false)
  const [showModal, setShowModal] = useState(false)
  const [showCompletionModal, setShowCompletionModal] = useState(false)
  const [fiatCurrency, setFiatCurrency] = useState<string>('RUB')
  const [userTaskStarted, setUserTaskStarted] = useState(false)

  useEffect(() => {
    loadTask()
    loadCurrency()
  }, [id])

  async function loadCurrency() {
    if (!user) return
    try {
      const response = await axios.get(`${API_URL}/api/balance/${user.telegram_id}`)
      if (response.data?.fiat_currency) {
        setFiatCurrency(response.data.fiat_currency)
      }
    } catch (error) {
      console.error('Error loading currency:', error)
    }
  }

  async function loadTask() {
    try {
      const response = await axios.get(`${API_URL}/api/tasks/${id}`)
      console.log('[TaskDetail] Loaded task data:', response.data)
      console.log('[TaskDetail] telegram_channel_id:', response.data.telegram_channel_id)
      console.log('[TaskDetail] telegram_post_id:', response.data.telegram_post_id)
      console.log('[TaskDetail] task_type:', response.data.task_type)
      setTask(response.data)
    } catch (error) {
      console.error('Error loading task:', error)
    } finally {
      setLoading(false)
    }
  }

  async function handleStart() {
    if (!user || !task) return
    
    // Если задача уже начата, просто открываем ссылку напрямую
    if (userTaskStarted) {
      if (task.task_type === 'subscription') {
        const channelLink = getChannelLink(task.telegram_channel_id)
        if (channelLink) {
          console.log('Opening channel link:', channelLink)
          openTelegramLink(channelLink)
        }
        return
      } else if (task.task_type === 'comment') {
        console.log('[TaskDetail] Comment task - checking link')
        console.log('[TaskDetail] task.telegram_channel_id:', task.telegram_channel_id)
        console.log('[TaskDetail] task.telegram_post_id:', task.telegram_post_id)
        
        // Для комментариев ссылка должна быть в telegram_channel_id
        const postLink = task.telegram_channel_id || getPostLink(task.telegram_channel_id, task.telegram_post_id)
        console.log('[TaskDetail] Comment task - postLink:', postLink)
        
        if (postLink) {
          console.log('[TaskDetail] Opening post link:', postLink)
          openTelegramLink(postLink)
        } else {
          console.error('[TaskDetail] No post link found! channel_id:', task.telegram_channel_id, 'post_id:', task.telegram_post_id)
          showError('Ссылка на пост не найдена')
        }
        return
      }
    }
    
    setProcessing(true)
    try {
      if (task.task_type === 'view') {
        await axios.post(`${API_URL}/api/tasks/${task.id}/start`, null, {
          params: { telegram_id: user.telegram_id }
        })
        const channelLink = getChannelLink(task.telegram_channel_id)
        if (channelLink) {
          console.log('Opening channel link:', channelLink)
          openTelegramLink(channelLink)
        }
        showSuccess('Задание выполнено! Средства зачислены на ваш баланс.')
        setTimeout(() => { navigate('/earn') }, 2000)
      } else if (task.task_type === 'subscription') {
        await axios.post(`${API_URL}/api/tasks/${task.id}/start`, null, {
          params: { telegram_id: user.telegram_id }
        })
        const channelLink = getChannelLink(task.telegram_channel_id)
        if (channelLink) {
          console.log('Opening channel link:', channelLink)
          openTelegramLink(channelLink)
        }
        showSuccess('Задание начато! После проверки ботом средства будут зачислены на ваш баланс.')
        setTimeout(() => { navigate('/earn') }, 2000)
      } else if (task.task_type === 'comment') {
        console.log('[TaskDetail] Starting comment task')
        console.log('[TaskDetail] task.telegram_channel_id:', task.telegram_channel_id)
        console.log('[TaskDetail] task.telegram_post_id:', task.telegram_post_id)
        
        // Для комментариев ссылка должна быть в telegram_channel_id
        const postLink = task.telegram_channel_id || getPostLink(task.telegram_channel_id, task.telegram_post_id)
        console.log('[TaskDetail] Starting comment task - postLink:', postLink)
        
        if (postLink) {
          console.log('[TaskDetail] Opening post link:', postLink)
          openTelegramLink(postLink)
        } else {
          console.error('[TaskDetail] No post link found! channel_id:', task.telegram_channel_id, 'post_id:', task.telegram_post_id)
          showError('Ссылка на пост не найдена')
          setProcessing(false)
          return
        }
        await axios.post(`${API_URL}/api/tasks/${task.id}/start`, null, {
          params: { telegram_id: user.telegram_id }
        })
        showSuccess('Задание начато! После проверки ботом средства будут зачислены на ваш баланс.')
        setTimeout(() => { navigate('/earn') }, 2000)
      }
    } catch (error: any) {
      console.error('Error starting task:', error)
      if (error.response?.data?.detail) {
        const errorDetail = error.response.data.detail
        if (errorDetail === 'Task already started') {
          setUserTaskStarted(true)
          if (task.task_type === 'subscription') {
            const channelLink = getChannelLink(task.telegram_channel_id)
            if (channelLink) {
              console.log('Opening channel link:', channelLink)
              openTelegramLink(channelLink)
            }
            showSuccess('Задание уже начато. После проверки ботом средства будут зачислены.')
            setTimeout(() => { navigate('/earn') }, 2000)
          } else if (task.task_type === 'comment') {
            // Для комментариев ссылка должна быть в telegram_channel_id
            const postLink = task.telegram_channel_id || getPostLink(task.telegram_channel_id, task.telegram_post_id)
            console.log('[TaskDetail] Comment task (already started) - postLink:', postLink)
            if (postLink) {
              console.log('[TaskDetail] Opening post link:', postLink)
              openTelegramLink(postLink)
            } else {
              console.error('[TaskDetail] No post link found! channel_id:', task.telegram_channel_id)
              showError('Ссылка на пост не найдена')
            }
          }
        } else {
          showError(errorDetail)
        }
      } else {
        showError('Ошибка при старте задания')
      }
    } finally {
      setProcessing(false)
    }
  }

  async function handleComplete() {
    if (!user || !task) return
    setProcessing(true)
    try {
      await axios.post(`${API_URL}/api/tasks/${task.id}/complete`, null, {
        params: { telegram_id: user.telegram_id }
      })
      showSuccess('Задание выполнено! Средства зачислены на ваш баланс.')
      setShowModal(false)
      setShowCompletionModal(true)
      setTimeout(() => { navigate('/earn') }, 1500)

    } catch (error: any) {
      console.error('Error starting task:', error)
      if (error.response?.data?.detail) {
        const errorDetail = error.response.data.detail
        if (errorDetail === 'Task already started') {
          // Если задание уже начато, просто открываем ссылку
          setUserTaskStarted(true)
          if (task.task_type === 'subscription') {
            const channelLink = getChannelLink(task.telegram_channel_id)
            if (channelLink) {
              console.log('Opening channel link:', channelLink)
              openTelegramLink(channelLink)
            }
            showSuccess('Задание уже начато. После проверки ботом средства будут зачислены.')
            setTimeout(() => { navigate('/earn') }, 2000)
          } else if (task.task_type === 'comment') {
            const postLink = getPostLink(task.telegram_channel_id, task.telegram_post_id)
            console.log('Comment task - post_id:', task.telegram_post_id, 'channel_id:', task.telegram_channel_id, 'postLink:', postLink)
            if (postLink) {
              console.log('Opening post link:', postLink)
              openTelegramLink(postLink)
            } else {
              console.error('No post link found! post_id:', task.telegram_post_id, 'channel_id:', task.telegram_channel_id)
              showError('Ссылка на пост не найдена')
            }
          }
        } else {
          showError(errorDetail)
        }
      } else {
        showError('Ошибка при старте задания')
      }
    } finally {
      setProcessing(false)
    }
  }

  async function handleComplete() {
    if (!user || !task) return
    setProcessing(true)
    try {
      await axios.post(`${API_URL}/api/tasks/${task.id}/complete`, null, {
        params: { telegram_id: user.telegram_id }
      })
      showSuccess('Задание выполнено! Средства зачислены на ваш баланс.')
      setShowModal(false)
      setShowCompletionModal(true)
      setTimeout(() => { navigate('/earn') }, 1500)
    } catch (error: any) {
      console.error('Error completing task:', error)
      showError(error.response?.data?.detail || 'Ошибка при завершении задания')
    } finally {
      setProcessing(false)
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

  if (loading || !task) {
    return (
      <div className="task-detail-page">
        <div className="task-detail-card">
          <div className="loading">Загрузка...</div>
        </div>
      </div>
    )
  }

  const isCreator = user?.telegram_id === 0

  return (
    <div className="task-detail-page">
      <div className="task-detail-card">
        <div className="task-header">
          {task.task_type !== 'subscription' && task.task_type !== 'comment' && (
          <div className="task-type-badge">
            {task.task_type === 'comment' && <MessageSquare size={16} color="#2196F3" />}
            {task.task_type === 'view' && <Eye size={16} color="#FF9800" />}
            <span>
              {task.task_type === 'comment' && 'Комментарий'}
              {task.task_type === 'view' && 'Просмотр'}
            </span>
            {task.is_test && (
              <span className="task-demo-badge">ПРИМЕР</span>
            )}
          </div>
        )}
          <div className="task-title-block">
            <h1 className={(task.task_type === "subscription" || task.task_type === "comment") ? "task-title-small" : ""}>{task.title}</h1>
            {task.description && <p className="task-description-spaced">{task.description}</p>}
          </div>
        </div>
        {task.task_type !== 'subscription' && task.task_type !== 'comment' && (
          <div className="task-meta">
            <div className="meta-item">
              <span>Всего слотов</span>
              <strong>{task.telegram_channel_id ? '—' : '∞'}</strong>
            </div>
            <div className="meta-item">
              <span>Опубликовано</span>
              <strong>Сегодня</strong>
            </div>
          </div>
        )}

        

        <div className={`task-rules ${(task.task_type === "subscription" || task.task_type === "comment") ? "task-rules-spaced" : ""}`}>
          <div className="rules-header">
            <AlertCircle size={18} />
            <h3>Правила выполнения</h3>
          </div>
          <ul>
            {task.task_type === 'subscription' && (
              <>
                <li>Не отписывайтесь в течение 7 дней, иначе средства не поступят на ваш баланс</li>
                <li>Средства будут зачислены на ваш баланс через 7 дней после проверки</li>
                <li>Проверяйте канал, перед тем, как подписаться. Не подписывайтесь на сомнительные каналы.</li>
              </>
            )}
            {task.task_type === 'comment' && (
              <>
                <li>Не публиковать оскорбительные и нарушающие правила телеграма сообщения.</li>
                <li>Нельзя удалять комментарий после публикации, иначе бан.</li>
                <li>За невыполнения правил - бан.</li>
                <li>Проверяйте пост, перед тем, как оставлять в нем сообщения. Не оставляйте комментарии под сомнительными постами.</li>
              </>
            )}
            {task.task_type === 'view' && (
              <>
                <li>Откройте и просмотрите публикацию</li>
                <li>Средства будут зачислены автоматически</li>
              </>
            )}
          </ul>
        </div>

        {task.task_type !== "subscription" && task.task_type !== "comment" && (
        <div className="task-price-large">
          <span className="price-label">Награда:</span>
          <span className="price-value">
            {parseFloat(task.price_per_slot_fiat).toFixed(2)} {currencySymbol(task.fiat_currency || fiatCurrency)}
          </span>
        </div>
      )}

      {!isCreator && (
          <button
            className="earn-button-large"
            onClick={handleStart}
            disabled={processing}
          >
            {processing ? 'Обработка...' : userTaskStarted ? (
              task.task_type === 'subscription' ? 'Перейти к каналу' : 
              task.task_type === 'comment' ? 'Перейти к посту' : 
              'Продолжить'
            ) : (
              task.task_type === 'subscription' ? 'Подписаться' : task.task_type === 'comment' ? 'Оставить комментарий' : 'Заработать'
            )}
          </button>
        )}
      </div>

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>{task.title}</h2>
            
            {task.task_type === 'subscription' && (
              <div className="modal-rules">
                <h3>Правила выполнения:</h3>
                <ul>
                  <li>Не отписывайтесь в течение 7 дней, иначе средства не поступят на ваш баланс</li>
                  <li>Средства будут зачислены на ваш баланс через 7 дней после проверки</li>
                  <li>Проверяйте канал, перед тем, как подписаться. Не подписывайтесь на сомнительные каналы.</li>
                </ul>
              </div>
            )}
            {task.task_type === 'view' && (
              <div className="modal-instruction">
                <h3>Инструкция:</h3>
                <p>Просмотрите публикацию.</p>
              </div>
            )}
            <div className="modal-actions">
              <button className="modal-close" onClick={() => setShowModal(false)}>Закрыть</button>
              <button className="modal-complete" onClick={task.task_type === 'subscription' ? () => {
                const channelLink = getChannelLink(task.telegram_channel_id)
                if (channelLink) {
          console.log('Opening channel link:', channelLink)
          openTelegramLink(channelLink)
                }
              } :  handleComplete} disabled={processing}>
                {processing ? 'Отправка...' : task.task_type === 'subscription' ? 'Подписаться' : 'Подтвердить выполнение'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showCompletionModal && (
        <div className="modal-overlay" onClick={() => setShowCompletionModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>Готово!</h2>
            <p>Задание выполнено. Награда будет начислена после проверки.</p>
            <button className="modal-close" onClick={() => setShowCompletionModal(false)}>Закрыть</button>
          </div>
        </div>
      )}
    </div>
  )
}

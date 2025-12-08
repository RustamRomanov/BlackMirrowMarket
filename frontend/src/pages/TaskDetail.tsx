import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import axios from 'axios'
import { Bell, MessageSquare, Eye, AlertCircle } from 'lucide-react'
import './TaskDetail.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface Task {
  id: number
  title: string
  description?: string
  task_type: 'subscription' | 'comment' | 'view'
  price_per_slot_ton: string
  price_per_slot_fiat: string
  telegram_channel_id?: string
  comment_instruction?: string
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

  useEffect(() => {
    loadTask()
  }, [id])

  async function loadTask() {
    try {
      const response = await axios.get(`${API_URL}/api/tasks/${id}`)
      setTask(response.data)
    } catch (error) {
      console.error('Error loading task:', error)
    } finally {
      setLoading(false)
    }
  }

  async function handleStart() {
    if (!user || !task) return
    
    setProcessing(true)
    
    try {
      // Для просмотра - сразу выполняем
      if (task.task_type === 'view') {
        await axios.post(`${API_URL}/api/tasks/${task.id}/start`, null, {
          params: { telegram_id: user.telegram_id }
        })
        
        // Перенаправляем на канал
        if (task.telegram_channel_id) {
          window.open(`https://t.me/${task.telegram_channel_id.replace('@', '')}`, '_blank')
        }
        
        showSuccess('Задание выполнено! Средства зачислены на ваш баланс.')
        setTimeout(() => {
          navigate('/earn')
        }, 2000)
      } else if (task.task_type === 'subscription') {
        // Для подписки - запускаем задание и сразу открываем канал
        await axios.post(`${API_URL}/api/tasks/${task.id}/start`, null, {
          params: { telegram_id: user.telegram_id }
        })
        
        // Открываем инвайт ссылку на канал
        if (task.telegram_channel_id) {
          const channelId = task.telegram_channel_id.replace('@', '')
          window.open(`https://t.me/${channelId}`, '_blank')
        }
        
        // Показываем окно с кнопками завершения
        setShowCompletionModal(true)
      } else {
        // Для комментария - показываем модальное окно
        await axios.post(`${API_URL}/api/tasks/${task.id}/start`, null, {
          params: { telegram_id: user.telegram_id }
        })
        
        // Показываем модальное окно с информацией
        setShowModal(true)
      }
    } catch (error: any) {
      showError(error.response?.data?.detail || 'Ошибка при выполнении задания')
    } finally {
      setProcessing(false)
    }
  }

  async function handleConfirm() {
    if (!user || !task) return
    
    setProcessing(true)
    
    try {
      if (task.task_type === 'comment') {
        // Для комментария - перенаправляем на пост
        if (task.telegram_channel_id) {
          window.open(`https://t.me/${task.telegram_channel_id.replace('@', '')}`, '_blank')
        }
        
        // После того как пользователь оставит комментарий, он должен вызвать валидацию
        // В реальной версии это будет делать бот автоматически
        setTimeout(async () => {
          await axios.post(`${API_URL}/api/tasks/${task.id}/validate-comment`, null, {
            params: { telegram_id: user.telegram_id }
          })
          showSuccess('Комментарий проверен! Средства зачислены.')
          navigate('/earn')
        }, 3000)
      }
    } catch (error: any) {
      showError(error.response?.data?.detail || 'Ошибка')
    } finally {
      setProcessing(false)
      setShowModal(false)
    }
  }

  if (loading) {
    return <div className="task-detail-page">Загрузка...</div>
  }

  if (!task) {
    return <div className="task-detail-page">Задание не найдено</div>
  }

  const taskTypeConfig = {
    subscription: {
      icon: Bell,
      color: '#4CAF50',
      label: 'Подписка',
      bgColor: '#E8F5E9'
    },
    comment: {
      icon: MessageSquare,
      color: '#2196F3',
      label: 'Комментарий',
      bgColor: '#E3F2FD'
    },
    view: {
      icon: Eye,
      color: '#FF9800',
      label: 'Просмотр',
      bgColor: '#FFF3E0'
    }
  }

  const config = taskTypeConfig[task.task_type]
  const Icon = config.icon

  return (
    <div className="task-detail-page">
      <div className="task-detail-card">
        <div className="task-detail-header">
          <div className="task-type-badge-large" style={{ backgroundColor: config.bgColor }}>
            <Icon size={20} color={config.color} />
            <span style={{ color: config.color }}>{config.label}</span>
          </div>
        </div>

        <h1 className="task-detail-title">{task.title}</h1>
        {task.description && (
          <p className="task-detail-description">{task.description}</p>
        )}

        {task.task_type === 'comment' && task.comment_instruction && (
          <div className="task-instruction">
            <h3>Инструкция:</h3>
            <p>{task.comment_instruction}</p>
          </div>
        )}

        {task.task_type === 'subscription' && task.telegram_channel_id && (
          <div className="task-channel-info">
            <h3>Канал:</h3>
            <p>@{task.telegram_channel_id.replace('@', '')}</p>
          </div>
        )}

        <div className="task-rules">
          <div className="rules-header">
            <AlertCircle size={18} />
            <h3>Правила выполнения</h3>
          </div>
          <ul>
            {task.task_type === 'subscription' && (
              <>
                <li>Подпишитесь на указанный канал</li>
                <li>Не отписывайтесь в течение 7 дней</li>
                <li>Средства будут зачислены через 7 дней после проверки</li>
                <li>Не подписывайтесь на сомнительные каналы</li>
              </>
            )}
            {task.task_type === 'comment' && (
              <>
                <li>Оставьте комментарий согласно инструкции</li>
                <li>Не используйте ненормативную лексику</li>
                <li>Комментарий должен быть уникальным</li>
                <li>Средства будут зачислены после проверки ботом</li>
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

        <div className="task-price-large">
          <span className="price-label">Награда:</span>
          <span className="price-value">{parseFloat(task.price_per_slot_fiat).toFixed(2)} ₽</span>
        </div>

        <button
          className="earn-button-large"
          onClick={handleStart}
          disabled={processing}
        >
          {processing ? 'Обработка...' : 'Заработать'}
        </button>
      </div>

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>{task.title}</h2>
            
            {task.task_type === 'comment' && (
              <>
                <div className="modal-instruction">
                  <h3>Инструкция от заказчика:</h3>
                  <p>{task.comment_instruction || 'Оставьте комментарий'}</p>
                </div>
                <div className="modal-rules">
                  <h3>Правила приложения:</h3>
                  <ul>
                    <li>Комментарий должен соответствовать инструкции</li>
                    <li>Запрещена ненормативная лексика</li>
                    <li>Комментарий должен быть уникальным</li>
                    <li>После оставления комментария средства будут зачислены после проверки</li>
                  </ul>
                </div>
              </>
            )}

            {task.task_type === 'subscription' && (
              <>
                <div className="modal-channel">
                  <h3>Информация о канале:</h3>
                  <p>@{task.telegram_channel_id?.replace('@', '')}</p>
                </div>
                <div className="modal-rules">
                  <h3>Важно помнить:</h3>
                  <ul>
                    <li>Оцените, подходит ли вам этот канал</li>
                    <li>Не отписывайтесь в течение 7 дней</li>
                    <li>Иначе средства не будут переведены с эскроу на ваш счет</li>
                    <li>Средства будут зачислены через 7 дней после проверки</li>
                    <li>Не подписывайтесь на сомнительные каналы</li>
                  </ul>
                </div>
              </>
            )}

            <button
              className="modal-confirm-button"
              onClick={handleConfirm}
              disabled={processing}
            >
              {processing ? 'Обработка...' : 'Продолжить'}
            </button>
          </div>
        </div>
      )}

      {/* Окно завершения для подписки */}
      {showCompletionModal && (
        <div className="modal-overlay" onClick={() => setShowCompletionModal(false)}>
          <div className="modal-content completion-modal" onClick={(e) => e.stopPropagation()}>
            <h2>Подписка выполнена</h2>
            <p className="completion-text">
              Вы были перенаправлены на канал. Если вы подписались, нажмите "Завершить".
            </p>
            <p className="completion-warning">
              Если канал показался вам сомнительным, вы можете пожаловаться на задание.
            </p>
            
            <div className="completion-buttons">
              <button
                className="completion-button complete-btn"
                onClick={async () => {
                  setShowCompletionModal(false)
                  showSuccess('Подписка зарегистрирована! Средства будут зачислены через 7 дней после проверки.')
                  navigate('/earn')
                }}
                disabled={processing}
              >
                Завершить
              </button>
              
              <button
                className="completion-button report-btn"
                onClick={async () => {
                  if (!user || !task) return
                  
                  setProcessing(true)
                  try {
                    // Отправляем жалобу на задание
                    await axios.post(`${API_URL}/api/tasks/${task.id}/report`, null, {
                      params: { telegram_id: user.telegram_id }
                    })
                    
                    setShowCompletionModal(false)
                    showSuccess('Жалоба отправлена модератору. Задание завершено.')
                    navigate('/earn')
                  } catch (error: any) {
                    showError(error.response?.data?.detail || 'Ошибка при отправке жалобы')
                  } finally {
                    setProcessing(false)
                  }
                }}
                disabled={processing}
              >
                Пожаловаться на задание
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}


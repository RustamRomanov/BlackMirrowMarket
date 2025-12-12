import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import axios from 'axios'
import { Bell, MessageSquare, Eye } from 'lucide-react'
import TaskCard from '../components/TaskCard'
import { TaskCardSkeleton } from '../components/Skeleton'
import './Earn.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface Task {
  id: number
  title: string
  description?: string
  task_type: 'subscription' | 'comment' | 'view'
  price_per_slot_ton: string
  price_per_slot_fiat: string
  total_slots: number
  completed_slots: number
  remaining_slots: number
  telegram_channel_id?: string
  comment_instruction?: string
}

export default function Earn() {
  const { user } = useAuth()
  const { showError } = useToast()
  const navigate = useNavigate()
  const [fiatCurrency, setFiatCurrency] = useState<string>(() => {
    if (typeof window === 'undefined') return 'RUB'
    return localStorage.getItem('fiatCurrency') || 'RUB'
  })
  const [tasks, setTasks] = useState<Task[]>([])
  const [allTasks, setAllTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)
  const [sortOrder, setSortOrder] = useState<'desc' | 'asc'>('desc')
  const [selectedTaskType, setSelectedTaskType] = useState<'subscription' | 'comment' | 'view' | null>(null)
  // Debounce для оптимизации запросов
  const [updateCounter, setUpdateCounter] = useState(0)

  useEffect(() => {
    if (!user) {
      setLoading(false)
      return
    }
    
    // Убрана автоматическая инициализация тестовых заданий
    // Тестовые задания создаются вручную через админку и помечаются как примеры
    loadTasks()
    
    // Обновляем счетчик каждую секунду
    const interval = setInterval(() => {
      setUpdateCounter(prev => prev + 1)
    }, 1000)

    return () => clearInterval(interval)
  }, [user, sortOrder, selectedTaskType])

  useEffect(() => {
    if (!user || updateCounter === 0) return
    loadTasks()
  }, [updateCounter, user])

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

  if (loading) {
    return (
      <div className="earn-page">
        <div className="earn-header">
          <button
            className="all-tasks-filter-btn active"
            disabled
          >
            Все задания
          </button>
        </div>
        <div className="tasks-list">
          {[...Array(5)].map((_, i) => (
            <TaskCardSkeleton key={i} />
          ))}
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
              fiatCurrency={fiatCurrency}
              onStart={() => {
                // Проверяем профиль при нажатии "Заработать"
                if (!user?.age || !user?.gender || !user?.country) {
                  showError('Для выполнения заданий необходимо заполнить профиль')
                  navigate('/profile')
                  return
                }
                navigate(`/task/${task.id}`)
              }}
              onRefresh={loadTasks}
            />
          ))
        )}
      </div>
    </div>
  )
}


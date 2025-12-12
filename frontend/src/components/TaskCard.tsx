import { Bell, MessageSquare, Eye } from 'lucide-react'
import './TaskCard.css'

interface Task {
  id: number
  title: string
  description?: string
  task_type: 'subscription' | 'comment' | 'view'
  price_per_slot_ton: string
  price_per_slot_fiat: string
  fiat_currency?: string
  total_slots: number
  completed_slots: number
  remaining_slots: number
  is_test?: boolean
}

interface TaskCardProps {
  task: Task
  onStart: () => void
}

const taskTypeConfig = {
  subscription: {
    icon: Bell,
    color: '#4ade80',
    title: 'Подписаться на канал',
    bgClass: 'task-card--subscription'
  },
  comment: {
    icon: MessageSquare,
    color: '#c084fc',
    title: 'Оставить комментарий',
    bgClass: 'task-card--comment'
  },
  view: {
    icon: Eye,
    color: '#fbbf24',
    title: 'Просмотреть пост',
    bgClass: 'task-card--view'
  }
}

export default function TaskCard({ task, onStart }: TaskCardProps) {
  const config = taskTypeConfig[task.task_type]
  const Icon = config.icon
  const price = parseFloat(task.price_per_slot_fiat || '0')
  const currency = task.fiat_currency || '₽'

  return (
    <div className={`task-card ${config.bgClass}`}>
      <div className="task-card-left">
        <div className="task-type-line">
          <div className="task-type-icon" style={{ color: config.color }}>
            <Icon size={14} />
          </div>
          <div className="task-type-title" style={{ color: config.color }}>
            {config.title}
          </div>
          {task.is_test && (
            <span className="task-demo-badge">ПРИМЕР</span>
          )}
        </div>
        <div className="task-content">
          <h3 className="task-title">{task.title}</h3>
          {task.description && (
            <p className="task-description">{task.description}</p>
          )}
        </div>
        <div className="task-available">
          Доступно: <span>{task.remaining_slots}</span>
        </div>
      </div>
      <div className="task-card-right">
        <button className="earn-button" onClick={onStart}>
          Заработать
        </button>
        <div className="task-price-block">
          <div className="task-price">
            {price.toFixed(2)} {currency}
          </div>
        </div>
      </div>
    </div>
  )
}

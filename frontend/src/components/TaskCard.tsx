import { Bell, MessageSquare, Eye } from 'lucide-react'
import './TaskCard.css'

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
  is_test?: boolean
}

interface TaskCardProps {
  task: Task
  onStart: () => void
  fiatCurrency?: string
}

const taskTypeConfig = {
  subscription: {
    icon: Bell,
    color: '#2e7d32',
    label: 'Подписка',
    bg: 'linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%)',
  },
  comment: {
    icon: MessageSquare,
    color: '#1565c0',
    label: 'Комментарий',
    bg: 'linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%)',
  },
  view: {
    icon: Eye,
    color: '#ef6c00',
    label: 'Просмотр',
    bg: 'linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%)',
  },
}

const currencySymbol = (cur?: string) => {
  switch (cur) {
    case 'USD':
      return '$'
    case 'EUR':
      return '€'
    case 'TON':
      return 'TON'
    case 'RUB':
    default:
      return '₽'
  }
}

export default function TaskCard({ task, onStart, fiatCurrency }: TaskCardProps) {
  const config = taskTypeConfig[task.task_type]
  const Icon = config.icon
  const title = task.title === 'Задание' ? '' : task.title
  const userCurrency = fiatCurrency || (typeof window !== 'undefined' ? localStorage.getItem('fiatCurrency') || 'RUB' : 'RUB')

  return (
    <div className={`task-card task-${task.task_type}`}>
      <div className="task-card-bg" style={{ background: config.bg }} />
      <div className="task-card-top">
        <div className="task-type-badge">
          <Icon size={16} color={config.color} />
          <span style={{ color: config.color }}>{config.label}</span>
          {task.is_test && (
            <span className="task-test-chip">ПРИМЕР</span>
          )}
        </div>
        <div className="task-price">
          {parseFloat(task.price_per_slot_fiat).toFixed(2)} {currencySymbol(userCurrency)}
        </div>
      </div>

      <div className="task-content">
        {title && <h3 className="task-title">{title}</h3>}
        {task.description && <p className="task-description">{task.description}</p>}
      </div>

      <div className="task-card-bottom">
        <div className="task-meta">
          <span className="task-remaining">
            Осталось: <strong>{task.remaining_slots}</strong>
          </span>
        </div>
        <button className="earn-button sheen" onClick={onStart}>
          Заработать
        </button>
      </div>
    </div>
  )
}





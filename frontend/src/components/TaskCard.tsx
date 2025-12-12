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
  fiatCurrency?: string
  onStart: () => void
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

function currencySymbol(currency?: string) {
  switch (currency) {
    case 'USD': return '$'
    case 'EUR': return '€'
    case 'TON': return 'TON'
    default: return '₽'
  }
}

export default function TaskCard({ task, onStart, fiatCurrency }: TaskCardProps) {
  const config = taskTypeConfig[task.task_type]
  const Icon = config.icon
  const displayCurrency = fiatCurrency || task.fiat_currency || 'RUB'
  const symbol = currencySymbol(displayCurrency)

  return (
    <div className="task-card">
      <div className="task-card-left">
        <div className="task-type-badge" style={{ backgroundColor: config.bgColor }}>
          <Icon size={16} color={config.color} />
          <span style={{ color: config.color }}>{config.label}</span>
          {task.is_test && (
            <span style={{ marginLeft: '8px', padding: '2px 6px', background: '#ff9800', color: 'white', borderRadius: '4px', fontSize: '10px', fontWeight: '600' }}>
              ПРИМЕР
            </span>
          )}
        </div>
        <div className="task-content">
          <h3 className="task-title">{task.title}</h3>
          {task.description && (
            <p className="task-description">{task.description}</p>
          )}
        </div>
        <div className="task-remaining">
          Осталось: <strong>{task.remaining_slots}</strong>
        </div>
      </div>
      <div className="task-card-right">
        <div className="task-price">
          {parseFloat(task.price_per_slot_fiat).toFixed(2)} {symbol}
        </div>
        <button className="earn-button" onClick={onStart}>
          Заработать
        </button>
      </div>
    </div>
  )
}

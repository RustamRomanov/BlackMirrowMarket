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
  fiat_currency?: string
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
    label: 'Подписка'
  },
  comment: {
    icon: MessageSquare,
    color: '#2196F3',
    label: 'Комментарий'
  },
  view: {
    icon: Eye,
    color: '#FF9800',
    label: 'Просмотр'
  }
}

function currencySymbol(code: string): string {
  if (code === 'USD') return '$'
  if (code === 'EUR') return '€'
  if (code === 'TON') return 'TON'
  return '₽'
}

export default function TaskCard({ task, fiatCurrency, onStart }: TaskCardProps) {
  const config = taskTypeConfig[task.task_type]
  const Icon = config.icon
  const currency = fiatCurrency || task.fiat_currency || 'RUB'
  const symbol = currencySymbol(currency)
  const price = parseFloat(task.price_per_slot_fiat)

  return (
    <div className={`task-card task-card--${task.task_type}`}>
      <div className="task-card-header">
        <div className="task-type-line">
          <Icon size={14} color={config.color} />
          <span style={{ color: config.color }}>{config.label}</span>
          {task.is_test && (
            <span className="test-badge">ПРИМЕР</span>
          )}
        </div>
      </div>
      
      <div className="task-content">
        <h3 className="task-title">{task.title}</h3>
        {task.description && (
          <p className="task-description">{task.description}</p>
        )}
      </div>

      <div className="task-footer">
        <div className="task-remaining">
          Осталось: <strong>{task.remaining_slots}</strong>
        </div>
        <div className="task-price-section">
          <div className="task-price-caption">
            Стоимость задания
          </div>
          <div className="task-price">
            {price.toFixed(2)} {symbol}
          </div>
        </div>
        <button className="earn-button" onClick={onStart}>
          Заработать
        </button>
      </div>
    </div>
  )
}





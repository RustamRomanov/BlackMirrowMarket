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
    color: '#7dd3fc',
    title: 'Подписаться на канал',
    bgColor: 'rgba(125, 211, 252, 0.12)'
  },
  comment: {
    icon: MessageSquare,
    color: '#c084fc',
    title: 'Оставить комментарий',
    bgColor: 'rgba(192, 132, 252, 0.12)'
  },
  view: {
    icon: Eye,
    color: '#fbbf24',
    title: 'Просмотреть пост',
    bgColor: 'rgba(251, 191, 36, 0.12)'
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

export default function TaskCard({ task, onStart }: TaskCardProps) {
  const config = taskTypeConfig[task.task_type]
  const Icon = config.icon
  const cleanTitle = task.title === 'Задание' ? '' : task.title
  const userCurrency =
    task.fiat_currency ||
    (typeof window !== 'undefined' ? localStorage.getItem('fiatCurrency') || 'RUB' : 'RUB')
  const priceTon = parseFloat(task.price_per_slot_ton || '0') / 10 ** 9
  const storedRate =
    typeof window !== 'undefined' ? parseFloat(localStorage.getItem('fiatRatePerTon') || '0') : 0
  const rate = storedRate > 0 ? storedRate : 250
  const displayPrice =
    userCurrency === 'TON'
      ? `${priceTon.toFixed(4)} TON`
      : `${(priceTon * rate).toFixed(2)} ${currencySymbol(userCurrency)}`

  return (
    <div className="task-card">
      <div className="task-card-left">
        <div className="task-type-line">
          <div className="task-type-icon" style={{ backgroundColor: config.bgColor, color: config.color }}>
            <Icon size={16} />
          </div>
          <div className="task-type-title" style={{ color: config.color }}>
            {config.title}
          </div>
          {task.is_test && (
            <span className="task-demo-badge">ПРИМЕР</span>
          )}
        </div>
        <div className="task-content">
          <h3 className="task-title">{cleanTitle}</h3>
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
            {displayPrice}
          </div>
          <div className="task-price-caption">стоимость задания</div>
        </div>
      </div>
    </div>
  )
}

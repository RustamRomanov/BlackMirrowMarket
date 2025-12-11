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
  const priceTon = parseFloat(task.price_per_slot_ton) / 10 ** 9
  const storedRate = typeof window !== 'undefined' ? parseFloat(localStorage.getItem('fiatRatePerTon') || '0') : 0
  const rate = storedRate > 0 ? storedRate : 250
  const displayPrice =
    userCurrency === 'TON'
      ? `${priceTon.toFixed(4)} TON`
      : `${(priceTon * rate).toFixed(2)} ${currencySymbol(userCurrency)}`

  return (
    <div className={`task-card task-${task.task_type}`}>
      <div className="task-card-bg" style={{ background: config.bg }} />
      <div className="task-card-top">
        <div className="task-left">
          <div className="task-type-badge">
            <Icon size={16} color={config.color} />
            <span style={{ color: config.color }}>{config.label}</span>
            {task.is_test && (
              <span className="task-test-chip">ПРИМЕР</span>
            )}
          </div>
          <span className="task-remaining inline left">
            Осталось слотов <strong>{task.remaining_slots}</strong>
          </span>
        </div>
        <div className="task-right">
          <button className="earn-button sheen" onClick={onStart}>
            <span className="earn-button-text">Заработать</span>
            <span className="earn-button-price">{displayPrice}</span>
          </button>
        </div>
      </div>

    </div>
  )
}





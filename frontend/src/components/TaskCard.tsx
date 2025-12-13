import { Bell, MessageSquare, Eye } from 'lucide-react'
import { useState, useEffect } from 'react'
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
<<<<<<< HEAD
  onStart: () => void
=======
  onRefresh?: () => void
>>>>>>> 9a42998934b9c436c76999cc9b35ec17f5c454bd
}

const taskTypeConfig = {
  subscription: {
    icon: Bell,
<<<<<<< HEAD
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
=======
    color: '#2e7d32',
    label: 'Подписка',
    title: 'Подпишись на канал',
    bg: 'linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%)',
  },
  comment: {
    icon: MessageSquare,
    color: '#1565c0',
    label: 'Комментарий',
    title: 'Оставить комментарий',
    bg: 'linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%)',
  },
  view: {
    icon: Eye,
    color: '#ef6c00',
    label: 'Просмотр',
    title: 'Посмотреть пост',
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

export default function TaskCard({ task, onStart, fiatCurrency, onRefresh }: TaskCardProps) {
  const config = taskTypeConfig[task.task_type]
  const Icon = config.icon
  const userCurrency = fiatCurrency || (typeof window !== 'undefined' ? localStorage.getItem('fiatCurrency') || 'RUB' : 'RUB')
  const priceTon = parseFloat(task.price_per_slot_ton) / 10 ** 9
  const storedRate = typeof window !== 'undefined' ? parseFloat(localStorage.getItem('fiatRatePerTon') || '0') : 0
  const rate = storedRate > 0 ? storedRate : 250
  const displayPrice =
    userCurrency === 'TON'
      ? `${priceTon.toFixed(4)} TON`
      : `${(priceTon * rate).toFixed(2)} ${currencySymbol(userCurrency)}`
>>>>>>> 9a42998934b9c436c76999cc9b35ec17f5c454bd

  // Состояние для счетчика доступных слотов с автообновлением
  const [remainingSlots, setRemainingSlots] = useState(task.remaining_slots)

  // Обновляем счетчик каждую секунду
  useEffect(() => {
    setRemainingSlots(task.remaining_slots)
    
    const interval = setInterval(() => {
      if (onRefresh) {
        onRefresh()
      }
    }, 1000)

    return () => clearInterval(interval)
  }, [task.remaining_slots, onRefresh])

  return (
<<<<<<< HEAD
    <div className={`task-card task-card--${task.task_type}`}>
      <div className="task-card-header">
        <div className="task-type-line">
          <Icon size={14} color={config.color} />
          <span style={{ color: config.color }}>{config.label}</span>
          {task.is_test && (
            <span className="test-badge">ПРИМЕР</span>
          )}
=======
    <div className={`task-card task-${task.task_type}`}>
      <div className="task-card-bg" style={{ background: config.bg }} />
      
      {/* Строка 1: Иконка + надпись типа задания */}
      <div className="task-row-1">
        <div className="task-type-label" style={{ color: config.color }}>
          <Icon size={14} color={config.color} />
          <span>{config.label}</span>
>>>>>>> 9a42998934b9c436c76999cc9b35ec17f5c454bd
        </div>
        {task.is_test && (
          <span className="task-test-chip">ПРИМЕР</span>
        )}
      </div>
      
      <div className="task-content">
        <h3 className="task-title">{task.title}</h3>
        {task.description && (
          <p className="task-description">{task.description}</p>
        )}
      </div>

<<<<<<< HEAD
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
=======
      {/* Строка 2-3: Описание + Кнопка */}
      <div className="task-row-2-3">
        {task.description && (
          <div className="task-description">{task.description}</div>
        )}
        <button className="earn-button-compact sheen" onClick={onStart}>
          <span className="earn-button-text-compact">Заработать</span>
          <span className="earn-button-price-compact">{displayPrice}</span>
        </button>
      </div>

      {/* Строка 4: Доступно (внизу) */}
      <div className="task-row-4">
        <div className="task-available-compact">
          <span className="task-available-label-compact">Доступно:</span>
          <span className="task-available-value-compact">{remainingSlots}</span>
        </div>
      </div>
>>>>>>> 9a42998934b9c436c76999cc9b35ec17f5c454bd
    </div>
  )
}





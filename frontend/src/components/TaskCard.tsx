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
  onStart: () => void
  onRefresh?: () => void
}

const taskTypeConfig = {
  subscription: {
    icon: Bell,

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

    </div>
  )
}





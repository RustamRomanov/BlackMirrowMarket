import { useState, useEffect } from 'react'
import { X } from 'lucide-react'
import TermsModal from './TermsModal'
import { useAuth } from '../context/AuthContext'
import axios from 'axios'
import './CreateTaskModal.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const ADMIN_BOT = '@BlackMirrowAdminBot'

const BOT_RULES_TEXT = `
Для работы заданий в вашем канале необходимо добавить бота @BlackMirrowAdminBot администратором.

**Почему это нужно:**
• Бот мониторит выполнение заданий пользователями
• Проверяет, что пользователи действительно подписались, оставили комментарий или просмотрели пост
• Бот не влияет на работу вашего канала
• Бот не публикует сообщения и не управляет каналом
• Бот только читает информацию для проверки выполнения заданий

**Что делает бот:**
• Отслеживает подписки пользователей на ваш канал
• Проверяет комментарии под постами
• Подтверждает просмотры публикаций
• Автоматически начисляет награды исполнителям

**Безопасность:**
• Бот имеет только права на чтение информации
• Бот не может удалять сообщения или пользователей
• Бот не может изменять настройки канала
• Все данные обрабатываются автоматически и безопасно
`

interface CreateTaskModalProps {
  onClose: () => void
  onSubmit: (formData: TaskFormData) => Promise<void>
}

export interface TaskFormData {
  title: string
  description: string
  task_type: 'subscription' | 'comment' | 'view'
  price_per_slot_ton: string
  total_slots: string
  telegram_channel_id: string
  telegram_post_id: string
  comment_instruction: string
  target_country: string
  target_gender: string
  target_age_min: string
  target_age_max: string
}

export default function CreateTaskModal({ onClose, onSubmit }: CreateTaskModalProps) {
  const { user } = useAuth()
  const [userBalance, setUserBalance] = useState<number>(0)
  
  const [formData, setFormData] = useState<TaskFormData>({
    title: '',
    description: '',
    task_type: 'view',
    price_per_slot_ton: '',
    total_slots: '',
    telegram_channel_id: '',
    telegram_post_id: '',
    comment_instruction: '',
    target_country: '',
    target_gender: 'both',
    target_age_min: '1',
    target_age_max: '100'
  })

  // Состояние для чекбоксов пола
  const [genderSelection, setGenderSelection] = useState({
    male: true,
    female: true
  })
  const [showPostHelp, setShowPostHelp] = useState(false)

  const [errors, setErrors] = useState<Record<string, string>>({})
  const [submitting, setSubmitting] = useState(false)
  const [botAdded, setBotAdded] = useState(false)
  const [showBotRules, setShowBotRules] = useState(false)

  // Загрузка баланса для расчета макс. слотов
  useEffect(() => {
    async function fetchBalance() {
      if (!user) return
      try {
        const response = await axios.get(`${API_URL}/api/balance/${user.telegram_id}`)
        if (response.data && response.data.ton_active_balance) {
          setUserBalance(parseFloat(response.data.ton_active_balance) / 10**9)
        }
      } catch (error) {
        console.error('Failed to fetch balance', error)
      }
    }
    fetchBalance()
  }, [user])

  // Расчет бюджета и макс слотов
  const price = parseFloat(formData.price_per_slot_ton) || 0
  const slots = parseInt(formData.total_slots) || 0
  const campaignBudget = price * slots
  const maxSlots = price > 0 ? Math.floor(userBalance / price) : 0

  function validateForm(): boolean {
    const newErrors: Record<string, string> = {}
    
    const titleTrim = formData.title.trim()
    if (!titleTrim) {
      newErrors.title = 'Название задания обязательно'
    } else if (titleTrim.length < 3) {
      newErrors.title = 'Минимум 3 символа'
    }
    
    const descTrim = formData.description.trim()
    if (!descTrim) {
      newErrors.description = 'Описание обязательно'
    } else {
      const words = descTrim.split(/\s+/).filter(Boolean)
      if (words.length < 3) {
        newErrors.description = 'Минимум 3 слова'
      }
    }
    
    if (!formData.price_per_slot_ton || price <= 0) {
      newErrors.price_per_slot_ton = 'Цена должна быть больше 0'
    }
    
    if (!formData.total_slots || slots < 1) {
      newErrors.total_slots = 'Количество слотов должно быть не менее 1'
    }

    if (campaignBudget > userBalance) {
      newErrors.total_slots = `Недостаточно средств. Ваш баланс: ${userBalance.toFixed(2)}`
    }
    
    if (formData.task_type === 'comment' && !formData.comment_instruction?.trim()) {
      newErrors.comment_instruction = 'Инструкция для комментария обязательна'
    }
    
    if ((formData.task_type === 'comment' || formData.task_type === 'view') && !formData.telegram_post_id) {
      newErrors.telegram_post_id = 'Ссылка поста обязательна'
    }
    
    if (formData.task_type !== 'view' && !formData.telegram_channel_id) {
      newErrors.telegram_channel_id = 'ID канала обязателен'
    }

    if (!genderSelection.male && !genderSelection.female) {
      newErrors.target_gender = 'Выберите хотя бы один пол'
    }
    
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    
    if (!validateForm()) {
      return
    }

    // Определяем target_gender на основе чекбоксов
    let finalGender = 'both'
    if (genderSelection.male && !genderSelection.female) finalGender = 'male'
    if (!genderSelection.male && genderSelection.female) finalGender = 'female'

    const submissionData = {
      ...formData,
      target_gender: finalGender
    }

    setSubmitting(true)
    try {
      await onSubmit(submissionData)
      onClose()
    } catch (error) {
      // Ошибка обрабатывается в родительском компоненте
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="create-task-modal-overlay" onClick={onClose}>
      <div className="create-task-modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="create-task-modal-header">
          <h2>Создать задание</h2>
          <button className="create-task-modal-close" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <form className="create-task-form" onSubmit={handleSubmit}>
          <div className="create-task-form-body" id="create-task-scroll">
            {/* Тип задания в начало */}
            <div className="form-field-group">
              <label className="form-label">
                Тип задания
              </label>
              <select
                value={formData.task_type}
                onChange={(e) => {
                  const newType = e.target.value as 'subscription' | 'comment' | 'view'
                  setFormData({ ...formData, task_type: newType })
                }}
                className="form-input"
                style={{ color: '#333' }}
              >
                <option value="view">Просмотр</option>
                <option value="subscription">Подписка</option>
                <option value="comment">Комментарий</option>
              </select>
            </div>

            {/* Название */}
            <div className="form-field-group">
              <label className="form-label">
                Название задания
              </label>
              <input
                type="text"
                value={formData.title}
                onChange={(e) => {
                  setFormData({ ...formData, title: e.target.value })
                  if (errors.title) setErrors({ ...errors, title: '' })
                }}
                placeholder="Краткое и понятное название задания"
                className={`form-input ${errors.title ? 'error' : ''}`}
              />
              {errors.title && <div className="form-error">{errors.title}</div>}
            </div>

            {/* Описание */}
            <div className="form-field-group">
              <label className="form-label">
                Описание
              </label>
              <textarea
                value={formData.description}
                onChange={(e) => {
                  setFormData({ ...formData, description: e.target.value })
                  if (errors.description) setErrors({ ...errors, description: '' })
                }}
                rows={2}
                placeholder="Краткое описание о чем пост"
                className={`form-input ${errors.description ? 'error' : ''}`}
              />
              {errors.description && <div className="form-error">{errors.description}</div>}
            </div>

            {/* Цена, Слоты, Бюджет - новая логика */}
            <div className="pricing-box">
              <div className="form-row-pricing">
                <div className="form-field-group">
                  <label className="form-label">
                    Стоимость слота
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    value={formData.price_per_slot_ton}
                    onChange={(e) => {
                      setFormData({ ...formData, price_per_slot_ton: e.target.value })
                      if (errors.price_per_slot_ton) setErrors({ ...errors, price_per_slot_ton: '' })
                    }}
                    min="0.1"
                    placeholder="0.5" 
                    className={`form-input ${errors.price_per_slot_ton ? 'error' : ''}`}
                  />
                  {errors.price_per_slot_ton && <div className="form-error">{errors.price_per_slot_ton}</div>}
                </div>

                <div className="form-field-group">
                  <label className="form-label">
                    Количество слотов
                  </label>
                  <input
                    type="number"
                    value={formData.total_slots}
                    onChange={(e) => {
                      setFormData({ ...formData, total_slots: e.target.value })
                      if (errors.total_slots) setErrors({ ...errors, total_slots: '' })
                    }}
                    min="1"
                    placeholder={`Макс: ${maxSlots}`}
                    className={`form-input ${errors.total_slots ? 'error' : ''}`}
                  />
                  {errors.total_slots && <div className="form-error">{errors.total_slots}</div>}
                </div>

                <div className="form-field-group budget-group">
                  <label className="form-label">
                    Бюджет кампании
                  </label>
                  <div className="budget-display">
                    {campaignBudget > 0 ? campaignBudget.toFixed(2) : '0'}
                  </div>
                </div>
              </div>
            </div>

            {/* ID канала */}
            {(formData.task_type === 'subscription' || formData.task_type === 'comment') && (
              <div className="form-field-group">
                <label className="form-label">
                  ID канала Telegram
                </label>
                <input
                  type="text"
                  value={formData.telegram_channel_id}
                  onChange={(e) => {
                    setFormData({ ...formData, telegram_channel_id: e.target.value })
                    if (errors.telegram_channel_id) setErrors({ ...errors, telegram_channel_id: '' })
                  }}
                  placeholder="@channelname"
                  className={`form-input ${errors.telegram_channel_id ? 'error' : ''}`}
                />
                {errors.telegram_channel_id && <div className="form-error">{errors.telegram_channel_id}</div>}
              </div>
            )}

            {/* Ссылка на пост */}
            {(formData.task_type === 'comment' || formData.task_type === 'view') && (
              <div className="form-field-group">
                <label className="form-label">
                  Ссылка на пост{' '}
                  <button
                    type="button"
                    className="helper-link"
                    onClick={() => setShowPostHelp(true)}
                  >
                    инструкция
                  </button>
                </label>
                <input
                  type="text"
                  value={formData.telegram_post_id}
                  onChange={(e) => {
                    setFormData({ ...formData, telegram_post_id: e.target.value })
                    if (errors.telegram_post_id) setErrors({ ...errors, telegram_post_id: '' })
                  }}
                  placeholder="Ссылка на пост"
                  className={`form-input ${errors.telegram_post_id ? 'error' : ''}`}
                />
                {errors.telegram_post_id && <div className="form-error">{errors.telegram_post_id}</div>}
              </div>
            )}

            {/* Инструкция для комментария */}
            {formData.task_type === 'comment' && (
              <div className="form-field-group">
                <label className="form-label">
                  Инструкция для комментария
                </label>
                <textarea
                  value={formData.comment_instruction}
                  onChange={(e) => {
                    setFormData({ ...formData, comment_instruction: e.target.value })
                    if (errors.comment_instruction) setErrors({ ...errors, comment_instruction: '' })
                  }}
                  rows={3}
                  placeholder="Опишите, какой комментарий нужно оставить"
                  className={`form-input ${errors.comment_instruction ? 'error' : ''}`}
                />
                {errors.comment_instruction && <div className="form-error">{errors.comment_instruction}</div>}
              </div>
            )}

            {/* Страна */}
            <div className="form-field-group">
              <label className="form-label">Страна исполнителя</label>
              <select
                value={formData.target_country}
                onChange={(e) => setFormData({ ...formData, target_country: e.target.value })}
                className="form-input"
                style={{ color: '#333' }}
              >
                <option value="">Все страны</option>
                <option value="Россия">Россия</option>
                <option value="Украина">Украина</option>
                <option value="Беларусь">Беларусь</option>
                <option value="Казахстан">Казахстан</option>
                <option value="США">США</option>
                <option value="Германия">Германия</option>
                {/* Другие страны... */}
              </select>
            </div>

            {/* Пол и Возраст в одной строке */}
            <div className="form-row-gender-age">
              <div className="form-field-group gender-group">
                <label className="form-label">Пол исполнителя</label>
                <div className="gender-checkboxes">
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={genderSelection.male}
                      onChange={(e) => setGenderSelection({ ...genderSelection, male: e.target.checked })}
                    />
                    М
                  </label>
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={genderSelection.female}
                      onChange={(e) => setGenderSelection({ ...genderSelection, female: e.target.checked })}
                    />
                    Ж
                  </label>
                </div>
                {errors.target_gender && <div className="form-error">{errors.target_gender}</div>}
              </div>

              <div className="form-field-group age-group">
                <label className="form-label">Возраст</label>
                <div className="age-inputs">
                  <input
                    type="number"
                    value={formData.target_age_min}
                    onChange={(e) => setFormData({ ...formData, target_age_min: e.target.value })}
                    min="1"
                    max="100"
                    placeholder="От"
                    className="form-input age-input"
                  />
                  <span className="age-separator">-</span>
                  <input
                    type="number"
                    value={formData.target_age_max}
                    onChange={(e) => setFormData({ ...formData, target_age_max: e.target.value })}
                    min="1"
                    max="100"
                    placeholder="До"
                    className="form-input age-input"
                  />
                </div>
              </div>

      {showPostHelp && (
        <TermsModal
          title="Как получить ссылку на пост"
          content={`1) Откройте публикацию в Telegram.\n2) Нажмите «Поделиться».\n3) Выберите «Копировать ссылку».\n4) Вставьте ссылку в поле «Ссылка на пост».`}
          onClose={() => setShowPostHelp(false)}
        />
      )}
            </div>

            {/* Информация о боте */}
            {(formData.task_type === 'subscription' || formData.task_type === 'comment') && (
              <div className="admin-bot-info-end">
                <label className="bot-checkbox-label">
                  <input
                    type="checkbox"
                    checked={botAdded}
                    onChange={(e) => setBotAdded(e.target.checked)}
                  />
                  <span>
                    Бот-администратор добавлен в группу{' '}
                    <button
                      type="button"
                      className="rules-link"
                      onClick={(e) => {
                        e.preventDefault()
                        setShowBotRules(true)
                      }}
                    >
                      Правила
                    </button>
                  </span>
                </label>
              </div>
            )}
          </div>

          <div className="create-task-modal-footer">
            <button
              type="button"
              className="cancel-button"
              onClick={onClose}
              disabled={submitting}
            >
              Отмена
            </button>
            <button
              type="submit"
              className="submit-button"
              disabled={submitting || ((formData.task_type === 'subscription' || formData.task_type === 'comment') && !botAdded)}
            >
              {submitting ? 'Создание...' : 'Создать'}
            </button>
          </div>
        </form>
      </div>

      {showBotRules && (
        <TermsModal
          title="Правила использования бота-администратора"
          content={BOT_RULES_TEXT}
          onClose={() => setShowBotRules(false)}
        />
      )}
    </div>
  )
}

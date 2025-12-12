import { useState, useEffect } from 'react'
import { X, Copy } from 'lucide-react'
import TermsModal from './TermsModal'
import { useAuth } from '../context/AuthContext'
import axios from 'axios'
import './CreateTaskModal.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const ADMIN_BOT = '@BlackMirrowAdminBot'

const BOT_RULES_TEXT = `
🔐 Правила для работы бота с заданиями

Добавьте бота @BlackMirrowAdminBot администратором вашего канала и отключите ему все права.

Что сможет бот
✅ Основная задача: Проверять задания, запрашивая у Telegram:
• Факт подписки конкретного пользователя на канал
• Факт публикации комментария
✅ Контроль контента: Автоматически отслеживать комментарии на наличие:
• Нормативной лексики
• Запрещённого контента
• Спама и оскорблений

Что не сможет бот
❌ Отправлять или удалять сообщения в вашем канале
❌ Изменять профиль канала
❌ Управлять подписчиками
❌ Назначать администраторов

Система модерации и уведомлений
• При нарушении правил пользователь автоматически блокируется в приложении
• Вам приходит уведомление в профиль с деталями нарушения
• Канал защищён от некачественных и рисковых активностей
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
  const [fiatCurrency, setFiatCurrency] = useState<string>('RUB')
  const [fiatRate, setFiatRate] = useState<number>(250)
  
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
  const [botCopied, setBotCopied] = useState(false)

  // Загрузка баланса и валюты для расчета макс. слотов
  useEffect(() => {
    async function fetchBalance() {
      if (!user) return
      try {
        // Загружаем валюту из localStorage
        const storedCurrency = typeof window !== 'undefined' 
          ? localStorage.getItem('fiatCurrency')
          : null
        if (storedCurrency && ['RUB', 'USD', 'EUR', 'TON'].includes(storedCurrency)) {
          setFiatCurrency(storedCurrency)
        }
        
        // Загружаем курс из localStorage
        const storedRate = typeof window !== 'undefined'
          ? parseFloat(localStorage.getItem('fiatRatePerTon') || '0')
          : 0
        if (storedRate > 0) {
          setFiatRate(storedRate)
        }
        
        const response = await axios.get(`${API_URL}/api/balance/${user.telegram_id}`)
        if (response.data && response.data.ton_active_balance) {
          setUserBalance(parseFloat(response.data.ton_active_balance) / 10**9)
        }
        
        // Если нет в localStorage, загружаем с бэкенда
        if (!storedCurrency && response.data?.fiat_currency) {
          setFiatCurrency(response.data.fiat_currency)
          if (typeof window !== 'undefined') {
            localStorage.setItem('fiatCurrency', response.data.fiat_currency)
          }
        }
        if (storedRate === 0) {
          if (response.data?.last_fiat_rate) {
            const rate = parseFloat(response.data.last_fiat_rate) || 250
            setFiatRate(rate)
            if (typeof window !== 'undefined') {
              localStorage.setItem('fiatRatePerTon', rate.toString())
            }
          } else if (response.data?.fiat_currency) {
            const rates: Record<string, number> = { RUB: 250, USD: 3.5, EUR: 3.2, TON: 1 }
            const rate = rates[response.data.fiat_currency] ?? 250
            setFiatRate(rate)
            if (typeof window !== 'undefined') {
              localStorage.setItem('fiatRatePerTon', rate.toString())
            }
          }
        }
      } catch (error) {
        console.error('Failed to fetch balance', error)
      }
    }
    fetchBalance()
  }, [user])


  // Расчет бюджета и макс слотов
  // Если валюта не TON, то пользователь вводит цену в выбранной валюте, нужно конвертировать в TON
  const priceInput = parseFloat(formData.price_per_slot_ton) || 0
  const safeFiatRate = (fiatRate > 0 && isFinite(fiatRate)) ? fiatRate : 250 // Защита от деления на ноль и NaN/Infinity
  const priceInTon = fiatCurrency === 'TON' 
    ? priceInput 
    : (safeFiatRate > 0 ? (priceInput / safeFiatRate) : 0) // Конвертируем из выбранной валюты в TON
  
  // Защита от NaN и Infinity
  const safePriceInTon = (isFinite(priceInTon) && priceInTon >= 0) ? priceInTon : 0
  
  const slots = parseInt(formData.total_slots) || 0
  const campaignBudgetInTon = safePriceInTon * slots // Бюджет в TON
  const maxSlots = safePriceInTon > 0 ? Math.floor(userBalance / safePriceInTon) : 0
  
  // Отображение бюджета в выбранной валюте
  const campaignBudgetDisplay = fiatCurrency === 'TON' 
    ? campaignBudgetInTon 
    : (isFinite(campaignBudgetInTon * safeFiatRate) ? campaignBudgetInTon * safeFiatRate : 0)

  // Средняя стоимость за слот по типу задания
  const getAveragePrice = (taskType: string): string => {
    const averages: Record<string, string> = {
      'view': '0.3',
      'subscription': '0.5',
      'comment': '0.7'
    }
    return averages[taskType] || '0.5'
  }

  function validateForm(): boolean {
    const newErrors: Record<string, string> = {}
    
    const descTrim = formData.description.trim()
    if (!descTrim) {
      newErrors.description = 'Описание обязательно'
    } else {
      const words = descTrim.split(/\s+/).filter(Boolean)
      if (words.length < 3) {
        newErrors.description = 'Минимум 3 слова'
      }
    }
    
    if (!formData.price_per_slot_ton || priceInput <= 0) {
      newErrors.price_per_slot_ton = 'Цена должна быть больше 0'
    }
    
    if (!formData.total_slots || slots < 1) {
      newErrors.total_slots = 'Количество слотов должно быть не менее 1'
    }

    // Проверяем баланс в TON (конвертируем введенную цену в TON если нужно)
    const safeBudgetInTon = isFinite(campaignBudgetInTon) ? campaignBudgetInTon : 0
    if (safeBudgetInTon > userBalance) {
      const balanceDisplay = fiatCurrency === 'TON' 
        ? userBalance.toFixed(4) + ' TON'
        : (isFinite(userBalance * safeFiatRate) ? (userBalance * safeFiatRate).toFixed(2) : '0.00') + ` ${fiatCurrency === 'USD' ? '$' : fiatCurrency === 'EUR' ? '€' : '₽'}`
      const budgetDisplay = fiatCurrency === 'TON'
        ? safeBudgetInTon.toFixed(4) + ' TON'
        : (isFinite(campaignBudgetDisplay) ? campaignBudgetDisplay.toFixed(2) : '0.00') + ` ${fiatCurrency === 'USD' ? '$' : fiatCurrency === 'EUR' ? '€' : '₽'}`
      newErrors.total_slots = `Недостаточно средств. Ваш баланс: ${balanceDisplay}, требуется: ${budgetDisplay}`
    }
    
    
    if ((formData.task_type === 'comment' || formData.task_type === 'view') && !formData.telegram_post_id) {
      newErrors.telegram_post_id = 'Ссылка поста обязательна'
    }
    
    if (formData.task_type === 'subscription' && !formData.telegram_channel_id) {
      newErrors.telegram_channel_id = 'Ссылка на канал обязательна'
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

    // Конвертируем цену в TON если валюта не TON
    const safeFiatRate = (fiatRate > 0 && isFinite(fiatRate)) ? fiatRate : 250 // Защита от деления на ноль и NaN/Infinity
    const priceInputValue = parseFloat(formData.price_per_slot_ton) || 0
    const priceInTon = fiatCurrency === 'TON' 
      ? priceInputValue 
      : (safeFiatRate > 0 ? (priceInputValue / safeFiatRate) : 0)
    
    // Защита от NaN и Infinity
    const safePriceInTon = (isFinite(priceInTon) && priceInTon >= 0) ? priceInTon : 0

    const submissionData = {
      ...formData,
      title: formData.title.trim() || 'Задание',
      target_gender: finalGender,
      price_per_slot_ton: safePriceInTon.toString() // Отправляем цену в TON
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
    <div className="create-task-modal-overlay">
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
                placeholder={
                  formData.task_type === 'subscription'
                    ? 'Краткое описание о чем канал'
                    : formData.task_type === 'comment'
                    ? 'Напишите о чем ваш пост и какой комментарий вы хотете увидеть'
                    : 'Краткое описание о чем пост'
                }
                className={`form-input ${errors.description ? 'error' : ''}`}
              />
              {errors.description && <div className="form-error">{errors.description}</div>}
            </div>

            {/* Цена, Слоты, Бюджет - новая логика */}
            <div className="pricing-box">
              <div className="form-row-pricing">
                <div className="form-field-group">
                  <label className="form-label">
                    Стоимость слота ({fiatCurrency === 'TON' ? 'TON' : fiatCurrency === 'USD' ? '$' : fiatCurrency === 'EUR' ? '€' : '₽'})
                    {fiatCurrency !== 'TON' && safePriceInTon > 0 && isFinite(safePriceInTon) && ` (≈ ${safePriceInTon.toFixed(4)} TON)`}
                  </label>
                  <input
                    type="number"
                    step={fiatCurrency === 'TON' ? "0.1" : "1"}
                    value={formData.price_per_slot_ton}
                    onChange={(e) => {
                      setFormData({ ...formData, price_per_slot_ton: e.target.value })
                      if (errors.price_per_slot_ton) setErrors({ ...errors, price_per_slot_ton: '' })
                    }}
                    min={fiatCurrency === 'TON' ? "0.1" : "1"}
                    placeholder="" 
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
                    placeholder=""
                    className={`form-input ${errors.total_slots ? 'error' : ''}`}
                  />
                  {errors.total_slots && <div className="form-error">{errors.total_slots}</div>}
                </div>

                <div className="form-field-group budget-group">
                  <label className="form-label">
                    Бюджет кампании ({fiatCurrency === 'TON' ? 'TON' : fiatCurrency === 'USD' ? '$' : fiatCurrency === 'EUR' ? '€' : '₽'})
                  </label>
                  <div className="budget-display">
                    {campaignBudgetInTon > 0 
                      ? (fiatCurrency === 'TON' 
                          ? `${campaignBudgetInTon.toFixed(4)} TON`
                          : `${isFinite(campaignBudgetDisplay) ? campaignBudgetDisplay.toFixed(2) : '0.00'} ${fiatCurrency === 'USD' ? '$' : fiatCurrency === 'EUR' ? '€' : '₽'}`)
                      : `0 ${fiatCurrency === 'TON' ? 'TON' : fiatCurrency === 'USD' ? '$' : fiatCurrency === 'EUR' ? '€' : '₽'}`}
                  </div>
                </div>
              </div>
              <div className="average-price-hint">
                Средняя стоимость за слот: {fiatCurrency === 'TON' 
                  ? `${getAveragePrice(formData.task_type)} TON`
                  : `${(parseFloat(getAveragePrice(formData.task_type)) * safeFiatRate).toFixed(2)} ${fiatCurrency === 'USD' ? '$' : fiatCurrency === 'EUR' ? '€' : '₽'} (${getAveragePrice(formData.task_type)} TON)`}
              </div>
            </div>

            {/* Ссылка на канал */}
            {formData.task_type === 'subscription' && (
              <div className="form-field-group">
                <label className="form-label">
                  Ссылка на канал
                </label>
                <input
                  type="text"
                  value={formData.telegram_channel_id}
                  onChange={(e) => {
                    setFormData({ ...formData, telegram_channel_id: e.target.value })
                    if (errors.telegram_channel_id) setErrors({ ...errors, telegram_channel_id: '' })
                  }}
                  placeholder="https://t.me/yourchannel"
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

            </div>


            {/* Информация о боте */}
            {(formData.task_type === 'subscription' || formData.task_type === 'comment') && (
              <div className="admin-bot-info-end bot-box">
                <div className="bot-info-text">
                  Добавьте нашего бота админом в свой канал
                </div>
                <div className="bot-actions-row">
                  <button
                    type="button"
                    className="copy-bot-button"
                    onClick={async () => {
                      await navigator.clipboard.writeText(ADMIN_BOT)
                      setBotCopied(true)
                      setTimeout(() => setBotCopied(false), 2000)
                    }}
                  >
                    {botCopied ? 'Бот скопирован' : 'Копировать бота'}
                  </button>
                  <button
                    type="button"
                    className="rules-button"
                    onClick={(e) => {
                      e.preventDefault()
                      setShowBotRules(true)
                    }}
                  >
                    Правила
                  </button>
                </div>
                <label className="bot-checkbox-label">
                  <input
                    type="checkbox"
                    checked={botAdded}
                    onChange={(e) => setBotAdded(e.target.checked)}
                  />
                  <span>Бот добавлен</span>
                </label>
              </div>
            )}

            {/* Кнопка Создать */}
            <div className="form-field-group" style={{ marginTop: '24px' }}>
              <button
                type="submit"
                className="submit-button-full"
                disabled={submitting}
              >
                {submitting ? 'Создание...' : 'Создать'}
              </button>
            </div>
          </div>
        </form>
      </div>

      {showPostHelp && (
        <TermsModal
          title="Как получить ссылку на пост"
          content={`1) Откройте публикацию в Telegram.\n2) Нажмите «Поделиться».\n3) Выберите «Копировать ссылку».\n4) Вставьте ссылку в поле «Ссылка на пост».`}
          onClose={() => setShowPostHelp(false)}
        />
      )}

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

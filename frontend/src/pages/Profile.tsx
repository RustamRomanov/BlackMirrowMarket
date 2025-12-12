import { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { initData } from '@twa-dev/sdk'
import axios from 'axios'
import { Users, TrendingUp } from 'lucide-react'
import TermsModal from '../components/TermsModal'
import { COUNTRIES, getCountryByCode } from '../data/countries'
import './Profile.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface ReferralInfo {
  referral_code: string
  referral_link: string
  total_referrals: number
  total_earned_ton: string
  total_earned_fiat: string
}

interface ReferralDetail {
  referred_username?: string
  referred_first_name?: string
  total_earned_ton: string
  commission_earned_ton: string
  created_at: string
}

interface TaskStats {
  subscription: { today_count: number; total_count: number; today_earned: string; total_earned: string }
  comment: { today_count: number; total_count: number; today_earned: string; total_earned: string }
  view: { today_count: number; total_count: number; today_earned: string; total_earned: string }
}

const TERMS_TEXT = `ПРАВИЛА ПОЛЬЗОВАНИЯ ПРИЛОЖЕНИЕМ

1. Общие положения
1.1. Настоящие Правила определяют порядок использования приложения BlackMirrowMarket.
1.2. Используя приложение, вы соглашаетесь с данными Правилами.

2. Обязанности пользователя
2.1. Пользователь обязуется выполнять задания добросовестно и в соответствии с инструкциями.
2.2. Запрещается использование автоматизированных средств для выполнения заданий.
2.3. Пользователь несет ответственность за достоверность предоставленной информации.

3. Финансовые условия
3.1. Выплаты производятся в соответствии с условиями заданий.
3.2. Платформа взимает комиссию 10% с каждого выполненного задания. Комиссия вычитается с пользователя, который выполнил задание (исполнителя).
3.3. Средства зачисляются после проверки выполнения задания.
3.4. Если пользователь пришел по реферальной ссылке, он дополнительно отдает 5% с каждого выполненного задания своему рефералу.
3.5. Только комиссия 10% является прибылью приложения.

4. Реферальная система
4.1. Пользователи могут приглашать других пользователей по реферальной ссылке.
4.2. За каждое выполненное задание рефералом, реферер получает 5% от суммы задания.
4.3. Реферальные выплаты начисляются автоматически после проверки выполнения задания.

5. Ответственность
5.1. Платформа не несет ответственности за действия третьих лиц.
5.2. Пользователь несет ответственность за соблюдение правил Telegram.

6. Изменения в Правилах
6.1. Платформа оставляет за собой право изменять Правила.
6.2. Изменения вступают в силу с момента публикации.`

const AGREEMENT_TEXT = `ПОЛЬЗОВАТЕЛЬСКОЕ СОГЛАШЕНИЕ

1. Предмет соглашения
1.1. Настоящее Соглашение регулирует отношения между Пользователем и Платформой BlackMirrowMarket.
1.2. Используя приложение, Пользователь принимает условия настоящего Соглашения.

2. Права и обязанности
2.1. Пользователь имеет право использовать функционал приложения в соответствии с Правилами.
2.2. Пользователь обязуется соблюдать Правила пользования приложением.

3. Конфиденциальность
3.1. Платформа обязуется защищать персональные данные Пользователя.
3.2. Пользователь дает согласие на обработку персональных данных.

4. Интеллектуальная собственность
4.1. Все права на приложение принадлежат Платформе.
4.2. Пользователь не вправе копировать или распространять материалы приложения.

5. Заключительные положения
5.1. Соглашение действует до момента его расторжения.
5.2. Платформа оставляет за собой право расторгнуть Соглашение в случае нарушения Правил.`

export default function Profile() {
  const { user, updateUser } = useAuth()
  const { showSuccess, showError } = useToast()
  const [age, setAge] = useState<number | ''>('')
  const [gender, setGender] = useState('')
  const [country, setCountry] = useState('')
  const [saving, setSaving] = useState(false)
  const [termsAccepted, setTermsAccepted] = useState(false)
  const [referralInfo, setReferralInfo] = useState<ReferralInfo | null>(null)
  const [referrals, setReferrals] = useState<ReferralDetail[]>([])
  const [showTermsModal, setShowTermsModal] = useState(false)
  const [showAgreementModal, setShowAgreementModal] = useState(false)
  const [loadingReferrals, setLoadingReferrals] = useState(false)
  const [taskStats, setTaskStats] = useState<TaskStats | null>(null)

  useEffect(() => {
    if (user) {
      setAge(user.age || '')
      setGender(user.gender || '')
      
      // Определяем страну по умолчанию из Telegram
      let defaultCountry = user.country || ''
      
      if (!defaultCountry && initData?.user) {
        // Пытаемся определить страну из языка пользователя
        const userLanguage = initData.user.languageCode?.toUpperCase()
        
        // Маппинг языков на страны
        const languageToCountry: Record<string, string> = {
          'RU': 'Россия',
          'EN': 'США',
          'UK': 'Украина',
          'BY': 'Беларусь',
          'KZ': 'Казахстан',
          'UZ': 'Узбекистан',
          'AZ': 'Азербайджан',
          'AM': 'Армения',
          'GE': 'Грузия',
          'MD': 'Молдова',
          'KG': 'Кыргызстан',
          'TJ': 'Таджикистан',
          'TM': 'Туркменистан',
          'DE': 'Германия',
          'FR': 'Франция',
          'ES': 'Испания',
          'IT': 'Италия',
          'PL': 'Польша',
          'TR': 'Турция',
          'IN': 'Индия',
          'ID': 'Индонезия',
          'BR': 'Бразилия',
          'MX': 'Мексика',
          'AR': 'Аргентина',
          'CN': 'Китай',
          'JP': 'Япония',
          'KR': 'Корея'
        }
        
        if (userLanguage && languageToCountry[userLanguage]) {
          defaultCountry = languageToCountry[userLanguage]
        }
      }
      
      // Если страна не установлена, используем Россию по умолчанию
      if (!defaultCountry || !COUNTRIES.includes(defaultCountry)) {
        defaultCountry = 'Россия'
      }
      
      setCountry(defaultCountry)
      setTermsAccepted(user.terms_accepted || false)
      loadReferralInfo()
      loadTaskStats()
    }
  }, [user])

  async function loadReferralInfo() {
    if (!user) return
    
    setLoadingReferrals(true)
    try {
      const [infoResponse, referralsResponse] = await Promise.all([
        axios.get(`${API_URL}/api/users/${user.telegram_id}/referral-info`),
        axios.get(`${API_URL}/api/users/${user.telegram_id}/referrals`)
      ])
      setReferralInfo(infoResponse.data)
      setReferrals(referralsResponse.data)
    } catch (error) {
      console.error('Error loading referral info:', error)
    } finally {
      setLoadingReferrals(false)
    }
  }

  async function loadTaskStats() {
    if (!user) return
    
    try {
      const response = await axios.get(`${API_URL}/api/balance/${user.telegram_id}/task-stats`)
      setTaskStats(response.data)
    } catch (error) {
      console.error('Error loading task stats:', error)
    }
  }

  async function copyReferralLink() {
    if (!referralInfo) return
    
    try {
      await navigator.clipboard.writeText(referralInfo.referral_link)
      showSuccess('Реферальная ссылка скопирована!')
    } catch (error) {
      showError('Не удалось скопировать ссылку')
    }
  }

  async function handleSave() {
    if (!age || !gender || !country) {
      showError('Заполните все обязательные поля')
      return
    }

    if (!termsAccepted) {
      showError('Необходимо принять Правила и Соглашение')
      return
    }

    if (!user) {
      showError('Пользователь не найден')
      return
    }

    setSaving(true)
    try {
      // Обновляем пользователя через updateUser, который обновит состояние
      await updateUser({
        age: Number(age),
        gender,
        country,
        terms_accepted: true
      })
      showSuccess('Профиль обновлен')
    } catch (error: any) {
      console.error('Error saving profile:', error)
      showError(error.response?.data?.detail || 'Ошибка при сохранении профиля')
    } finally {
      setSaving(false)
    }
  }

  const isComplete = age && gender && country
  const profileFilled = user?.age && user?.gender && user?.country

  // Проверяем блокировку
  const isBanned = user?.is_banned || false
  const banUntil = user?.ban_until ? new Date(user.ban_until) : null
  const banReason = user?.ban_reason || 'Не указана'
  const isPermanentlyBanned = isBanned && !banUntil
  const isTemporarilyBanned = isBanned && banUntil && banUntil > new Date()

  return (
    <div className="profile-page">
      <h1>Профиль</h1>
      
      {/* Блок информации о блокировке */}
      {isBanned && (
        <div className="ban-notice" style={{
          background: '#ffebee',
          border: '2px solid #f44336',
          borderRadius: '8px',
          padding: '20px',
          marginBottom: '20px',
          color: '#c62828'
        }}>
          <h2 style={{ marginTop: 0, color: '#c62828', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '24px' }}>🚫</span>
            Ваш аккаунт заблокирован
          </h2>
          {isPermanentlyBanned ? (
            <p style={{ margin: '10px 0', fontWeight: 'bold' }}>Блокировка: <span style={{ color: '#d32f2f' }}>Постоянная</span></p>
          ) : isTemporarilyBanned ? (
            <p style={{ margin: '10px 0', fontWeight: 'bold' }}>
              Блокировка до: <span style={{ color: '#d32f2f' }}>{banUntil.toLocaleString('ru-RU', { 
                year: 'numeric', 
                month: 'long', 
                day: 'numeric', 
                hour: '2-digit', 
                minute: '2-digit' 
              })}</span>
            </p>
          ) : null}
          <div style={{ 
            background: 'white', 
            padding: '15px', 
            borderRadius: '6px', 
            marginTop: '15px',
            border: '1px solid #ffcdd2'
          }}>
            <p style={{ margin: '0 0 10px 0', fontWeight: 'bold', color: '#333' }}>Причина блокировки:</p>
            <p style={{ margin: 0, color: '#555', whiteSpace: 'pre-wrap' }}>{banReason}</p>
          </div>
          {isTemporarilyBanned && (
            <p style={{ marginTop: '15px', fontSize: '14px', color: '#666' }}>
              ⏰ Блокировка будет автоматически снята после указанной даты.
            </p>
          )}
        </div>
      )}
      
      <div className="profile-card">
        <div className="profile-info">
          <div className="info-item">
            <label>ID</label>
            <span>{user?.telegram_id}</span>
          </div>
          <div className="info-item">
            <label>Username</label>
            <span>@{user?.username || 'Не указано'}</span>
          </div>
        </div>

        {/* Статистика выполненных заданий */}
        {taskStats && (
          <div className="task-stats-blocks-container">
            <div className="task-stat-block task-stat-block-subscription">
              <div className="task-stat-title">Подписка</div>
              <div className="task-stat-today">сегодня</div>
              <div className="task-stat-value">{taskStats.subscription.today_count}</div>
              <div className="task-stat-total">всего</div>
              <div className="task-stat-value">{taskStats.subscription.total_count}</div>
            </div>
            <div className="task-stat-block task-stat-block-comment">
              <div className="task-stat-title">Комментарий</div>
              <div className="task-stat-today">сегодня</div>
              <div className="task-stat-value">{taskStats.comment.today_count}</div>
              <div className="task-stat-total">всего</div>
              <div className="task-stat-value">{taskStats.comment.total_count}</div>
            </div>
            <div className="task-stat-block task-stat-block-view">
              <div className="task-stat-title">Просмотр</div>
              <div className="task-stat-today">сегодня</div>
              <div className="task-stat-value">{taskStats.view.today_count}</div>
              <div className="task-stat-total">всего</div>
              <div className="task-stat-value">{taskStats.view.total_count}</div>
            </div>
          </div>
        )}

        {!profileFilled ? (
          <div className="profile-form">
            <h2>Обязательные поля</h2>
            <p className="form-note">Заполните эти поля для доступа к заданиям</p>

            <div className="form-row-age-gender">
              <div className="form-group">
                <label>Возраст *</label>
                <select
                  value={age}
                  onChange={(e) => setAge(e.target.value ? Number(e.target.value) : '')}
                  className="form-select age-select"
                >
                  <option value="">Выберите возраст</option>
                  {Array.from({ length: 108 }, (_, i) => i + 13).map((ageValue) => (
                    <option key={ageValue} value={ageValue}>
                      {ageValue}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Пол *</label>
                <select
                  value={gender}
                  onChange={(e) => setGender(e.target.value)}
                  className="form-select"
                >
                  <option value="">Выберите пол</option>
                  <option value="male">М</option>
                  <option value="female">Ж</option>
                </select>
              </div>
            </div>

            <div className="form-group">
              <label>Страна *</label>
              <select
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                className="form-select"
              >
                <option value="">Выберите страну</option>
                {COUNTRIES.map((countryName) => (
                  <option key={countryName} value={countryName}>
                    {countryName}
                  </option>
                ))}
              </select>
            </div>

            <div className="terms-section">
              <label className="terms-checkbox-label">
                <input
                  type="checkbox"
                  checked={termsAccepted}
                  onChange={(e) => setTermsAccepted(e.target.checked)}
                />
                <span>
                  Я принимаю{' '}
                  <button
                    type="button"
                    className="terms-link"
                    onClick={() => setShowTermsModal(true)}
                  >
                    Правила пользования приложением
                  </button>
                  {' '}и{' '}
                  <button
                    type="button"
                    className="terms-link"
                    onClick={() => setShowAgreementModal(true)}
                  >
                    Пользовательское соглашение
                  </button>
                </span>
              </label>
            </div>

            <button
              className="save-button"
              onClick={handleSave}
              disabled={saving || !isComplete || !termsAccepted}
            >
              {saving ? 'Сохранение...' : 'Сохранить'}
            </button>
          </div>
        ) : (
          <div className="profile-filled">
            <div className="profile-status ok">Профиль заполнен</div>
            <div className="inline-links">
              <button
                type="button"
                className="terms-link"
                onClick={() => setShowTermsModal(true)}
              >
                Правила пользования приложением
              </button>
              <span className="inline-sep">и</span>
              <button
                type="button"
                className="terms-link"
                onClick={() => setShowAgreementModal(true)}
              >
                Пользовательское соглашение
              </button>
            </div>
          </div>
        )}
      </div>

      {showTermsModal && (
        <TermsModal
          title="Правила пользования приложением"
          content={TERMS_TEXT}
          onClose={() => setShowTermsModal(false)}
        />
      )}

      {showAgreementModal && (
        <TermsModal
          title="Пользовательское соглашение"
          content={AGREEMENT_TEXT}
          onClose={() => setShowAgreementModal(false)}
        />
      )}
    </div>
  )
}


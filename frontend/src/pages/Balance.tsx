import { useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import axios from 'axios'
import { Copy, Users, TrendingUp, Info } from 'lucide-react'
import { useToast } from '../context/ToastContext'
import './Balance.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface Balance {
  ton_active_balance: string
  ton_escrow_balance: string
  fiat_balance: string
  fiat_currency: string
  subscription_limit_24h: number
  subscriptions_used_24h: number
}

interface ReferralInfo {
  referral_link: string
  total_referrals: number
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

export default function Balance() {
  const { user } = useAuth()
  const { showSuccess } = useToast()
  const [balance, setBalance] = useState<Balance | null>(null)
  const [loading, setLoading] = useState(true)
  const [fiatCurrency, setFiatCurrency] = useState<string>('RUB')
  const [showDepositInfo, setShowDepositInfo] = useState(false)
  const [showWithdrawForm, setShowWithdrawForm] = useState(false)
  const [depositInfo, setDepositInfo] = useState<{service_wallet_address: string, telegram_id?: number, username?: string, note?: string} | null>(null)
  const [withdrawAddress, setWithdrawAddress] = useState('')
  const [withdrawAmount, setWithdrawAmount] = useState('')
  const [withdrawLoading, setWithdrawLoading] = useState(false)
  const [referralInfo, setReferralInfo] = useState<ReferralInfo | null>(null)
  const [referrals, setReferrals] = useState<ReferralDetail[]>([])
  const [taskStats, setTaskStats] = useState<TaskStats | null>(null)

  useEffect(() => {
    if (user) {
      loadBalance()
      loadReferralInfo()
      loadTaskStats()
      const interval = setInterval(() => {
        loadBalance()
        loadReferralInfo()
        loadTaskStats()
      }, 5000)
      return () => clearInterval(interval)
    } else {
      setLoading(false)
    }
  }, [user])

  // Убрана автоматическая инициализация тестовых заданий
  // Тестовые задания создаются вручную через админку и помечаются как примеры

  async function loadBalance() {
    if (!user) {
      setLoading(false)
      return
    }
    
    try {
      const response = await axios.get(`${API_URL}/api/balance/${user.telegram_id}`)
      setBalance(response.data)
      if (response.data?.fiat_currency) {
        setFiatCurrency(response.data.fiat_currency)
      }
    } catch (error: any) {
      console.error('Error loading balance:', error)
      // Если пользователь не найден, попробуем создать его
      if (error.response?.status === 404) {
        try {
          await axios.post(`${API_URL}/api/users/`, {
            telegram_id: user.telegram_id,
            username: user.username,
            first_name: user.first_name
          })
          // Повторно загружаем баланс
          const retryResponse = await axios.get(`${API_URL}/api/balance/${user.telegram_id}`)
          setBalance(retryResponse.data)
          if (retryResponse.data?.fiat_currency) {
            setFiatCurrency(retryResponse.data.fiat_currency)
          }
        } catch (createError) {
          console.error('Error creating user:', createError)
          setBalance(null)
        }
      } else {
        setBalance(null)
      }
    } finally {
      setLoading(false)
    }
  }

  async function loadReferralInfo() {
    if (!user) return
    
    try {
      const [infoResponse, referralsResponse] = await Promise.all([
        axios.get(`${API_URL}/api/users/${user.telegram_id}/referral-info`),
        axios.get(`${API_URL}/api/users/${user.telegram_id}/referrals`)
      ])
      setReferralInfo(infoResponse.data)
      setReferrals(referralsResponse.data)
    } catch (error) {
      console.error('Error loading referral info:', error)
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
      console.error('Failed to copy:', error)
    }
  }

  async function changeCurrency(currency: string) {
    if (!user || !balance) return
    
    try {
      // Обновляем валюту на бэкенде
      await axios.patch(`${API_URL}/api/balance/${user.telegram_id}/currency`, null, {
        params: { currency }
      })
      setFiatCurrency(currency)
      loadBalance()
    } catch (error) {
      console.error('Error changing currency:', error)
    }
  }

  async function loadDepositInfo() {
    if (!user) return
    
    try {
      const response = await axios.get(`${API_URL}/api/balance/${user.telegram_id}/deposit-info`)
      setDepositInfo(response.data)
      setShowDepositInfo(true)
    } catch (error) {
      console.error('Error loading deposit info:', error)
      showSuccess('Ошибка загрузки информации о пополнении')
    }
  }

  async function handleWithdraw() {
    if (!user || !withdrawAddress || !withdrawAmount) {
      showSuccess('Заполните все поля')
      return
    }

    const amount = parseFloat(withdrawAmount)
    if (isNaN(amount) || amount <= 0) {
      showSuccess('Введите корректную сумму')
      return
    }

    if (amount > tonActive) {
      showSuccess('Недостаточно средств')
      return
    }

    setWithdrawLoading(true)
    try {
      const response = await axios.post(`${API_URL}/api/balance/${user.telegram_id}/withdraw`, {
        to_address: withdrawAddress,
        amount_ton: amount
      })
      
      showSuccess(`Вывод создан! Статус: ${response.data.status}. TX Hash: ${response.data.tx_hash || 'ожидается...'}`)
      setShowWithdrawForm(false)
      setWithdrawAddress('')
      setWithdrawAmount('')
      loadBalance()
    } catch (error: any) {
      showSuccess(error.response?.data?.detail || 'Ошибка при выводе средств')
    } finally {
      setWithdrawLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="balance-page">
        <h1>Баланс</h1>
        <div className="balance-loading">Загрузка...</div>
      </div>
    )
  }

  if (!balance) {
    return (
      <div className="balance-page">
        <h1>Баланс</h1>
        <div className="balance-error">
          <p>Не удалось загрузить баланс</p>
          <button onClick={loadBalance} className="retry-button">
            Повторить
          </button>
        </div>
      </div>
    )
  }

  const tonActive = parseFloat(balance.ton_active_balance) / 10**9
  const tonEscrow = parseFloat(balance.ton_escrow_balance) / 10**9
  const fiatActive = parseFloat(balance.fiat_balance)
  const fiatRate = tonActive > 0 ? fiatActive / tonActive : 250
  
  // Показываем реальные значения (0 если 0, без виртуальных сумм)
  const displayTonActive = Math.max(0, tonActive)  // Убеждаемся, что не отрицательное
  const displayTonEscrow = Math.max(0, tonEscrow)
  const displayFiatActive = Math.max(0, fiatActive)

  return (
    <div className="balance-page">
      <div className="balance-header">
        <h1>Баланс</h1>
        <select
          value={fiatCurrency}
          onChange={(e) => changeCurrency(e.target.value)}
          className="currency-select"
        >
          <option value="RUB">₽ RUB</option>
          <option value="USD">$ USD</option>
          <option value="EUR">€ EUR</option>
        </select>
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

      <div className="balance-card">
        <div className="balance-section">
          <div className="balance-label">Общий Баланс</div>
          <div className="balance-value-primary">
            {displayFiatActive.toFixed(2)} {fiatCurrency}
          </div>
          <div className="balance-value-secondary">
            {displayTonActive.toFixed(4)} TON
          </div>
        </div>

        <div className="balance-section">
          <div className="balance-label">В эскроу (в проверке)</div>
          <div className="balance-value-secondary">
            {displayTonEscrow.toFixed(4)} TON
          </div>
          <div className="balance-value-tertiary">
            {(displayTonEscrow * fiatRate).toFixed(2)} {fiatCurrency}
          </div>
        </div>

        <div className="balance-section">
          <div className="balance-label">Доступно для вывода</div>
          <div className="balance-value-secondary">
            {displayTonActive.toFixed(4)} TON
          </div>
          <div className="balance-value-tertiary">
            {displayFiatActive.toFixed(2)} {fiatCurrency}
          </div>
        </div>

        {displayTonActive < 0 && (
          <div className="balance-warning">
            ⚠️ У вас отрицательный баланс. Доступ к заданиям заблокирован.
          </div>
        )}
        
        {displayTonActive === 0 && displayTonEscrow === 0 && (
          <div style={{background: '#e3f2fd', borderLeft: '4px solid #2196f3', padding: '15px', marginTop: '15px', borderRadius: '8px'}}>
            <strong>💰 Ваш баланс пуст</strong>
            <p style={{margin: '8px 0 0 0', fontSize: '14px', color: '#666'}}>
              Пополните баланс, чтобы создавать задания (если вы заказчик) или выполнять задания для заработка (если вы исполнитель).
            </p>
          </div>
        )}

      </div>

      {/* Кнопки пополнения и вывода */}
      <div className="balance-actions">
        <button
          className="action-button deposit-button"
          onClick={loadDepositInfo}
        >
          💰 Пополнить
        </button>
        <button 
          className="action-button withdraw-button"
          onClick={() => setShowWithdrawForm(true)}
          disabled={displayTonActive <= 0}
        >
          💸 Вывести
        </button>
      </div>


      {/* Информация о пополнении */}
      {showDepositInfo && depositInfo && (
        <div className="deposit-info-modal">
          <div className="deposit-info-content">
            <button
              className="close-deposit-info"
              onClick={() => setShowDepositInfo(false)}
            >
              ×
            </button>
            <h3>💰 Пополнить баланс</h3>
            <div className="deposit-steps">
              <div className="deposit-step">
                <div className="step-number">1</div>
                <div className="step-content">
                  <strong>Откройте ваш кошелек TON</strong>
                  <p>Используйте Tonkeeper, MyTonWallet или другой кошелек TON</p>
                </div>
              </div>
              <div className="deposit-step">
                <div className="step-number">2</div>
                <div className="step-content">
                  <strong>Переведите TON на сервисный кошелек</strong>
                  <p style={{marginTop: '8px', marginBottom: '12px'}}>Скопируйте адрес сервисного кошелька и переведите TON с вашего внешнего кошелька (Tonkeeper, HTX и т.д.)</p>
                  <div style={{background: '#f5f5f5', padding: '12px', borderRadius: '8px', marginTop: '8px', fontFamily: 'monospace', fontSize: '12px', wordBreak: 'break-all'}}>
                    {depositInfo.service_wallet_address}
                  </div>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(depositInfo.service_wallet_address)
                      showSuccess('Адрес скопирован!')
                    }}
                    style={{marginTop: '8px', padding: '6px 12px', background: '#667eea', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer'}}
                  >
                    <Copy size={14} style={{display: 'inline', marginRight: '4px'}} />
                    Копировать адрес
                  </button>
                </div>
              </div>
              <div className="deposit-step">
                <div className="step-number">3</div>
                <div className="step-content">
                  <strong>⚠️ ВАЖНО: Укажите Telegram ID в комментарии</strong>
                  <p style={{marginTop: '8px', marginBottom: '12px'}}>При переводе в поле "Тег/Мемо" (комментарий к транзакции) обязательно укажите ваш Telegram ID:</p>
                  <div style={{
                    marginTop: '10px',
                    padding: '15px',
                    background: '#fff3cd',
                    border: '2px solid #ffc107',
                    borderRadius: '8px',
                    textAlign: 'center'
                  }}>
                    <div style={{fontSize: '12px', color: '#666', marginBottom: '8px'}}>Ваш Telegram ID:</div>
                    <div style={{
                      fontFamily: 'monospace',
                      fontSize: '24px',
                      fontWeight: 'bold',
                      color: '#d32f2f',
                      marginBottom: '12px'
                    }}>
                      {depositInfo.telegram_id || user?.telegram_id || 'не найден'}
                    </div>
                    <button
                      onClick={() => {
                        const telegramId = (depositInfo.telegram_id || user?.telegram_id)?.toString() || ''
                        navigator.clipboard.writeText(telegramId)
                        showSuccess('Telegram ID скопирован!')
                      }}
                      style={{
                        padding: '10px 20px',
                        background: '#ff9800',
                        color: 'white',
                        border: 'none',
                        borderRadius: '6px',
                        cursor: 'pointer',
                        fontSize: '14px',
                        fontWeight: '600',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '8px'
                      }}
                    >
                      <Copy size={16} />
                      Копировать Telegram ID
                    </button>
                    <div style={{marginTop: '12px', padding: '10px', background: '#e3f2fd', borderRadius: '6px', fontSize: '12px', color: '#1976d2', textAlign: 'left'}}>
                      💡 <strong>Как найти Telegram ID:</strong> Напишите боту <strong>@userinfobot</strong> в Telegram. Также ваш ID отображается в разделе "Профиль".
                    </div>
                  </div>
                </div>
              </div>
              <div className="deposit-step">
                <div className="step-number">4</div>
                <div className="step-content">
                  <strong>Автоматическое зачисление</strong>
                  <p>После подтверждения транзакции в блокчейне (обычно 1-2 минуты) система автоматически найдет ваш Telegram ID в комментарии и зачислит средства на ваш баланс. Обновите страницу для проверки.</p>
                </div>
              </div>
            </div>
            <div className="deposit-note">
              <Info size={18} />
              <p>Минимальная сумма пополнения: 0.01 TON. Не забудьте указать ваш Telegram ID в комментарии к транзакции для автоматического зачисления!</p>
            </div>
          </div>
        </div>
      )}

      {/* Форма вывода */}
      {showWithdrawForm && (
        <div className="deposit-info-modal">
          <div className="deposit-info-content">
            <button
              className="close-deposit-info"
              onClick={() => {
                setShowWithdrawForm(false)
                setWithdrawAddress('')
                setWithdrawAmount('')
              }}
            >
              ×
            </button>
            <h3>💸 Вывести средства</h3>
            <div style={{marginTop: '20px'}}>
              <label style={{display: 'block', marginBottom: '8px', fontWeight: '600'}}>
                Адрес вашего внешнего кошелька TON
              </label>
              <input
                type="text"
                value={withdrawAddress}
                onChange={(e) => setWithdrawAddress(e.target.value)}
                placeholder="EQ..."
                style={{width: '100%', padding: '12px', border: '1px solid #ddd', borderRadius: '8px', fontFamily: 'monospace', fontSize: '12px'}}
              />
            </div>
            <div style={{marginTop: '16px'}}>
              <label style={{display: 'block', marginBottom: '8px', fontWeight: '600'}}>
                Сумма (TON)
              </label>
              <input
                type="number"
                step="0.000000001"
                min="0"
                max={displayTonActive}
                value={withdrawAmount}
                onChange={(e) => setWithdrawAmount(e.target.value)}
                placeholder="0.1"
                style={{width: '100%', padding: '12px', border: '1px solid #ddd', borderRadius: '8px'}}
              />
              <div style={{marginTop: '4px', fontSize: '12px', color: '#666'}}>
                Доступно: {displayTonActive.toFixed(4)} TON
              </div>
            </div>
            <button
              onClick={handleWithdraw}
              disabled={withdrawLoading || !withdrawAddress || !withdrawAmount || parseFloat(withdrawAmount) <= 0 || parseFloat(withdrawAmount) > displayTonActive}
              style={{
                width: '100%',
                marginTop: '20px',
                padding: '12px',
                background: withdrawLoading ? '#ccc' : '#667eea',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                cursor: withdrawLoading ? 'not-allowed' : 'pointer',
                fontWeight: '600'
              }}
            >
              {withdrawLoading ? 'Отправка...' : 'Вывести TON'}
            </button>
            <div className="deposit-note" style={{marginTop: '16px'}}>
              <Info size={18} />
              <p>Средства будут отправлены с сервисного кошелька приложения на указанный адрес. Транзакция обрабатывается автоматически.</p>
            </div>
          </div>
        </div>
      )}

      {/* Реферальная программа */}
      {referralInfo && (
        <div className="referral-section-balance">
          <h2>Реферальная программа</h2>
          <p className="referral-description">
            Приглашайте друзей и получайте 5% от их заработка!
          </p>

          <div className="referral-info-card">
            <div className="referral-link-section">
              <label>Ваша реферальная ссылка:</label>
              <div className="referral-link-input">
                <input
                  type="text"
                  value={referralInfo.referral_link}
                  readOnly
                />
                <button
                  className="copy-button"
                  onClick={copyReferralLink}
                  title="Копировать"
                >
                  <Copy size={18} />
                </button>
              </div>
            </div>

            <div className="referral-stats">
              <div className="stat-item">
                <Users size={20} color="#667eea" />
                <div className="stat-value">{referralInfo.total_referrals}</div>
                <div className="stat-label">Рефералов</div>
              </div>
              <div className="stat-item">
                <TrendingUp size={20} color="#4CAF50" />
                <div className="stat-value">
                  {parseFloat(referralInfo.total_earned_fiat).toFixed(2)} {fiatCurrency}
                </div>
                <div className="stat-label">Заработано</div>
              </div>
            </div>

            {referrals.length > 0 && (
              <div className="referrals-list">
                <h3>Ваши рефералы:</h3>
                {referrals.map((ref, index) => (
                  <div key={index} className="referral-item">
                    <div className="referral-name">
                      {ref.referred_first_name || ref.referred_username || 'Пользователь'}
                    </div>
                    <div className="referral-earnings">
                      Заработано: {parseFloat(ref.total_earned_ton) / 10**9} TON
                      <br />
                      Ваша комиссия: {parseFloat(ref.commission_earned_ton) / 10**9} TON
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

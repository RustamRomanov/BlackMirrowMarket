import { useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import axios from 'axios'
import { Info } from 'lucide-react'
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

  useEffect(() => {
    if (user) {
      loadBalance()
      const interval = setInterval(() => {
        loadBalance()
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
      
      // Загружаем валюту из localStorage, если есть, иначе из бэкенда
      const storedCurrency = localStorage.getItem('fiatCurrency')
      if (storedCurrency && ['RUB', 'USD', 'EUR', 'TON'].includes(storedCurrency)) {
        setFiatCurrency(storedCurrency)
      } else if (response.data?.fiat_currency) {
        setFiatCurrency(response.data.fiat_currency)
        localStorage.setItem('fiatCurrency', response.data.fiat_currency)
      }
      
      // Сохраняем курс конвертации
      if (response.data) {
        const tonActive = parseFloat(response.data.ton_active_balance || '0') / 10**9
        const fiatActive = parseFloat(response.data.fiat_balance || '0')
        const fiatRate = tonActive > 0 ? fiatActive / tonActive : 250
        localStorage.setItem('fiatRatePerTon', fiatRate.toString())
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


  async function changeCurrency(currency: string) {
    if (!user || !balance) return
    
    try {
      // Обновляем валюту на бэкенде
      await axios.patch(`${API_URL}/api/balance/${user.telegram_id}/currency`, null, {
        params: { currency }
      })
      setFiatCurrency(currency)
      
      // Сохраняем валюту и курс в localStorage
      const tonActive = parseFloat(balance.ton_active_balance) / 10**9
      const fiatActive = parseFloat(balance.fiat_balance)
      const fiatRate = tonActive > 0 ? fiatActive / tonActive : 250
      
      localStorage.setItem('fiatCurrency', currency)
      localStorage.setItem('fiatRatePerTon', fiatRate.toString())
      
      // Отправляем событие для синхронизации в других вкладках
      window.dispatchEvent(new Event('storage'))
      window.dispatchEvent(new CustomEvent('currencyChanged', { detail: { currency, rate: fiatRate } }))
      
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
          <option value="TON">TON</option>
        </select>
      </div>

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
            {(displayTonEscrow * fiatRate).toFixed(2)} {fiatCurrency}
          </div>
          <div className="balance-value-tertiary">
            {displayTonEscrow.toFixed(4)} TON
          </div>
        </div>

        <div className="balance-section">
          <div className="balance-label">Доступно для вывода</div>
          <div className="balance-value-secondary">
            {displayFiatActive.toFixed(2)} {fiatCurrency}
          </div>
          <div className="balance-value-tertiary">
            {displayTonActive.toFixed(4)} TON
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


      {showDepositInfo && depositInfo && (
        <div className="deposit-info-modal">
          <div className="deposit-info-content">
            <button
              className="close-deposit-info"
              onClick={() => setShowDepositInfo(false)}
            >
              ×
            </button>
            <h3 style={{ marginBottom: '16px' }}>Пополнить баланс</h3>

            {/* Шаг 1 */}
            <div style={{ marginBottom: '14px', fontSize: '14px', color: '#333', fontWeight: 400 }}>
              1. Минимальная сумма пополнения: <span style={{ fontWeight: 700 }}>1 TON</span>
            </div>

            {/* Шаг 2 */}
            <div style={{ marginTop: '6px', fontSize: '14px', color: '#333', fontWeight: 400 }}>
              2. Отправьте TON по этому адресу:
            </div>
            <div style={{
              marginTop: '8px',
              background: '#e8f5e9',
              border: '1px solid #c8e6c9',
              padding: '12px',
              borderRadius: '12px',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              fontFamily: 'monospace',
              fontSize: '16px',
              lineHeight: 1.3
            }}>
              <div style={{ flex: 1, wordBreak: 'break-all' }}>
                {depositInfo.service_wallet_address}
              </div>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(depositInfo.service_wallet_address)
                  showSuccess('Адрес скопирован!')
                }}
                style={{
                  background: '#4caf50',
                  color: 'white',
                  border: 'none',
                  borderRadius: '8px',
                  padding: '8px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                <Copy size={16} />
              </button>
            </div>

            {/* Шаг 3 */}
            <div style={{ marginTop: '12px', fontSize: '14px', color: '#333', fontWeight: 400 }}>
              3. Обязательно укажите Telegram ID в комментарии/мемо:
            </div>
            <div style={{
              marginTop: '8px',
              background: '#fff3cd',
              border: '1px solid #ffe082',
              padding: '12px',
              borderRadius: '12px',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              lineHeight: 1.35
            }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: '12px', color: '#8a6d3b', marginBottom: '6px', fontWeight: 600 }}>
                  Укажите в комментарии/мемо:
                </div>
                <div style={{ fontFamily: 'monospace', fontSize: '20px', fontWeight: 700, color: '#bf360c' }}>
                  {user?.telegram_id}
                </div>
                <div style={{ fontSize: '11px', color: '#8a6d3b', marginTop: '6px', lineHeight: 1.25 }}>
                  Если не указать ID, зачисление может не произойти.
                </div>
              </div>
              <button
                onClick={() => {
                  const telegramId = (user?.telegram_id)?.toString() || ''
                  navigator.clipboard.writeText(telegramId)
                  showSuccess('Telegram ID скопирован!')
                }}
                style={{
                  background: '#ff9800',
                  color: 'white',
                  border: 'none',
                  borderRadius: '8px',
                  padding: '8px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                <Copy size={16} />
              </button>
            </div>

            {/* Шаг 4 */}
            <div style={{ marginTop: '12px', fontSize: '14px', color: '#333', fontWeight: 400 }}>
              4. После подтверждения сети (обычно 1–2 минуты) зачисление происходит автоматически.
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

    </div>
  )
}

import { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { User, TrendingUp, Plus, Wallet } from 'lucide-react'
import './Layout.css'

interface LayoutProps {
  children: ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const location = useLocation()

  const navItems = [
    { path: '/earn', icon: TrendingUp, label: 'Заработок' },
    { path: '/create', icon: Plus, label: 'Создать' },
    { path: '/balance', icon: Wallet, label: 'Баланс' },
    { path: '/profile', icon: User, label: 'Профиль' },
  ]

  return (
    <div className="layout">
      <main className="main-content">{children}</main>
      <nav className="bottom-nav">
        {navItems.map((item) => {
          const Icon = item.icon
          const isActive = location.pathname === item.path
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`nav-item ${isActive ? 'active' : ''}`}
            >
              <Icon size={20} />
              <span>{item.label}</span>
            </Link>
          )
        })}
      </nav>
    </div>
  )
}





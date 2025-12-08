import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { useEffect } from 'react'
import { initData } from '@twa-dev/sdk'
import Layout from './components/Layout'
import Profile from './pages/Profile'
import Earn from './pages/Earn'
import Create from './pages/Create'
import Balance from './pages/Balance'
import TaskDetail from './pages/TaskDetail'
import { AuthProvider } from './context/AuthContext'
import { ToastProvider } from './context/ToastContext'

function App() {
  useEffect(() => {
    // Инициализация Telegram Mini App
    console.log('Init data:', initData)
  }, [])

  return (
    <ToastProvider>
      <AuthProvider>
        <Router>
          <Layout>
            <Routes>
              <Route path="/" element={<Earn />} />
              <Route path="/profile" element={<Profile />} />
              <Route path="/earn" element={<Earn />} />
              <Route path="/create" element={<Create />} />
              <Route path="/balance" element={<Balance />} />
              <Route path="/task/:id" element={<TaskDetail />} />
            </Routes>
          </Layout>
        </Router>
      </AuthProvider>
    </ToastProvider>
  )
}

export default App

